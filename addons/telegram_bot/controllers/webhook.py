import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class TelegramBotWebhook(http.Controller):

    @http.route('/telegram_bot/webhook',
                type='http', auth='public', methods=['POST'], csrf=False)
    def webhook(self, **kwargs):
        secret = request.env['ir.config_parameter'].sudo().get_param(
            'telegram_bot.webhook_secret')
        sent = request.httprequest.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        if not secret or not hmac.compare_digest(secret, sent):
            return request.make_response('forbidden', status=403)
        try:
            update = request.httprequest.get_json(force=True, silent=True)
        except Exception:
            update = None
        if isinstance(update, dict):
            try:
                request.env['telegram.bot'].sudo()._handle_update(update)
            except Exception as e:
                # 200 dönmeye devam et — Telegram yeniden deneme fırtınası olmasın
                _logger.error('Telegram webhook handling failed: %s', type(e).__name__)
        return request.make_response(
            '{"ok": true}', headers={'Content-Type': 'application/json'})
