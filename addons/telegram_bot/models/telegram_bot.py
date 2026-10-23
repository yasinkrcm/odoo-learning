import logging
import threading
import time
from datetime import timedelta

import requests

import odoo
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.modules.registry import Registry
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)

API_URL = 'https://api.telegram.org/bot%s/%s'
_REBUILD_DELAY = 5  # long-poll hata sonrası yeniden deneme süresi


class ExitLongPoll(Exception):
    """Webhook kayıt edildi — polling thread'i sessizce sonlanır."""


def _long_poll_loop(db_name):
    """Daemon thread gövdesi: her turda taze cursor ile getUpdates çeker."""
    while True:
        try:
            with Registry(db_name).cursor() as cr:
                env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
                env['telegram.bot']._poll_updates_long()
                cr.commit()
        except ExitLongPoll:
            _logger.info('Telegram long-poll stopped (webhook active)')
            return
        except Exception:
            _logger.exception('Telegram long poll loop error')
            time.sleep(_REBUILD_DELAY)


_POLL_THREAD = None  # proses başına tek long-poll thread

# Telegram "//" menüsünde görünecek yardımcı komutlar (setMyCommands)
BOT_COMMANDS = [
    ('siparis', 'Son 5 onaylı sipariş'),
    ('stok', 'Ürün stok ve fiyat'),
    ('musteri', 'Müşteri arama'),
    ('rapor', 'Satış özeti, örn. /rapor 7'),
    ('bilet', 'Helpdesk ticket oluştur'),
    ('yardim', 'Komut listesi'),
]


