import base64
import logging
import threading
import time
from datetime import timedelta

import requests

import odoo
from odoo import api, fields, models
from odoo.addons.finance_ticker.controllers.main import _build_payload
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
    ('bilet', 'Yeni helpdesk ticket (adım adım sorar)'),
    ('kur', 'Dolar/Euro/Ons ve altın kurları'),
    ('sor', 'Doğal dilde sor: geçen ay ciro'),
    ('siparis', 'Son 5 sipariş/teklif (taslak onay butonu)'),
    ('stok', 'Ürün stok ve fiyat'),
    ('musteri', 'Müşteri arama'),
    ('rapor', 'Satış özeti, örn. /rapor 7'),
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

    def _download_file(self, file_id):
        """Telegram getFile ile raw byte indirir: (bytes, filename)."""
        info = self._api('getFile', {'file_id': file_id})
        file_path = (info or {}).get('result', {}).get('file_path')
        if not file_path:
            return b'', 'photo.jpg'
        token = self._icp().get_param('telegram_notify.bot_token')
        url = 'https://api.telegram.org/file/bot%s/%s' % (token, file_path)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.content, file_path.rsplit('/', 1)[-1]

    def _cmd_keyboard(self):
        """Her cevabın altına eklenen tıklanabilir kısayol menüsü."""
        return {'inline_keyboard': [
            [
                {'text': '🎫 Yeni bilet', 'callback_data': 'cmd:/bilet'},
                {'text': '📈 Rapor (7 gün)', 'callback_data': 'cmd:/rapor 7'},
            ],
            [
                {'text': '💱 Kurlar', 'callback_data': 'cmd:/kur'},
                {'text': '🤖 Sor', 'callback_data': 'cmd:/sor'},
            ],
            [
                {'text': '🧾 Son siparişler', 'callback_data': 'cmd:/siparis'},
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

    def _odoo_user_for(self, telegram_id):
        if not telegram_id:
            return self.env['res.users']
        return self.env['res.users'].sudo().search(
            [('telegram_user_id', '=', str(telegram_id))], limit=1)

    # ------------------------------------------------------------------
    # Update handling
    # ------------------------------------------------------------------

    def _handle_update(self, update):
        if update.get('callback_query'):
            return self._handle_callback(update['callback_query'])

        message = update.get('message') or {}
        chat = message.get('chat') or {}
        sender = message.get('from') or {}
        text = (message.get('text') or message.get('caption') or '').strip()
        chat_id = chat.get('id')
        photo = message.get('photo')
        document = message.get('document')
        if chat_id is None or (not text and not photo and not document):
            return False
        username = sender.get('username') or sender.get('first_name') or ''

        self = self.with_context(tg_chat_id=str(chat_id))
        mapped = self._odoo_user_for(sender.get('id'))
        if mapped:
            self = self.with_user(mapped).with_context(tg_chat_id=str(chat_id), tg_uid=mapped.id)

        if sender.get('id') not in self._allowed_ids() and not mapped:
            reply = self._deny(sender)
        elif photo or document:
            reply = self._handle_media(chat_id, message)
        else:
            parts = text.split(' ', 1)
            arg = parts[1].strip() if len(parts) > 1 else ''
            flow = self._get_flow(chat_id)
            if flow and not parts[0].startswith('/'):
                reply = self._flow_step(flow, text)
            else:
                if flow:
                    flow.unlink()
                reply = self._dispatch(self._clean_command(parts[0]), arg, chat_id)

        text_out, markup = self._send_result(reply)
        self.env['telegram.bot.log'].sudo().create({
            'chat_id': str(chat_id),
            'username': username,
            'command': text[:255],
            'reply': text_out,
        })
        return self._send_to(chat_id, text_out, reply_markup=markup)

    def _handle_media(self, chat_id, message):
        """Fotoğraf/dosyayı aktif bilet akışının attachment adımına bağlar."""
        flow = self._get_flow(chat_id)
        if not flow or flow.step != 'attachment':
            return 'ℹ️ Fotoğraf yalnızca aktif bilet akışının ek adımında eklenir.'
        photo = message.get('photo') or []
        file_id = (photo[-1] if photo else {}).get('file_id') or \
            (message.get('document') or {}).get('file_id')
        if not file_id:
            return '❌ Dosya alınamadı.'
        try:
            raw, filename = self._download_file(file_id)
        except Exception as e:
            _logger.error('Telegram file download failed: %s', type(e).__name__)
            return '❌ Dosya indirilemedi, tekrar dene.'
        flow.attachment_data = base64.b64encode(raw).decode() if raw else False
        flow.attachment_name = (message.get('caption') or '').strip()[:120] or filename
        return self._finish_flow(flow)

    def _handle_callback(self, callback_query):
        """Buton tıklamaları: callback_data 'cmd:<komut> [arg]' / 'f...:<value>' / 'so:<id>'."""
        callback_query_id = callback_query.get('id')
        self._api('answerCallbackQuery', {'callback_query_id': callback_query_id})
        sender = callback_query.get('from') or {}
        data = callback_query.get('data') or ''
        chat_id = (callback_query.get('message') or {}).get('chat', {}).get('id')
        username = sender.get('username') or sender.get('first_name') or ''

        self = self.with_context(tg_chat_id=str(chat_id))
        mapped = self._odoo_user_for(sender.get('id'))
        if mapped:
            self = self.with_user(mapped).with_context(tg_chat_id=str(chat_id), tg_uid=mapped.id)

        if sender.get('id') not in self._allowed_ids() and not mapped:
            reply = self._deny(sender)
        elif data.startswith('cmd:'):
            parts = data[4:].strip().split(' ', 1)
            arg = parts[1].strip() if len(parts) > 1 else ''
            reply = self._dispatch(self._clean_command(parts[0]), arg, chat_id)
        elif data.startswith('so:'):
            reply = self._confirm_order(chat_id, data[3:])
        elif data.startswith('f') and ':' in data:
            reply = self._flow_choice(chat_id, data)
        else:
            reply = self.cmd_yardim()

        text_out, markup = self._send_result(reply)
        self.env['telegram.bot.log'].sudo().create({
            'chat_id': str(chat_id),
            'username': username,
            'command': '[button] %s' % data[:240],
            'reply': text_out,
        })
        return self._send_to(chat_id, text_out, reply_markup=markup)

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

    def _dispatch(self, command, arg, chat_id=None):
        handler = {
            '/start': lambda a: self.cmd_yardim(),
            '/help': lambda a: self.cmd_yardim(),
            '/yardim': lambda a: self.cmd_yardim(),
            '/siparis': self.cmd_siparis,
            '/stok': self.cmd_stok,
            '/musteri': self.cmd_musteri,
            '/rapor': self.cmd_rapor,
            '/bilet': self.cmd_bilet,
            '/kur': self.cmd_kur,
            '/sor': self.cmd_sor,
        }.get(command)
        if handler is None:
            return self.cmd_yardim()
        usage = {
            '/stok': '/stok ürün adı',
            '/musteri': '/musteri müşteri adı',
            '/rapor': '/rapor [gün sayısı, örn. 7]',
        }
        if command in usage and not arg:
            return 'ℹ️ Kullanım: <code>%s</code>' % usage[command]
        return handler(arg)

    def _get_flow(self, chat_id):
        return self.env['telegram.bot.flow'].sudo().search(
            [('chat_id', '=', str(chat_id))], limit=1)

    def _send_result(self, reply):
        """(metin, anahtarlık) ikilisini metne ayrıştırır."""
        if isinstance(reply, tuple):
            return reply if len(reply) == 2 else (reply[0], None)
        return reply, self._cmd_keyboard()

    # ------------------------------------------------------------------
    # Step-by-step ticket flow (/bilet)
    # ------------------------------------------------------------------

    def _flow_keyboard(self, rows):
        return {'inline_keyboard': [[{'text': label, 'callback_data': data}
                                     for label, data in row] for row in rows]}

    def _confirm_order(self, chat_id, order_id):
        order = self.env['sale.order'].with_context(
            tg_chat_id=str(chat_id)).browse(int(order_id))
        if not order.exists():
            return '❌ Sipariş bulunamadı.'
        if order.state not in ('draft', 'sent'):
            return 'ℹ️ %s zaten onaylı/kapalı durumda.' % order.name
        order.action_confirm()
        return '✅ <b>Sipariş onaylandı</b>\n%s · %s · %0.2f %s' % (
            order.name,
            self._h(order.partner_id.name),
            order.amount_total,
            self._h(order.currency_id.symbol),
        )

    def cmd_kur(self, arg):
        try:
            items = _build_payload()
        except Exception:
            _logger.exception('cmd_kur veri alınamadı')
            return '❌ Kur verisi alınamadı, biraz sonra dene.'
        lines = ['💱 <b>Kurlar & Altın</b>']
        for it in items:
            sign = '+' if it['change'] > 0 else ''
            lines.append('%s: <b>%s</b> %s (%s%%)' % (
                self._h(it['label']),
                '{:,.2f}'.format(it['value']),
                self._h(it['currency']),
                sign + '{:,.2f}'.format(it['change']),
            ))
        return '\n'.join(lines)

    def cmd_sor(self, arg):
        if not arg:
            return 'ℹ️ Kullanım: <code>/sor geçen ay ciro</code>'
        try:
            answer = self.env['sales.insights.nl'].sudo().query(arg).get('answer')
        except Exception:
            _logger.exception('cmd_sor NL sorgu hatası')
            answer = '❌ Sorgu çalıştırılamadı.'
        return answer

    def _ask_attachment(self):
        return (
            '📎 <b>Fotoğraf</b> — dilersen tek fotoğraf/dosya gönder;\n'
            'ya da "skip" yaz / aşağıdaki butona bas.',
            {'inline_keyboard': [[{'text': '📤 Ekledim / geç', 'callback_data': 'fskip'}]]},
        )

    def cmd_bilet(self, arg):
        chat_id = self.env.context.get('tg_chat_id')
        if 'mini.helpdesk.ticket' not in self.env:
            return 'ℹ️ mini_helpdesk kurulu değil — ticket oluşturulamadı.'
        flow = self._get_flow(chat_id)
        if arg.lower() in ('iptal', 'cancel'):
            if flow:
                flow.unlink()
                return '🚫 Ticket akışı iptal edildi.'
            return 'ℹ️ Açık bilet akışı yok.'
        cancelled = ''
        if flow:
            flow.unlink()
            cancelled = '♻️ Eski akış sıfırlandı.\n'
        flow = self.env['telegram.bot.flow'].sudo().create({'chat_id': str(chat_id)})
        if arg:
            flow.title = arg[:100]
            flow.step = 'partner'
            return cancelled + self._ask_partner_name(flow)
        flow.step = 'title'
        return cancelled + (
            '🎫 <b>Bilet başlığı</b> — başlığı tek mesaj olarak yaz.\n'
            'Vazgeç: "iptal"')

    def _ask_partner_name(self, flow):
        return (
            '🏢 <b>Müşteri</b> — müşteri adını yaz, eşleşenleri butonlarla sunayım.',
            {'inline_keyboard': [[{'text': '🚫 Müşteri olmadan devam',
                                   'callback_data': 'fskip'}]]},
        )

    def _ask_priority(self):
        return (
            '🎯 <b>Öncelik</b> seç:',
            self._flow_keyboard([
                [('🟢 Düşük', 'fprio:0'), ('🔵 Normal', 'fprio:1')],
                [('🟠 Yüksek', 'fprio:2'), ('🔴 Acil', 'fprio:3')],
            ]),
        )

    def _ask_assignee(self):
        # Odoo 19: res.groups.users kaldırıldı — res.users.all_group_ids üzerinden
        users = self.env['res.users'].sudo().search(
            [('all_group_ids', 'in', self.env.ref('base.group_user').id)],
            limit=8, order='id')
        rows = [[u.name, 'fuser:%d' % u.id] for u in users]
        chunked = [rows[i:i + 2] for i in range(0, len(rows), 2)]
        chunked.append([('🚫 Atama olmadan devam', 'fskip')])
        return ('👤 <b>Atanacak kişi</b> seç:',
                self._flow_keyboard(chunked))

    def _ask_description(self):
        return (
            '📝 <b>Açıklama</b> — tek mesaj yaz veya "skip" gönder. Vazgeç: "iptal".',
        )

    def _flow_step(self, flow, text):
        """Metin cevabını aktif adım işler."""
        if text.lower() in ('iptal', 'cancel'):
            flow.unlink()
            return '🚫 Ticket akışı iptal edildi.'
        step = flow.step
        if step == 'title':
            flow.title = text[:100]
            flow.step = 'partner'
            return self._ask_partner_name(flow)
        if step == 'partner':
            partners = self.env['res.partner'].sudo().search(
                [('name', 'ilike', text)], limit=6)
            if not partners:
                return ('❌ "%s" bulunamadı. Tekrar müşteri adı yaz veya "iptal".' %
                        self._h(text))
            if len(partners) == 1:
                flow.partner_id = partners[0]
                flow.step = 'priority'
                return self._ask_priority()
            rows = [[p.name or '-', 'fpart:%d' % p.id] for p in partners]
            rows.append(['🚫 Müşteri olmadan devam', 'fskip'])
            return (
                '🏢 <b>Müşteri</b> — eşleşenler, birini seç ya da adı düzelt:',
                self._flow_keyboard([rows[i:i + 2] for i in range(0, len(rows), 2)]),
            )
        if step == 'description':
            flow.description = '' if text.lower() == 'skip' else text
            flow.step = 'attachment'
            return self._ask_attachment()
        if step == 'attachment':
            if text.lower() == 'skip':
                return self._finish_flow(flow)
            return self._ask_attachment()
        flow.unlink()
        return '🚫 Ticket akışı sıfırlandı.'

    def _flow_choice(self, chat_id, data):
        """Buton cevaplarını aktif adım işler: fpart/id, fprio/kod, fuser/id, fskip."""
        flow = self._get_flow(chat_id)
        if not flow:
            return 'ℹ️ Bilet akışı yok. <code>/bilet</code> ile başla.'
        if flow.step in ('title', 'description'):
            return 'ℹ️ Bu adımda buton yok — yazı bekleniyor.'
        prefix, _, value = data.partition(':')
        if prefix == 'fpart':
            flow.partner_id = int(value)
            flow.step = 'priority'
            return self._ask_priority()
        if prefix == 'fprio':
            flow.priority = value
            flow.step = 'assignee'
            return self._ask_assignee()
        if prefix == 'fuser':
            flow.user_id = int(value)
            flow.step = 'description'
            return self._ask_description()
        if prefix == 'fskip':
            if flow.step == 'partner':
                flow.step = 'priority'
                return self._ask_priority()
            if flow.step == 'assignee':
                flow.step = 'description'
                return self._ask_description()
            if flow.step == 'attachment':
                return self._finish_flow(flow)
            flow.unlink()
            return '🚫 Ticket akışı iptal edildi.'
        return self.cmd_yardim()

    def _finish_flow(self, flow):
        vals = {'name': flow.title or ''}
        if flow.partner_id:
            vals['partner_id'] = flow.partner_id.id
        vals['priority'] = flow.priority or '1'
        if flow.user_id:
            vals['user_id'] = flow.user_id.id
        if flow.description:
            vals['description'] = '<p>%s</p>' % self._h(flow.description)
        customer = flow.partner_id.name
        assignee = flow.user_id.name
        attachment_name = flow.attachment_name or 'photo.jpg'
        attachment_data = flow.attachment_data
        flow.unlink()
        ticket = self.env['mini.helpdesk.ticket'].sudo().create(vals)
        if attachment_data:
            ticket.message_post(
                body='📎 Telegram ek dosyası',
                attachments=[(attachment_name, attachment_data)])
        return '✅ <b>Ticket oluşturuldu</b>\n%s — %s\n🏢 %s · 👤 %s · 🎯 %s' % (
            self._h(ticket.number),
            self._h(ticket.name),
            self._h(customer or '—'),
            self._h(assignee or '—'),
            '🟢 Düşük' if vals['priority'] == '0' else
            '🔵 Normal' if vals['priority'] == '1' else
            '🟠 Yüksek' if vals['priority'] == '2' else '🔴 Acil',
        )

    def cmd_yardim(self):
        return (
            '🤖 <b>Komutlar</b>\n'
            '/bilet [başlık] — adım adım ticket: başlık, müşteri, öncelik, atama, açıklama\n'
            '/siparis [müşteri] — son 5 onaylı sipariş\n'
            '/stok ürün adı — stok ve fiyat\n'
            '/musteri müşteri adı — müşteri arama\n'
            '/rapor [gün] — satış özeti (varsayılan 7)\n'
            'Akışı her zaman "iptal" ile bozabilirsin.'
        )

    def cmd_siparis(self, arg):
        SaleOrder = self.env['sale.order'].sudo()
        domain = [('state', '!=', 'cancel')]
        if arg:
            partner = self.env['res.partner'].sudo().search(
                [('name', 'ilike', arg)], limit=1)
            if not partner:
                return '❌ "%s" adında müşteri bulunamadı.' % self._h(arg)
            domain.append(('partner_id', '=', partner.id))
        orders = SaleOrder.search(domain, order='date_order desc, id desc', limit=5)
        if not orders:
            return '📭 Sipariş/teklif bulunamadı.'
        lines = ['🧾 <b>Son %d sipariş/teklif</b>' % len(orders)]
        confirm_rows = []
        for o in orders:
            date = o.date_order and o.date_order.strftime('%d.%m.%Y') or ''
            state_label = dict(SaleOrder._fields['state'].selection).get(o.state, o.state)
            lines.append('%s · %s · %s — %s · %0.2f %s' % (
                o.name,
                self._h(o.partner_id.name),
                self._h(state_label),
                date,
                o.amount_total,
                self._h(o.currency_id.symbol),
            ))
            if o.state in ('draft', 'sent'):
                confirm_rows.append([('✅ Onayla %s' % o.name, 'so:%d' % o.id)])
        if confirm_rows:
            return ('\n'.join(lines), {'inline_keyboard': confirm_rows})
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
