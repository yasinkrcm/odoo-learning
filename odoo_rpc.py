import os
import xmlrpc.client
from dotenv import load_dotenv

load_dotenv()

url = os.environ['ODOO_URL']
db = os.environ['ODOO_DB']
username = os.environ['ODOO_USERNAME']
password = os.environ['ODOO_PASSWORD']

common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, password, {})
if not uid:
    raise SystemExit('Authentication failed: check .env values')

models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')


def call(model, method, args, kwargs=None):
    return models.execute_kw(db, uid, password, model, method, args, kwargs or {})


# CREATE
todo_id = call('my.todo', 'create', [{'name': 'Created via RPC', 'description': 'From Python'}])
print('created:', todo_id)

# READ
print(call('my.todo', 'search_read', [[]], {'fields': ['name', 'is_done', 'deadline'], 'limit': 10}))

# UPDATE
call('my.todo', 'write', [[todo_id], {'is_done': True}])

# CALL A MODEL METHOD
call('my.todo', 'action_mark_done', [[todo_id]])

# DELETE
call('my.todo', 'unlink', [[todo_id]])

# --- res.partner ile deneme ---
partner_id = call('res.partner', 'create', [{
    'name': 'Test Müşteri',
    'email': 'test@example.com',
    'is_vip': True,
}])
print('partner:', partner_id)

records = call('res.partner', 'search_read',
    [[['email', '=', 'test@example.com']]],
    {'fields': ['name', 'email', 'is_vip']})
print(records)

# --- güncelleme ---
call('res.partner', 'write', [[partner_id], {'phone': '+90 555 000 0000'}])

updated = call('res.partner', 'search_read',
    [[['id', '=', partner_id]]],
    {'fields': ['name', 'phone']})
print(updated)

# --- crm.lead ile deneme ---
lead_id = call('crm.lead', 'create', [{
    'name': 'Yeni fırsat',
    'partner_id': partner_id,
    'expected_revenue': 5000,
}])
print('lead:', lead_id)

lead = call('crm.lead', 'search_read',
    [[['id', '=', lead_id]]],
    {'fields': ['name', 'partner_id', 'expected_revenue']})
print(lead)

# --- sale.order ile deneme ---
product = call('product.product', 'search_read', [[]], {'fields': ['name'], 'limit': 1})
print('product:', product)
product_id = product[0]['id']

order_id = call('sale.order', 'create', [{
    'partner_id': partner_id,
    'order_line': [
        (0, 0, {'product_id': product_id, 'product_uom_qty': 3}),
    ],
}])
print('order:', order_id)

order = call('sale.order', 'search_read',
    [[['id', '=', order_id]]],
    {'fields': ['name', 'partner_id', 'amount_total', 'state']})
print(order)

call('sale.order', 'action_confirm', [[order_id]])

confirmed = call('sale.order', 'search_read',
    [[['id', '=', order_id]]],
    {'fields': ['state']})
print(confirmed)

grouped = call('my.todo', 'read_group', [[], ['is_done'], ['is_done']])
print(grouped)