import hmac
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class NisaPosWebhook(http.Controller):
    """POS -> Odoo satış bildirimi.

    İstek (JSON-RPC zarfı, Odoo type='jsonrpc' gereği):
        POST /nisa_pos_sync/webhook/sale
        Header: X-API-Key: <nisa_pos_sync.webhook_key>   (veya params.api_key)
        {
          "jsonrpc": "2.0", "method": "call",
          "params": {
            "api_key": "...",
            "lines": [{"barcode": "8690000000001", "qty": 2}]
          }
        }
    Tek ürün için `lines` yerine doğrudan params içinde `barcode`/`external_pos_id`
    ve `qty` da gönderilebilir.
    """

    @http.route('/nisa_pos_sync/webhook/sale', type='jsonrpc', auth='public', methods=['POST'])
    def sale_webhook(self, **payload):
        icp = request.env['ir.config_parameter'].sudo()
        expected = (icp.get_param('nisa_pos_sync.webhook_key') or '').strip()
        given = str(request.httprequest.headers.get('X-API-Key') or payload.get('api_key') or '')
        if not expected or not hmac.compare_digest(expected.encode(), given.encode()):
            _logger.warning("nisa_pos_sync: yetkisiz webhook isteği (IP: %s)",
                            request.httprequest.remote_addr)
            return {'status': 'error', 'message': 'unauthorized'}

        lines = payload.get('lines') or [payload]
        if not isinstance(lines, list):
            return {'status': 'error', 'message': 'lines bir liste olmalı'}

        env = request.env
        Product = env['product.template'].sudo()
        Log = env['nisa.sync.log'].sudo()
        results = []

        for line in lines:
            line = line if isinstance(line, dict) else {}
            ref = line.get('external_pos_id') or line.get('barcode')
            tmpl = Product.browse()
            ok, msg = False, ''
            try:
                raw_qty = line.get('qty', line.get('quantity'))
                if not ref:
                    msg = "barcode veya external_pos_id zorunlu"
                elif raw_qty is None or not float(raw_qty).is_integer() or int(raw_qty) <= 0:
                    msg = "qty pozitif bir tam sayı olmalı"
                else:
                    qty = int(raw_qty)
                    domain = ([('external_pos_id', '=', str(ref))] if line.get('external_pos_id')
                              else [('barcode', '=', str(ref))])
                    tmpl = Product.search(domain, limit=1)
                    if not tmpl:
                        msg = "ürün bulunamadı: %s" % ref
                    else:
                        with env.cr.savepoint():
                            # Atomik düşüm: eşzamanlı satışlarda yarış durumu olmaz.
                            tmpl.flush_recordset(['nisa_stock_qty'])
                            env.cr.execute(
                                "UPDATE product_template "
                                "SET nisa_stock_qty = nisa_stock_qty - %s "
                                "WHERE id = %s RETURNING nisa_stock_qty",
                                (qty, tmpl.id))
                            new_qty = env.cr.fetchone()[0]
                            tmpl.invalidate_recordset(['nisa_stock_qty'])
                        ok = True
                        msg = "satış işlendi: -%s, yeni stok: %s" % (qty, new_qty)
            except (ValueError, TypeError):
                msg = "geçersiz qty değeri"
            except Exception as exc:  # noqa: BLE001 - webhook asla 500 dönmemeli
                _logger.exception("nisa_pos_sync webhook hatası")
                msg = "sunucu hatası: %s" % exc

            Log.create({
                'product_tmpl_id': tmpl.id or False,
                'product_name': tmpl.name if tmpl else str(ref or ''),
                'operation': 'webhook_sale',
                'status': 'success' if ok else 'failed',
                'message': msg,
            })
            results.append({'ref': ref, 'ok': ok, 'message': msg})

        all_ok = all(r['ok'] for r in results)
        return {'status': 'ok' if all_ok else 'partial', 'results': results}
