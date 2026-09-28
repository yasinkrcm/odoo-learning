from odoo import models, fields


class Todo(models.Model):
    _name = 'my.todo'
    _description = 'Todo Item'

    name = fields.Char(string='Title', required=True)
    description = fields.Text(string='Description')
    is_done = fields.Boolean(string='Done', default=False)
    deadline = fields.Date(string='Deadline')
    user_id = fields.Many2one('res.users', string='Assigned To')
    partner_id = fields.Many2one('res.partner', string='Related Customer')
    partner_is_vip = fields.Boolean(related='partner_id.is_vip', string='VIP Customer')

    def action_mark_done(self):
        for rec in self:
            rec.is_done = True
        return True