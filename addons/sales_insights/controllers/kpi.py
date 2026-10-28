import hmac
from datetime import timedelta

from odoo import fields, http
from odoo.addons.finance_ticker.controllers.main import _cached_payload
from odoo.http import request


class SalesInsightsKpi(http.Controller):

    def _check_key(self, provided):
        secret = request.env['ir.config_parameter'].sudo().get_param(
            'sales_insights.api_key')
        if not secret or not provided:
            return False
        return hmac.compare_digest(provided, secret)

    def _ar_aging(self):
        lines = request.env['account.move.line'].sudo().search([
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
        buckets['overdue_count'] = len(lines.filtered(
            lambda l: l.date_maturity and (today - l.date_maturity).days > 0))
        return buckets

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
        open_tickets = 0
        if 'mini.helpdesk.ticket' in request.env:
            Helpdesk = request.env['mini.helpdesk.ticket'].sudo()
            open_tickets = Helpdesk.search_count([('stage_id.is_closed', '=', False)])
            breached = Helpdesk.search_count([
                ('sla_deadline', '<', fields.Datetime.now()),
                ('stage_id.is_closed', '=', False)])

        threshold = int(request.env['ir.config_parameter'].sudo().get_param(
            'sales_insights.stock_threshold') or 10)
        stock_alerts = request.env['product.product'].sudo().search_count([
            ('is_storable', '=', True),
            ('free_qty', '<', threshold),
        ])

        ar_aging = self._ar_aging()
        currency_ticker, _ticker_error = _cached_payload()

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
            'helpdesk': {'sla_breached': breached, 'open_tickets': open_tickets},
            'inventory': {'stock_alerts': stock_alerts, 'threshold': threshold},
            'ar_aging': ar_aging,
            'currency_ticker': currency_ticker,
        })

    @http.route('/sales_insights/ask', type='http', auth='public',
                methods=['GET', 'POST'], csrf=False, cors='*')
    def ask(self, **kw):
        if not self._check_key(kw.get('api_key')):
            return request.make_json_response({'error': 'invalid api_key'}, status=403)
        text = (kw.get('q') or kw.get('query') or '').strip()
        if not text:
            return request.make_json_response({'answer': 'Soru gir.'})
        answer = request.env['sales.insights.nl'].sudo().query(text)
        return request.make_json_response(answer)

    @http.route('/sales_insights/ask_user', type='jsonrpc', auth='user')
    def ask_user(self, q=None):
        text = (q or '').strip()
        if not text:
            return {'answer': 'Soru gir.'}
        return request.env['sales.insights.nl'].sudo().query(text)
