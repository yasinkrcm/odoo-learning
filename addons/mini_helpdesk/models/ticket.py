from datetime import timedelta
from html import escape as e
from odoo import _, api, fields, models

SLA_HOURS = {'0': 72, '1': 48, '2': 24, '3': 4}

PRIORITY_UI = {
    '0': ('🟢', 'Düşük'),
    '1': ('🔵', 'Normal'),
    '2': ('🟠', 'Yüksek'),
    '3': ('🔴', 'Acil'),
}


class HelpdeskTicket(models.Model):
    _name = 'mini.helpdesk.ticket'
    _description = 'Helpdesk Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, id desc'

    number = fields.Char(readonly=True, copy=False)
    name = fields.Char(string='Subject', required=True, tracking=True)
    description = fields.Html()
    partner_id = fields.Many2one('res.partner', string='Customer', tracking=True)
    user_id = fields.Many2one('res.users', string='Assigned To', tracking=True)
    priority = fields.Selection(
        [('0', 'Low'), ('1', 'Normal'), ('2', 'High'), ('3', 'Urgent')],
        default='1', tracking=True,
    )
    stage_id = fields.Many2one(
        'mini.helpdesk.stage', string='Stage', tracking=True, index=True, copy=False,
        default=lambda self: self.env['mini.helpdesk.stage'].search([], limit=1),
        group_expand='_read_group_stage_ids',
    )
    sla_deadline = fields.Datetime(
        string='SLA Deadline', compute='_compute_sla_deadline',
        store=True, readonly=False,
    )
    is_sla_breached = fields.Boolean(compute='_compute_is_sla_breached')
    sla_notified = fields.Boolean(copy=False)

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        return stages.search([], order=stages._order)

    @api.depends('create_date', 'priority')
    def _compute_sla_deadline(self):
        for rec in self:
            base = rec.create_date or fields.Datetime.now()
            rec.sla_deadline = base + timedelta(hours=SLA_HOURS.get(rec.priority, 48))

    @api.depends('sla_deadline', 'stage_id.is_closed')
    def _compute_is_sla_breached(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_sla_breached = bool(
                rec.sla_deadline and rec.sla_deadline < now and not rec.stage_id.is_closed
            )

    def _priority_label(self):
        self.ensure_one()
        emoji, label = PRIORITY_UI.get(self.priority, ('', ''))
        return f'{emoji} {label}'.strip()

    def _notify_telegram(self, title, lines):
        self.ensure_one()
        text = (
            f'{title} · <code>{e(self.number or "")}</code>\n'
            f'━━━━━━━━━━━━━━\n'
            f'📌 <b>{e(self.name or "")}</b>\n'
            + '\n'.join(lines)
        )
        self.env['telegram.notifier']._send(text, parse_mode='HTML')

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('number'):
                vals['number'] = seq.next_by_code('mini.helpdesk.ticket') or 'New'
        records = super().create(vals_list)
        for ticket in records:
            ticket._notify_telegram('🆕 <b>Yeni Talep</b>', [
                f'🏢 Müşteri: {e(ticket.partner_id.name or "-")}',
                f'🎯 Öncelik: {e(ticket._priority_label())}',
                f'👤 Atanan: {e(ticket.user_id.name or "-")}',
            ])
        return records

    def write(self, vals):
        watched = {'stage_id', 'user_id', 'priority'}
        old = {}
        if watched & set(vals):
            old = {
                t.id: (t.stage_id.display_name, t.user_id.name, t._priority_label())
                for t in self
            }
        res = super().write(vals)
        for ticket in self:
            if ticket.id not in old:
                continue
            old_stage, old_user, old_prio = old[ticket.id]
            if 'stage_id' in vals and old_stage != ticket.stage_id.display_name:
                title = (
                    '✅ <b>Talep Çözüldü</b>' if ticket.stage_id.is_closed
                    else '🔄 <b>Aşama Değişti</b>'
                )
                ticket._notify_telegram(title, [
                    f'📍 {e(old_stage or "-")} ➜ <b>{e(ticket.stage_id.display_name)}</b>',
                    f'👤 Atanan: {e(ticket.user_id.name or "-")}',
                ])
            if 'user_id' in vals and old_user != ticket.user_id.name:
                ticket._notify_telegram('👤 <b>Atama Değişti</b>', [
                    f'{e(old_user or "-")} ➜ <b>{e(ticket.user_id.name or "-")}</b>',
                ])
            if 'priority' in vals and old_prio != ticket._priority_label():
                ticket._notify_telegram('⚡ <b>Öncelik Değişti</b>', [
                    f'{e(old_prio)} ➜ <b>{e(ticket._priority_label())}</b>',
                ])
        return res
    @api.model
    def _cron_sla_check(self):
        now = fields.Datetime.now()
        tickets = self.search([
            ('sla_deadline', '<', now),
            ('stage_id.is_closed', '=', False),
            ('sla_notified', '=', False),
        ])
        for ticket in tickets:
            assignee = ticket.user_id or ticket.create_uid
            ticket.message_post(
                body=_('SLA breached for ticket %s', ticket.number),
                subtype_xmlid='mail.mt_comment',
                partner_ids=assignee.partner_id.ids,
            )
            ticket.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=assignee.id,
                summary=_('SLA breached: %s', ticket.number),
            )
            ticket._notify_telegram('🚨 <b>SLA Aşıldı</b>', [
                f'👤 Atanan: {e(assignee.name)}',
                f'⏰ Bitiş: {fields.Datetime.to_string(ticket.sla_deadline)} UTC',
            ])
            ticket.sla_notified = True
        return True