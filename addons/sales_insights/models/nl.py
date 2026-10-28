import re
from datetime import timedelta

from odoo import fields, models


class SalesInsightsNl(models.AbstractModel):
    _name = 'sales.insights.nl'
    _description = 'Rule-based natural language queries'

    def _days_from_text(self, text):
        text = text.lower()
        if 'bu hafta' in text or 'hafta' in text:
            return 7
        if 'geçen ay' in text or 'gecen ay' in text or 'son ay' in text:
            return 30
        if 'bu ay' in text:
            return fields.Date.today().day
        match = re.search(r'(\d+)\s*gün', text)
        if match:
            return max(1, min(365, int(match.group(1))))
        return 30

    def _ar_aging(self):
        lines = self.env['account.move.line'].sudo().search([
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('reconciled', '=', False),
        ])
        today = fields.Date.today()
        buckets = {'0_30': 0.0, '31_60': 0.0, '61_90': 0.0, '90_plus': 0.0}
        for line in lines:
            due = line.date_maturity
            if not due:
                continue
            days = (today - due).days
            val = line.amount_residual or 0.0
            if days <= 30:
                buckets['0_30'] += val
            elif days <= 60:
                buckets['31_60'] += val
            elif days <= 90:
                buckets['61_90'] += val
            else:
                buckets['90_plus'] += val
        buckets['overdue_total'] = sum(buckets.values())
        buckets['overdue_count'] = len(lines.filtered(lambda l: l.date_maturity and (today - l.date_maturity).days > 0))
        return buckets

    def query(self, text):
        """text -> {'answer': str, 'kind': str}. Kural tabanlı Türkçe NL."""
        q = (text or '').lower()
        days = self._days_from_text(q)
        since = fields.Datetime.now() - timedelta(days=days)
        Analysis = self.env['sales.analysis'].sudo()
        domain = [('date_order', '>=', since)]

        # 1. Satış/ciro/gelir
        if any(k in q for k in ('ciro', 'sat', 'gelir', 'kazan', 'satış')):
            rows = Analysis._read_group(domain, [], ['amount:sum'])
            total = rows[0][0] or 0 if rows else 0
            count = Analysis.search_count(domain)
            return {
                'answer': 'Son %d gün: <b>%s</b> ciro, <b>%d</b> sipariş.' % (
                    days, '{:,.2f}'.format(total), count),
                'kind': 'sales',
            }

        # 2. En çok müşteri
        if 'müşteri' in q or 'musteri' in q:
            top = Analysis._read_group(domain, ['partner_id'], ['amount:sum'],
                                       order='amount:sum desc', limit=3)
            if not top:
                return {'answer': 'Bu aralıkta müşteri verisi yok.', 'kind': 'customers'}
            lines = '\n'.join('• %s — %s' % (p.name or '-', '{:,.2f}'.format(v or 0))
                              for p, v in top)
            return {'answer': 'En iyi müşteriler:\n' + lines, 'kind': 'customers'}

        # 3. Ürün
        if 'ürün' in q or 'urun' in q:
            top = Analysis._read_group(domain, ['product_id'], ['qty:sum'],
                                       order='qty:sum desc', limit=3)
            if not top:
                return {'answer': 'Bu aralıkta ürün verisi yok.', 'kind': 'products'}
            lines = '\n'.join('• %s — %s adet' % (p.name or '-', '{:g}'.format(q or 0))
                              for p, q in top)
            return {'answer': 'En çok satan ürünler:\n' + lines, 'kind': 'products'}

        # 4. Ticket
        if any(k in q for k in ('ticket', 'talep', 'helpdesk')):
            if 'mini.helpdesk.ticket' not in self.env:
                return {'answer': 'mini_helpdesk kurulu değil.', 'kind': 'tickets'}
            open_count = self.env['mini.helpdesk.ticket'].sudo().search_count([
                ('stage_id.is_closed', '=', False)])
            breached = self.env['mini.helpdesk.ticket'].sudo().search_count([
                ('sla_deadline', '<', fields.Datetime.now()),
                ('stage_id.is_closed', '=', False)])
            return {'answer': 'Açık talep: <b>%d</b> · SLA ihlali: <b>%d</b>' % (
                open_count, breached), 'kind': 'tickets'}

        # 5. Stok
        if 'stok' in q:
            threshold = int(self.env['ir.config_parameter'].sudo().get_param(
                'sales_insights.stock_threshold') or 10)
            alerts = self.env['product.product'].sudo().search_count([
                ('is_storable', '=', True),
                ('free_qty', '<', threshold)])
            return {'answer': 'Eşik <b>%d</b> altında <b>%d</b> ürün var.' % (
                threshold, alerts), 'kind': 'stock'}

        # 6. Alacak/borç
        if any(k in q for k in ('alacak', 'borç', 'borc')):
            ar = self._ar_aging()
            return {'answer': (
                'Vadesi geçen alacak toplamı: <b>%s</b> (%d kalem)\n'
                '0-30 gün: %s · 31-60: %s · 61-90: %s · 90+: %s' % (
                    '{:,.2f}'.format(ar['overdue_total']),
                    ar['overdue_count'],
                    '{:,.2f}'.format(ar['0_30']),
                    '{:,.2f}'.format(ar['31_60']),
                    '{:,.2f}'.format(ar['61_90']),
                    '{:,.2f}'.format(ar['90_plus']),
                )), 'kind': 'ar_aging'}

        return {
            'answer': ('Ne sorabilirsin:\n'
                       '• "geçen ay ciro"\n'
                       '• "en çok müşteri"\n'
                       '• "en çok satan ürün"\n'
                       '• "açık talepler"\n'
                       '• "kritik stok"\n'
                       '• "vadesi geçen alacak"'),
            'kind': 'help',
        }
