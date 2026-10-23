import json
import logging
import os
import tempfile
import time
from datetime import date

import requests

from odoo import http

_logger = logging.getLogger(__name__)

CACHE_TTL = 60  # saniye
OUNCE_GRAMS = 31.1035

# Geçmiş /var/lib/odoo (host'ta ./data/odoo) bind mount'ına yazılır;
# böylece konteyner/docker restart'ta Gün içi trend kaybolmaz.
STATE_FILE = os.path.join(
    os.environ.get("ODOO_DATA_DIR", "/var/lib/odoo"), "finance_ticker_state.json"
)

# Gram has altına göre hesaplanan ürünler (22 ayar = 0.916 saflık)
GOLD_ITEMS = [
    ("gram_has", "Gram Has Altın", 1.0),
    ("gram_22", "Gram 22 Ayar", 0.916),
    ("ceyrek", "Çeyrek Altın", 1.754 * 0.916),
    ("yarim", "Yarım Altın", 3.508 * 0.916),
    ("tam", "Tam Altın", 7.016 * 0.916),
    ("cumhuriyet", "Cumhuriyet Altını", 7.216 * 0.916),
]

# Gün başına history sınırı: 60 sn TTL ile borsa günü (~700 nokta) için güvenli üst sınır
HISTORY_DAY_CAP = 800

_state = {"ts": 0, "payload": None, "day": None, "history": {}}


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


def _load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return
    if data.get("day") == date.today().isoformat():
        _state["day"] = data["day"]
        _state["history"] = data.get("history", {})


def _save_state():
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=os.path.dirname(STATE_FILE), delete=False
        ) as f:
            json.dump(
                {"day": _state["day"], "history": _state["history"]}, f
            )
        os.replace(f.name, STATE_FILE)
    except Exception:
        _logger.debug("Ticker state kaydedilemedi", exc_info=True)


def _track(key, value):
    """Günün ilk değerinden bugüne % değişim + aynı pencereyi gösteren sparkline.

    history günün ilk çağrısından itibaren tutulur, böylece sparkline eğimi
    ile gösterilen % değişim daima aynı zaman penceresini yansıtır.
    """
    today = date.today().isoformat()
    if _state["day"] != today:
        _state["day"] = today
        _state["history"] = {}
    hist = _state["history"].setdefault(key, [])
    if len(hist) >= HISTORY_DAY_CAP:
        del hist[0]
    hist.append(value)
    base = hist[0]
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

    _save_state()
    return items


_load_state()


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
