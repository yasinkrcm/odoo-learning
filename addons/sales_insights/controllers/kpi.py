import hmac
from datetime import timedelta

from odoo import fields, http
from odoo.http import request


class SalesInsightsKpi(http.Controller):

    def _check_key(self, provided):
        secret = request.env['ir.config_parameter'].sudo().get_param(
            'sales_insights.api_key')
        if not secret or not provided:
            return False
        return hmac.compare_digest(provided, secret)

    @http.route('/sales_insights/kpi', type='http', auth='public',
                methods=['GET', 'POST'], csrf=False, cors='*')
    def kpi(self, **kw):
        if not self._check_key(kw.get('api_key')):
            return request.make_json_response(
                {'error': 'invalid api_key'}, status=403)

        try:
            days = max(1, min(365, int(kw.get('days') or 30)))
        except (TypeError, ValueError):
            days = 30

        env = request.env['sales.analysis'].sudo()
        now = fields.Datetime.now()
        since = now - timedelta(days=days)
        prev_since = since - timedelta(days=days)
        domain = [('date_order', '>=', since)]

        rows = env._read_group(domain, [], ['amount:sum', 'order_id:count_distinct', 'qty:sum'])
        amount_total = rows and rows[0][0] or 0
        order_count = rows and rows[0][1] or 0
        qty_total = rows and rows[0][2] or 0

        prev_rows = env._read_group(
            [('date_order', '>=', prev_since), ('date_order', '<', since)],
            [], ['amount:sum'])
        prev_amount = prev_rows and prev_rows[0][0] or 0

        daily = [
            {'date': d.strftime('%Y-%m-%d'), 'amount': float(v or 0)}
            for d, v in env._read_group(domain, ['date_order:day'], ['amount:sum'])
        ]
        daily.sort(key=lambda x: x['date'])
        top_customers = [
            {'name': c.name or '-', 'amount': float(v or 0)}
            for c, v in env._read_group(domain, ['partner_id'], ['amount:sum'])
        ]
        top_customers.sort(key=lambda x: -x['amount'])
        top_customers = top_customers[:5]
        top_products = [
            {'name': p.name or '-', 'qty': float(q or 0), 'amount': float(v or 0)}
            for p, q, v in env._read_group(domain, ['product_id'], ['qty:sum', 'amount:sum'])
        ]
        top_products.sort(key=lambda x: -x['qty'])
        top_products = top_products[:5]

        breached = 0
        if 'mini.helpdesk.ticket' in request.env:
            breached = request.env['mini.helpdesk.ticket'].sudo().search_count([
                ('sla_deadline', '<', fields.Datetime.now()),
                ('stage_id.is_closed', '=', False)])

        company = request.env.company
        return request.make_json_response({
            'generated_at': now.strftime('%Y-%m-%d %H:%M:%S'),
            'company': company.name,
            'currency': company.currency_id.name,
            'days': days,
            'kpi': {
                'amount_total': float(amount_total or 0),
                'prev_amount_total': float(prev_amount or 0),
                'order_count': order_count,
                'qty_total': float(qty_total or 0),
                'avg_order': float(amount_total / order_count) if order_count else 0,
            },
            'daily': daily,
            'top_customers': top_customers,
            'top_products': top_products,
            'helpdesk': {'sla_breached': breached},
        })

