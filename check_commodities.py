#!/usr/bin/env python3
"""
Commodity Preis-Alert Checker
Läuft via GitHub Actions alle 5 Min — prüft commodities_alerts.json gegen aktuelle Yahoo-Finance-Preise
und sendet Telegram-Nachrichten bei Treffer.
"""
import json
import os
import sys
import requests

try:
    import yfinance as yf
except ImportError:
    print("yfinance nicht installiert", file=sys.stderr)
    sys.exit(1)

ALERTS_FILE = "commodities_alerts.json"
TG_TOKEN    = os.environ.get("TG_TOKEN", "")
TG_CHAT     = os.environ.get("TG_CHAT",  "")


def get_price(sym: str) -> float | None:
    try:
        t = yf.Ticker(sym)
        price = t.fast_info.last_price
        if price and price > 0:
            return float(price)
    except Exception:
        pass
    try:
        hist = yf.download(sym, period="1d", interval="1m", progress=False, auto_adjust=True)
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


def send_telegram(token: str, chat: str, text: str) -> bool:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if not r.ok:
            print(f"[TG] Fehler {r.status_code}: {r.text[:200]}", file=sys.stderr)
            return False
        return True
    except Exception as e:
        print(f"[TG] Netzwerkfehler: {e}", file=sys.stderr)
        return False


def load_alerts() -> dict:
    if not os.path.exists(ALERTS_FILE):
        return {"alerts": []}
    with open(ALERTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        data = {"alerts": data}
    return data


def save_alerts(data: dict) -> None:
    with open(ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main() -> int:
    data = load_alerts()
    alerts = data.get("alerts", [])

    active = [a for a in alerts if a.get("active")]
    if not active:
        print("Keine aktiven Alerts.")
        return 0

    # Unique Symbole bündeln → ein Fetch pro Symbol
    syms = {a["sym"]: None for a in active}
    for sym in syms:
        price = get_price(sym)
        syms[sym] = price
        print(f"  {sym}: {price}")

    changed = False
    for alert in alerts:
        if not alert.get("active"):
            continue
        price = syms.get(alert["sym"])
        if price is None:
            print(f"[WARN] Kein Preis für {alert['sym']}")
            continue

        direction = alert.get("direction", "above")
        target    = float(alert.get("price", 0))
        hit = (direction == "above" and price >= target) or \
              (direction == "below" and price <= target)

        if not hit:
            continue

        alert["active"] = False
        changed = True

        arrow = "▲" if direction == "above" else "▼"
        dir_de = "über" if direction == "above" else "unter"
        name   = alert.get("name", alert.get("sym", "?"))
        comment = alert.get("comment", "")

        msg = (
            f"🎯 <b>PREIS ALERT</b> — <b>{name}</b>\n"
            f"{arrow} {dir_de} <b>{target:,.2f}</b> erreicht! "
            f"(Kurs: {price:,.2f})"
            + (f"\n💬 {comment}" if comment else "")
        )
        print(f"[ALERT] {name} {dir_de} {target} → Preis: {price}")

        if TG_TOKEN and TG_CHAT:
            ok = send_telegram(TG_TOKEN, TG_CHAT, msg)
            print(f"  Telegram: {'✓' if ok else '✗'}")
        else:
            print("  [WARN] TG_TOKEN/TG_CHAT nicht gesetzt — kein Telegram")

    if changed:
        save_alerts(data)
        print("commodities_alerts.json aktualisiert.")
        return 1  # Signalisiert dem Workflow: Commit nötig

    return 0


if __name__ == "__main__":
    sys.exit(main())
