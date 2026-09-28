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