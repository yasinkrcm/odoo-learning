import logging
import time
from datetime import date

import requests

from odoo import http

_logger = logging.getLogger(__name__)

CACHE_TTL = 60  # saniye
HISTORY_LEN = 24  # sparkline nokta sayısı
OUNCE_GRAMS = 31.1035

# Gram has altına göre hesaplanan ürünler (22 ayar = 0.916 saflık)
GOLD_ITEMS = [
    ("gram_has", "Gram Has Altın", 1.0),
    ("gram_22", "Gram 22 Ayar", 0.916),
    ("ceyrek", "Çeyrek Altın", 1.754 * 0.916),
    ("yarim", "Yarım Altın", 3.508 * 0.916),
    ("tam", "Tam Altın", 7.016 * 0.916),
    ("cumhuriyet", "Cumhuriyet Altını", 7.216 * 0.916),
]

_state = {"ts": 0, "payload": None, "day": None, "open": {}, "history": {}}


def _fetch_raw():
    """USD bazlı kurlar + ons altın (USD). Ücretsiz, anahtarsız kaynaklar."""
    fx = requests.get("https://open.er-api.com/v6/latest/USD", timeout=8)
    fx.raise_for_status()
    rates = fx.json()["rates"]
    usd_try = float(rates["TRY"])
    eur_try = usd_try / float(rates["EUR"])

    gold = requests.get("https://api.gold-api.com/price/XAU", timeout=8)
    gold.raise_for_status()
    ons = float(gold.json()["price"])
    return usd_try, eur_try, ons


def _track(key, value):
    """Günün ilk değerine göre % değişim ve sparkline geçmişi tut."""
    today = date.today().isoformat()
    if _state["day"] != today:
        _state["day"] = today
        _state["open"] = {}
    base = _state["open"].setdefault(key, value)
    hist = _state["history"].setdefault(key, [])
    hist.append(value)
    del hist[:-HISTORY_LEN]
    change = ((value - base) / base * 100) if base else 0.0
    return round(change, 2), list(hist)


def _build_payload():
    usd_try, eur_try, ons = _fetch_raw()
    gram_has = ons * usd_try / OUNCE_GRAMS

    items = []

    def add(key, label, value, currency):
        change, hist = _track(key, value)
        items.append({
            "key": key,
            "label": label,
            "value": round(value, 2),
            "currency": currency,
            "change": change,
            "history": hist,
        })

    add("usd", "Dolar", usd_try, "₺")
    add("eur", "Euro", eur_try, "₺")
    add("ons", "Ons Altın", ons, "$")
    for key, label, factor in GOLD_ITEMS:
        add(key, label, gram_has * factor, "₺")
    return items


class FinanceTickerController(http.Controller):

    @http.route("/finance_ticker/data", type="jsonrpc", auth="user")
    def data(self):
        now = time.time()
        if _state["payload"] is None or now - _state["ts"] > CACHE_TTL:
            try:
                _state["payload"] = _build_payload()
                _state["ts"] = now
            except Exception:
                _logger.exception("Finance ticker verisi alınamadı")
                if _state["payload"] is None:
                    return {"items": [], "error": True}
        return {"items": _state["payload"], "error": False}
