from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_vip = fields.Boolean(string='VIP Customer')
    vip_notes = fields.Text(string='VIP Notes')

