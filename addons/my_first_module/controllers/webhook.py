from odoo import http
from odoo.http import request


class TodoWebhookController(http.Controller):

    API_KEY = 'change-me-secret'

    @http.route('/my_first_module/webhook/todo', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def create_todo_from_webhook(self, **kwargs):
        if kwargs.get('api_key') != self.API_KEY:
            return {'success': False, 'error': 'invalid api_key'}

        name = kwargs.get('name')
        if not name:
            return {'success': False, 'error': 'name is required'}

        todo = request.env['my.todo'].sudo().create({
            'name': name,
            'description': kwargs.get('description'),
        })
        return {'success': True, 'id': todo.id}