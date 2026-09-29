import csv
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


def import_customers(csv_path):
    created, updated, skipped = 0, 0, 0

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get('name') or '').strip()
            email = (row.get('email') or '').strip()
            phone = (row.get('phone') or '').strip()

            if not name or not email:
                print(f'skip (missing name/email): {row}')
                skipped += 1
                continue

            existing = call('res.partner', 'search', [[['email', '=', email]]], {'limit': 1})

            if existing:
                call('res.partner', 'write', [existing, {'name': name, 'phone': phone}])
                print(f'updated: {email}')
                updated += 1
            else:
                call('res.partner', 'create', [{
                    'name': name,
                    'email': email,
                    'phone': phone,
                }])
                print(f'created: {email}')
                created += 1

    print(f'\nDone. created={created} updated={updated} skipped={skipped}')


if __name__ == '__main__':
    import_customers('customers.csv')