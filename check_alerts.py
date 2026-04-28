import json
import os
import requests
from datetime import datetime

TG_TOKEN = os.environ['TG_TOKEN']
TG_CHAT = os.environ['TG_CHAT']

def get_mark_price(coin):
      r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT", timeout=10)
      r.raise_for_status()
      return float(r.json()['price'])

def send_telegram(text):
    requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={'chat_id': TG_CHAT, 'text': text, 'parse_mode': 'HTML'}, timeout=10)

def main():
    with open('alerts.json', 'r') as f:
        alerts = json.load(f)
    changed = False
    now = datetime.now().strftime('%d.%m.%Y %H:%M')
    for alert in alerts:
        if not alert.get('active', True):
            continue
        try:
            price = get_mark_price(alert['coin'])
        except Exception as e:
            print(f"Fehler: {e}")
            continue
        target = alert['price']
        direction = alert['direction']
        triggered = (direction == 'above' and price >= target) or (direction == 'below' and price <= target)
        if triggered:
            icon = '\U0001f7e2' if direction == 'above' else '\U0001f534'
            arrow = '▲' if direction == 'above' else '▼'
            msg = f"{icon} <b>PREIS ALERT</b> - <b>{alert['coin']}</b>\nZiel {arrow} ${target:,.0f} erreicht!\nMark Price: <b>${price:,.2f}</b>\n<code>{now} UTC</code>"
            send_telegram(msg)
            alert['active'] = False
            changed = True
            print(f"Alert: {alert['coin']} {direction} ${target}")
        else:
            print(f"{alert['coin']}: ${price:,.2f}")
    if changed:
        with open('alerts.json', 'w') as f:
            json.dump(alerts, f, indent=2)

if __name__ == '__main__':
    main()
