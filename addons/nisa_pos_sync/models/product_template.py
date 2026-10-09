import logging

import requests

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15  # saniye


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    external_pos_id = fields.Char(
        'POS Ürün ID', copy=False, index=True,
        help='Harici POS sistemindeki karşılık gelen ürün ID\'si.')
    nisa_stock_qty = fields.Integer(
        'POS Stok Adedi', default=0, copy=False,
        help='POS ile senkronize edilen stok adedi. POS satış webhook\'u bunu düşürür.')
    nisa_last_sync = fields.Datetime('Son POS Senkronu', readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Odoo -> POS
    # ------------------------------------------------------------------
    def _nisa_get_config(self):
        icp = self.env['ir.config_parameter'].sudo()
        url = (icp.get_param('nisa_pos_sync.api_url') or '').strip()
        if not url:
            raise UserError(self.env._(
                "POS API adresi tanımlı değil. Ayarlar > Teknik > Sistem Parametreleri "
                "içinde 'nisa_pos_sync.api_url' değerini girin."))
        api_key = (icp.get_param('nisa_pos_sync.api_key') or '').strip()
        return url, api_key

    def _nisa_push_one(self, url, api_key):
        """Tek ürünü POS'a gönderir. Exception fırlatmaz.
        Dönüş: (başarılı_mı, mesaj, pos_id)"""
        self.ensure_one()
        if not self.barcode:
            return False, self.env._("Barkod tanımlı değil."), None

        payload = {
            'barcode': self.barcode,
            'name': self.name,
            'price': self.list_price,
            'stock': self.nisa_stock_qty,
        }
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['X-API-Key'] = api_key

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            return False, self.env._("Bağlantı hatası: %s", exc), None

        if not resp.ok:
            return False, self.env._(
                "HTTP %(code)s: %(body)s", code=resp.status_code, body=resp.text[:300]), None

        try:
            data = resp.json()
        except ValueError:
            data = {}
        pos_id = data.get('id') if isinstance(data, dict) else None
        return True, self.env._("POS'a gönderildi."), (str(pos_id) if pos_id else None)

    def action_nisa_sync_to_pos(self):
        """Seçili ürünleri POS'a senkronize eder (buton + server action)."""
        if not self:
            raise UserError(self.env._("Senkronize edilecek ürün seçilmedi."))
        url, api_key = self._nisa_get_config()

        now = fields.Datetime.now()
        logs, updates, errors = [], [], []
        ok_count = 0

        for rec in self:
            ok, msg, pos_id = rec._nisa_push_one(url, api_key)
            logs.append({
                'date': now,
                'product_tmpl_id': rec.id,
                'product_name': rec.name,
                'operation': 'push',
                'status': 'success' if ok else 'failed',
                'message': msg,
            })
            if ok:
                ok_count += 1
                vals = {'nisa_last_sync': now}
                if pos_id:
                    vals['external_pos_id'] = pos_id
                updates.append((rec.id, vals))
            else:
                errors.append("%s: %s" % (rec.name, msg))

        # Log ve başarılı güncellemeler ayrı cursor ile yazılır; böylece aşağıda
        # UserError fırlatılsa bile (ana işlem rollback) kaybolmaz ve bir sonraki
        # senkronda aynı ürün POS'ta mükerrer oluşturulmaz.
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            for tmpl_id, vals in updates:
                env['product.template'].browse(tmpl_id).write(vals)
            env['nisa.sync.log'].create(logs)
        self.invalidate_recordset(['external_pos_id', 'nisa_last_sync'])

        if errors:
            shown = errors[:10]
            more = len(errors) - len(shown)
            msg = self.env._(
                "%(ok)s ürün gönderildi, %(fail)s ürün başarısız:\n",
                ok=ok_count, fail=len(errors)) + "\n".join("• " + e for e in shown)
            if more > 0:
                msg += self.env._("\n… ve %s hata daha (loglara bakın).", more)
            raise UserError(msg)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._("NISA POS"),
                'message': self.env._("%s ürün POS'a başarıyla gönderildi.", ok_count),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
