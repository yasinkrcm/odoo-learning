import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class NisaMockPos(http.Controller):
    """Gerçek POS API'si hazır olana kadar kullanılan sahte endpoint.

    `nisa_pos_sync.mock_enabled` = '1' iken çalışır; canlıda '0' yapın
    (veya bu dosyayı kaldırın). Düz JSON body kabul eder (requests.post(json=...)).
    """

    @http.route('/nisa_pos_sync/mock/products', type='http', auth='public',
                methods=['POST'], csrf=False)
    def mock_products(self, **kwargs):
        icp = request.env['ir.config_parameter'].sudo()
        if icp.get_param('nisa_pos_sync.mock_enabled') != '1':
            return request.not_found()

        try:
            data = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except ValueError:
            return request.make_json_response({'error': 'geçersiz JSON'}, status=400)
        if not isinstance(data, dict):
            return request.make_json_response({'error': 'JSON nesnesi bekleniyor'}, status=400)

        missing = [k for k in ('barcode', 'name', 'price', 'stock') if k not in data]
        if missing:
            return request.make_json_response(
                {'error': 'eksik alanlar: %s' % ', '.join(missing)}, status=400)
        try:
            if int(data['stock']) < 0:
                return request.make_json_response({'error': 'stock negatif olamaz'}, status=422)
        except (TypeError, ValueError):
            return request.make_json_response({'error': 'stock sayı olmalı'}, status=400)

        _logger.info("MOCK POS aldı: %s", data)
        return request.make_json_response({'id': 'MOCK-%s' % data['barcode'], 'status': 'ok'})
