import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class Todo(models.Model):
    _name = 'my.todo'
    _description = 'Todo Item'

    name = fields.Char(string='Title', required=True)
    description = fields.Text(string='Description')
    is_done = fields.Boolean(string='Done', default=False)
    deadline = fields.Date(string='Deadline')
    user_id = fields.Many2one('res.users', string='Assigned To', default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', string='Related Customer')
    partner_is_vip = fields.Boolean(related='partner_id.is_vip', string='VIP Customer')

    partner_country = fields.Char(string='Customer Country', compute='_compute_partner_country', store=True)

    @api.depends('partner_id.country_id.name')
    def _compute_partner_country(self):
        for rec in self:
            rec.partner_country = rec.partner_id.country_id.name or ''

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id and self.partner_id.is_vip:
            self.description = (self.description or '') + '\n[VIP customer, prioritize this]'

    def action_mark_done(self):
        for rec in self:
            rec.is_done = True
        return True

    def action_log_partner_note_as_admin(self):
        for rec in self:
            if rec.partner_id:
                rec.partner_id.sudo().write({'comment': f'Todo linked: {rec.name}'})
        return True

    def action_notify_external(self):
        import requests
        for rec in self:
            try:
                requests.post(
                    'https://httpbin.org/post',
                    json={'todo': rec.name, 'is_done': rec.is_done},
                    timeout=5,
                )
            except Exception:
                _logger.warning('External notify failed for todo %s', rec.id)
        return True