class TelegramBot(models.AbstractModel):
    _name = 'telegram.bot'
    _description = 'Telegram Bot (two-way dispatch)'

    # ------------------------------------------------------------------
    # Telegram API helpers (token shared with telegram_notify)
    # ------------------------------------------------------------------

    def _icp(self):
        return self.env['ir.config_parameter'].sudo()

    def _api(self, method, payload=None, timeout=10):
        token = self._icp().get_param('telegram_notify.bot_token')
        if not token:
            _logger.warning('Telegram is not configured (bot_token missing)')
            return None
        try:
            resp = requests.post(
                API_URL % (token, method),
                json=payload or {},
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            # error strings contain the URL (and the token) — log type only
            _logger.error('Telegram API %s failed: %s', method, type(e).__name__)
            return None

    def _send_to(self, chat_id, text, parse_mode='HTML', reply_markup=None):
        if not chat_id or not text:
            return False
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True,
        }
        if reply_markup:
            payload['reply_markup'] = reply_markup
        resp = self._api('sendMessage', payload)
        return bool(resp and resp.get('ok'))

    def _cmd_keyboard(self):
        """Her cevabın altına eklenen tıklanabilir kısayol menüsü."""
        return {'inline_keyboard': [
            [
                {'text': '🧾 Son siparişler', 'callback_data': 'cmd:/siparis'},
                {'text': '📈 Rapor (7 gün)', 'callback_data': 'cmd:/rapor 7'},
            ],
            [
                {'text': '👥 Müşteri ara', 'callback_data': 'cmd:/musteri'},
                {'text': '📦 Stok ara', 'callback_data': 'cmd:/stok'},
            ],
        ]}

    def _register_commands(self):
        """Yazım menüsünde '/', komut önerilerini kaydet (bir kez)."""
        icp = self._icp()
        if icp.get_param('telegram_bot.commands_registered'):
            return True
        resp = self._api('setMyCommands', {
            'commands': [
                {'command': command, 'description': description}
                for command, description in BOT_COMMANDS
            ]
        })
        if resp and resp.get('ok'):
            icp.set_param('telegram_bot.commands_registered', '1')
        return True

    @staticmethod
    def _h(text):
        return html_escape(text or '')

    # ------------------------------------------------------------------
    # Access control: comma-separated telegram user ids in ICP
    # ------------------------------------------------------------------

    def _allowed_ids(self):
        raw = self._icp().get_param('telegram_bot.allowed_telegram_ids') or ''
        return {int(x) for x in raw.replace(' ', '').split(',') if x.strip().isdigit()}

    # ------------------------------------------------------------------
    # Update handling
    # ------------------------------------------------------------------

    def _handle_update(self, update):
        if update.get('callback_query'):
            return self._handle_callback(update['callback_query'])

        message = update.get('message') or {}
        chat = message.get('chat') or {}
        sender = message.get('from') or {}
        text = (message.get('text') or '').strip()
        chat_id = chat.get('id')
        if not text or chat_id is None:
            return False
        username = sender.get('username') or sender.get('first_name') or ''

        if sender.get('id') not in self._allowed_ids():
            reply = self._deny(sender)
        else:
            parts = text.split(' ', 1)
            arg = parts[1].strip() if len(parts) > 1 else ''
            reply = self._dispatch(self._clean_command(parts[0]), arg)

        self.env['telegram.bot.log'].sudo().create({
            'chat_id': str(chat_id),
            'username': username,
            'command': text[:255],
            'reply': reply,
        })
        return self._send_to(chat_id, reply, reply_markup=self._cmd_keyboard())

    def _handle_callback(self, callback_query):
        """Buton tıklamaları: callback_data 'cmd:<komut> [arg]'."""
        callback_query_id = callback_query.get('id')
        self._api('answerCallbackQuery', {'callback_query_id': callback_query_id})
        sender = callback_query.get('from') or {}
        data = callback_query.get('data') or ''
        chat_id = (callback_query.get('message') or {}).get('chat', {}).get('id')
        username = sender.get('username') or sender.get('first_name') or ''

        if sender.get('id') not in self._allowed_ids():
            reply = self._deny(sender)
        elif data.startswith('cmd:'):
            parts = data[4:].strip().split(' ', 1)
            arg = parts[1].strip() if len(parts) > 1 else ''
            reply = self._dispatch(self._clean_command(parts[0]), arg)
        else:
            reply = self.cmd_yardim()

        self.env['telegram.bot.log'].sudo().create({
            'chat_id': str(chat_id),
            'username': username,
            'command': '[button] %s' % data[:240],
            'reply': reply,
        })
        return self._send_to(chat_id, reply, reply_markup=self._cmd_keyboard())

    def _deny(self, sender):
        return (
            '⛔ Bu bot sadece kayıtlı kullanıcılara açıktır.\n'
            'Telegram id: <code>%s</code>' % self._h(sender.get('id'))
        )

    def _clean_command(self, raw):
        """'/bilet@BotAdi' formunu da ele alan güvenli normalize.

        strip karakter-kümesi '/'ü de kestiği için slah korunuyor.
        """
        command = (raw or '').strip().lower()
        if '@' in command:
            command = command.split('@', 1)[0]
        if not command.startswith('/'):
            command = '/' + command
        return command

    def _dispatch(self, command, arg):
        handler = {
            '/start': lambda a: self.cmd_yardim(),
            '/help': lambda a: self.cmd_yardim(),
            '/yardim': lambda a: self.cmd_yardim(),
            '/siparis': self.cmd_siparis,
            '/stok': self.cmd_stok,
            '/musteri': self.cmd_musteri,
            '/rapor': self.cmd_rapor,
            '/bilet': self.cmd_bilet,
        }.get(command)
        if handler is None:
            return self.cmd_yardim()
        usage = {
            '/stok': '/stok ürün adı',
            '/musteri': '/musteri müşteri adı',
            '/rapor': '/rapor [gün sayısı, örn. 7]',
            '/bilet': '/bilet başlık',
        }
        if command in usage and not arg:
            return 'ℹ️ Kullanım: <code>%s</code>' % usage[command]
        return handler(arg)

    def cmd_yardim(self):
        return (
            '🤖 <b>Komutlar</b>\n'
            '/siparis [müşteri] — son 5 onaylı sipariş\n'
            '/stok ürün adı — stok ve fiyat\n'
            '/musteri müşteri adı — müşteri arama\n'
            '/rapor [gün] — satış özeti (varsayılan 7)\n'
            '/bilet başlık — helpdesk ticket oluştur'
        )

    def cmd_siparis(self, arg):
        SaleOrder = self.env['sale.order'].sudo()
        domain = [('state', 'in', ('sale', 'done'))]
        if arg:
            partner = self.env['res.partner'].sudo().search(
                [('name', 'ilike', arg)], limit=1)
            if not partner:
                return '❌ "%s" adında müşteri bulunamadı.' % self._h(arg)
            domain.append(('partner_id', '=', partner.id))
        orders = SaleOrder.search(domain, order='date_order desc, id desc', limit=5)
        if not orders:
            return '📭 Onaylı sipariş bulunamadı.'
        lines = ['🧾 <b>Son %d onaylı sipariş</b>' % len(orders)]
        for o in orders:
            date = o.date_order and o.date_order.strftime('%d.%m.%Y') or ''
            lines.append('%s — %s · %0.2f %s · %s' % (
                o.name,
                self._h(o.partner_id.name),
                o.amount_total,
                self._h(o.currency_id.symbol),
                date,
            ))
        return '\n'.join(lines)

    def cmd_stok(self, arg):
        products = self.env['product.product'].sudo().search(
            ['|', ('display_name', 'ilike', arg), ('default_code', 'ilike', arg)],
            limit=5,
        )
        if not products:
            return '❌ "%s" için ürün bulunamadı.' % self._h(arg)
        lines = ['📦 <b>Stok — "%s"</b>' % self._h(arg)]
        for p in products:
            lines.append('%s — %s adet · %s %s' % (
                self._h(p.display_name),
                '{:g}'.format(p.free_qty or 0),
                '{:,.2f}'.format(p.list_price or 0),
                self._h(p.currency_id.name),
            ))
        return '\n'.join(lines)

    def cmd_musteri(self, arg):
        partners = self.env['res.partner'].sudo().search(
            [('name', 'ilike', arg)], limit=5)
        if not partners:
            return '❌ "%s" için müşteri bulunamadı.' % self._h(arg)
        lines = ['👥 <b>Müşteriler — "%s"</b>' % self._h(arg)]
        for p in partners:
            extra = ['📧 %s' % self._h(p.email)] if p.email else []
            if p.customer_rank:
                extra.append('🏙️ şirket müşterisi')
            lines.append('%s%s' % (self._h(p.name), ('\n   ' + '\n   '.join(extra)) if extra else ''))
        return '\n'.join(lines)

    def cmd_rapor(self, arg):
        try:
            days = max(1, min(90, int(arg))) if arg else 7
        except ValueError:
            return 'ℹ️ Kullanım: <code>/rapor [gün sayısı]</code>'
        from_dt = fields.Datetime.now() - timedelta(days=days)
        SaleOrder = self.env['sale.order'].sudo()
        domain = [('state', 'in', ('sale', 'done')), ('date_order', '>=', from_dt)]

        agg = SaleOrder._read_group(domain, [], ['amount_total:sum'])
        total = agg[0][0] or 0.0 if agg else 0.0
        count = SaleOrder.search_count(domain)
        lines = [
            '📈 <b>Satış Özeti — son %d gün</b>' % days,
            '🧾 Sipariş: <b>%d</b>' % count,
        ]
        sample = SaleOrder.search(domain, limit=1)
        lines.append('💰 Toplam: <b>%s %s</b>' % (
            '{:,.2f}'.format(total),
            self._h(sample.currency_id and sample.currency_id.name or 'TRY'),
        ))
        top = SaleOrder._read_group(
            domain, ['partner_id'], ['amount_total:sum'],
            order='amount_total:sum desc', limit=3,
        )
        if top:
            lines.append('🏆 <b>En iyi müşteriler</b>')
            for partner_record, amount in top:
                lines.append('   • %s — %s' % (
                    self._h(partner_record.name),
                    '{:,.2f}'.format(amount or 0),
                ))
        if 'mini.helpdesk.ticket' in self.env:
            breached = self.env['mini.helpdesk.ticket'].sudo().search_count([
                ('sla_deadline', '<', fields.Datetime.now()),
                ('stage_id.is_closed', '=', False),
                ('sla_notified', '=', False),
            ])
            lines.append('⏰ Yeni SLA ihlali: <b>%d</b>' % breached)
        return '\n'.join(lines)

    def cmd_bilet(self, arg):
        if 'mini.helpdesk.ticket' not in self.env:
            return 'ℹ️ mini_helpdesk kurulu değil — ticket oluşturulamadı.'
        ticket = self.env['mini.helpdesk.ticket'].sudo().create({'name': arg[:100]})
        return '✅ <b>Ticket oluşturuldu</b>\n%s — %s' % (
            self._h(ticket.number),
            self._h(ticket.name),
        )

    # ------------------------------------------------------------------
    # Polling: daemon long-poll thread + 1-min cron watchdog
    # ------------------------------------------------------------------

    def _poll_updates(self):
        """Cron hedefi — watchdog: long-poll thread'i ayakta tutar."""
        icp = self._icp()
        if icp.get_param('telegram_bot.webhook_url'):
            return True  # webhook aktif — polling çakışmasın
        self._register_commands()
        self._ensure_long_poll(self.env.cr.dbname)
        return True

    def _ensure_long_poll(self, db_name):
        global _POLL_THREAD
        if _POLL_THREAD is not None and _POLL_THREAD.is_alive():
            return True
        _POLL_THREAD = threading.Thread(
            target=_long_poll_loop, args=(db_name, ), daemon=True,
            name='telegram-bot-longpoll')
        _POLL_THREAD.start()
        _logger.info('Telegram long-poll thread started')
        return True

    def _poll_updates_long(self):
        """Thread içinde çalışır: 50 sn uzun beklemeli getUpdates çeker."""
        icp = self._icp()
        if icp.get_param('telegram_bot.webhook_url'):
            raise ExitLongPoll()  # webhook'a geçildi — thread'i bitir
        self._register_commands()
        offset = 0
        try:
            offset = int(icp.get_param('telegram_bot.poll_offset') or 0)
        except ValueError:
            pass
        resp = self._api('getUpdates', {
            'offset': offset,
            'timeout': 50,
            'limit': 20,
            'allowed_updates': ['message', 'callback_query'],
        }, timeout=60)  # sunucu 50sn bekliyor — client daha uzun dayansın
        updates = (resp or {}).get('result') or []
        for update in updates:
            try:
                self._handle_update(update)
            except Exception as e:
                _logger.error('Telegram update handling failed: %s', type(e).__name__)
        if updates:
            icp.set_param('telegram_bot.poll_offset', updates[-1]['update_id'] + 1)
        return True

    def _register_webhook(self, base_url, secret):
        if not base_url or not secret:
            raise UserError('base_url ve secret zorunludur.')
        self._register_commands()
        url = base_url.rstrip('/') + '/telegram_bot/webhook'
        resp = self._api('setWebhook', {
            'url': url,
            'secret_token': secret,
            'allowed_updates': ['message', 'callback_query'],
        })
        if not (resp and resp.get('ok')):
            raise UserError('setWebhook çağrısı başarısız oldu (loglara bakın).')
        self._icp().set_param('telegram_bot.webhook_url', url)
        return url
