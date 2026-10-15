from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _telegram_overdue_report(self):
        today = fields.Date.context_today(self)
        moves = self.search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('invoice_date_due', '<', today),
        ])
        if not moves:
            return True
        lines = [
            f'{m.name} - {m.partner_id.name} - {m.amount_residual} {m.currency_id.name}'
            for m in moves[:20]
        ]
        text = f'⚠️ Vadesi geçmiş fatura sayısı: {len(moves)}\n' + '\n'.join(lines)
        self.env['telegram.notifier']._send(text)
        return True