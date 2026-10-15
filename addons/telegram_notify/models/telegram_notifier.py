import logging

import requests

from odoo import api, models

_logger = logging.getLogger(__name__)


class TelegramNotifier(models.AbstractModel):
    _name = 'telegram.notifier'
    _description = 'Telegram Notifier'

    @api.model
    def _send(self, text):
        icp = self.env['ir.config_parameter'].sudo()
        token = icp.get_param('telegram_notify.bot_token')
        chat_id = icp.get_param('telegram_notify.chat_id')
        if not token or not chat_id:
            _logger.warning('Telegram is not configured (bot_token / chat_id missing)')
            return False
        try:
            resp = requests.post(
                f'https://api.telegram.org/bot{token}/sendMessage',
                json={'chat_id': chat_id, 'text': text},
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            # exception message contains the URL (and token), so log only the type
            _logger.error('Telegram send failed: %s', type(e).__name__)
            return False