from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_priority = fields.Selection(
        [('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')],
        string='Priority', default='normal')
    x_internal_note = fields.Text(string='Internal Note')

    def action_set_urgent(self):
        for order in self:
            order.x_priority = 'urgent'
        return True
