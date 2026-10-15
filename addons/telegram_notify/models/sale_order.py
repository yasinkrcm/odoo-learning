from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super().action_confirm()
        notifier = self.env['telegram.notifier']
        for order in self:
            notifier._send(
                f'✅ Sipariş onaylandı: {order.name}\n'
                f'Müşteri: {order.partner_id.name}\n'
                f'Tutar: {order.amount_total} {order.currency_id.name}'
            )
        return res