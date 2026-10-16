import os
import random
import xmlrpc.client
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("ODOO_URL")
DB = os.getenv("ODOO_DB")
USER = os.getenv("ODOO_USERNAME")
PASSWORD = os.getenv("ODOO_PASSWORD")

common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
uid = common.authenticate(DB, USER, PASSWORD, {})
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")


def call(model, method, *args, **kwargs):
    return models.execute_kw(DB, uid, PASSWORD, model, method, list(args), kwargs)


partners = call("res.partner", "search", [("is_company", "=", True)], limit=10)
products = call("product.product", "search", [("default_code", "like", "EXT-")], limit=20)
users = call("res.users", "search", [("share", "=", False)], limit=5)

if not partners or not products:
    raise SystemExit("Need company partners and EXT- products (run sync_products.py first).")

for _ in range(15):
    lines = [
        (0, 0, {"product_id": random.choice(products), "product_uom_qty": random.randint(1, 5)})
        for _ in range(random.randint(1, 3))
    ]
    order_id = call("sale.order", "create", [{
        "partner_id": random.choice(partners),
        "user_id": random.choice(users),
        "order_line": lines,
    }])[0]
    call("sale.order", "action_confirm", [order_id])
    when = datetime.now() - timedelta(days=random.randint(0, 120))
    call("sale.order", "write", [order_id], {"date_order": when.strftime("%Y-%m-%d %H:%M:%S")})
    print("confirmed order", order_id, when.date())