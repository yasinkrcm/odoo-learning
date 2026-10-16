from datetime import timedelta
from html import escape as e

from odoo import api, fields, models


class SalesAnalysis(models.Model):
    _name = 'sales.analysis'
    _description = 'Sales Analysis'
    _auto = False
    _order = 'date_order desc'

    order_id = fields.Many2one('sale.order', string='Order', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    user_id = fields.Many2one('res.users', string='Salesperson', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    date_order = fields.Datetime(string='Order Date', readonly=True)
    qty = fields.Float(string='Quantity', readonly=True)
    amount = fields.Float(string='Untaxed Amount', readonly=True)

    def init(self):
        self.env.cr.execute(f'DROP VIEW IF EXISTS {self._table} CASCADE')
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    l.id AS id,
                    s.id AS order_id,
                    s.partner_id AS partner_id,
                    s.user_id AS user_id,
                    s.company_id AS company_id,
                    s.date_order AS date_order,
                    l.product_id AS product_id,
                    t.categ_id AS categ_id,
                    l.product_uom_qty AS qty,
                    l.price_subtotal AS amount
                FROM sale_order_line l
                JOIN sale_order s ON s.id = l.order_id
                JOIN product_product p ON p.id = l.product_id
                JOIN product_template t ON t.id = p.product_tmpl_id
                WHERE s.state IN ('sale', 'done')
                  AND l.display_type IS NULL
            )
        """)

    @api.model
    def _telegram_weekly_summary(self):
        since = fields.Datetime.now() - timedelta(days=7)
        domain = [('date_order', '>=', since)]
        total_rows = self._read_group(domain, [], ['amount:sum'])
        total = (total_rows[0][0] if total_rows else 0) or 0
        top = self._read_group(
            domain, ['partner_id'], ['amount:sum'],
            order='amount:sum desc', limit=5,
        )
        if not top:
            return True
        lines = [
            f'{i}. {e(partner.name or "-")} — <b>{amount:,.2f}</b>'
            for i, (partner, amount) in enumerate(top, start=1)
        ]
        text = (
            '📊 <b>Haftalık Satış Özeti</b>\n'
            '━━━━━━━━━━━━━━\n'
            f'💰 Son 7 gün toplam: <b>{total:,.2f}</b>\n\n'
            '🏆 <b>En iyi müşteriler</b>\n' + '\n'.join(lines)
        )
        self.env['telegram.notifier']._send(text, parse_mode='HTML')
        return True