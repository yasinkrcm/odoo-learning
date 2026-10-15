import logging
import os
import sys
import xmlrpc.client

import requests
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("ODOO_URL")
DB = os.getenv("ODOO_DB")
USER = os.getenv("ODOO_USERNAME")
PASSWORD = os.getenv("ODOO_PASSWORD")

SOURCE_URL = "https://dummyjson.com/products?limit=20"
REF_PREFIX = "EXT-"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("sync.log")],
)
log = logging.getLogger("sync")


def connect():
    common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
    uid = common.authenticate(DB, USER, PASSWORD, {})
    if not uid:
        log.error("Odoo authentication failed")
        sys.exit(1)
    models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")
    return uid, models


def fetch_products():
    resp = requests.get(SOURCE_URL, timeout=15)
    resp.raise_for_status()
    return resp.json()["products"]


def map_product(p):
    return {
        "name": p["title"],
        "default_code": f"{REF_PREFIX}{p['id']}",
        "list_price": float(p["price"]),
        "description_sale": p.get("description") or "",
    }


def sync():
    uid, models = connect()
    stats = {"created": 0, "updated": 0, "unchanged": 0, "failed": 0}

    for p in fetch_products():
        vals = map_product(p)
        try:
            found = models.execute_kw(
                DB, uid, PASSWORD, "product.template", "search_read",
                [[("default_code", "=", vals["default_code"])]],
                {"fields": ["name", "list_price", "description_sale"], "limit": 1},
            )
            if not found:
                models.execute_kw(DB, uid, PASSWORD, "product.template", "create", [vals])
                stats["created"] += 1
                log.info("created %s", vals["default_code"])
                continue

            rec = found[0]
            changed = {
                k: v for k, v in vals.items()
                if k != "default_code" and rec.get(k) != v
            }
            if changed:
                models.execute_kw(
                    DB, uid, PASSWORD, "product.template", "write", [[rec["id"]], changed]
                )
                stats["updated"] += 1
                log.info("updated %s: %s", vals["default_code"], list(changed))
            else:
                stats["unchanged"] += 1
        except Exception as e:
            stats["failed"] += 1
            log.error("failed %s: %s", vals.get("default_code"), e)

    log.info("done: %s", stats)


if __name__ == "__main__":
    sync()