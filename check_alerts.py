import json
import os
import time
import requests
from datetime import datetime, timezone

TG_TOKEN = os.environ['TG_TOKEN']
TG_CHAT  = os.environ['TG_CHAT']

CG_IDS = {
    'BTC':'bitcoin','ETH':'ethereum','BNB':'binancecoin',
    'SOL':'solana','XRP':'ripple','SUI':'sui','TAO':'bittensor',
    'KAS':'kaspa','NEAR':'near','DOGE':'dogecoin','AVAX':'avalanche-2',
    'LINK':'chainlink','ARB':'arbitrum','OP':'optimism',
    'TON':'the-open-network','PEPE':'pepe','WIF':'dogwifcoin',
}

def get_prices(coins, retries=3, delay=5):
    ids = [CG_IDS[c] for c in coins if c in CG_IDS]
    if not ids: return {}
    for attempt in range(retries):
        try:
            r = requests.get(
                'https://api.coingecko.com/api/v3/simple/price',
                params={'ids': ','.join(ids), 'vs_currencies': 'usd'},
                timeout=10
            )
            r.raise_for_status()
            data = r.json()
            return {c: data[CG_IDS[c]]['usd'] for c in coins if c in CG_IDS and CG_IDS[c] in data}
        except Exception as e:
            print(f"CoinGecko Fehler (Versuch {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    return {}

def send_telegram(text):
    requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        json={'chat_id': TG_CHAT, 'text': text, 'parse_mode': 'HTML'},
        timeout=10
    )

def fmt(price):
    if price >= 100: return f"${price:,.2f}"
    if price >= 1:   return f"${price:.4f}"
    return f"${price:.6f}"

def dedup_alerts(alerts):
    seen, result, removed = set(), [], 0
    for a in alerts:
        key = (a['coin'], a['price'], a['direction'], a.get('active', True))
        if key not in seen:
            seen.add(key)
            result.append(a)
        else:
            print(f"Duplikat entfernt: {a['coin']} {a['direction']} {a['price']}")
            removed += 1
    return result, removed > 0

def check_alerts(alerts, prices, now):
    changed = False
    for alert in alerts:
        if not alert.get('active', True): continue
        coin, price = alert['coin'], prices.get(alert['coin'])
        if price is None: print(f"Kein Preis: {coin}"); continue
        target, direction = alert['price'], alert['direction']
        if (direction == 'above' and price >= target) or (direction == 'below' and price <= target):
            icon  = '\U0001f7e2' if direction == 'above' else '\U0001f534'
            arrow = '▲' if direction == 'above' else '▼'
            send_telegram(
                f"{icon} <b>PREIS ALERT</b> - <b>{coin}</b>\n"
                f"Ziel {arrow} {fmt(target)} erreicht!\n"
                f"Preis: <b>{fmt(price)}</b>\n<code>{now} UTC</code>"
            )
            alert['active'] = False
            changed = True
            print(f"Alert: {coin} {direction} {fmt(target)}")
    return changed

def check_trades(trades, prices, now):
    changed = False
    for trade in trades:
        if not trade.get('active', True): continue
        coin, price = trade['coin'], prices.get(trade['coin'])
        if price is None: print(f"Kein Preis (Trade): {coin}"); continue

        is_long   = trade['direction'] == 'long'
        dir_label = 'LONG' if is_long else 'SHORT'
        sl        = trade.get('sl')
        tps_hit   = trade.setdefault('tpsHit', [])

        if sl is not None and ((is_long and price <= sl) or (not is_long and price >= sl)):
            send_telegram(
                f"🛑 <b>STOP LOSS</b> - <b>{coin}</b> {dir_label}\n"
                f"SL {fmt(sl)} wurde getroffen\n"
                f"Preis: <b>{fmt(price)}</b>\n<code>{now} UTC</code>"
            )
            trade['slHit'] = True
            trade['active'] = False
            changed = True
            print(f"SL: {coin} {dir_label} @ {fmt(price)}")
            continue

        for tp_key in ['tp1', 'tp2', 'tp3']:
            tp_val = trade.get(tp_key)
            if tp_val is None or tp_key in tps_hit: continue
            if (is_long and price >= tp_val) or (not is_long and price <= tp_val):
                send_telegram(
                    f"🎯 <b>{tp_key.upper()} ERREICHT</b> - <b>{coin}</b> {dir_label}\n"
                    f"{tp_key.upper()} {fmt(tp_val)} getroffen!\n"
                    f"Preis: <b>{fmt(price)}</b>\n<code>{now} UTC</code>"
                )
                tps_hit.append(tp_key)
                changed = True
                print(f"{tp_key.upper()}: {coin} {dir_label} @ {fmt(price)}")

        defined_tps = [k for k in ['tp1', 'tp2', 'tp3'] if trade.get(k) is not None]
        if defined_tps and all(t in tps_hit for t in defined_tps):
            trade['active'] = False
            changed = True
            print(f"Alle TPs: {coin} Trade geschlossen")

    return changed

def main():
    with open('alerts.json', 'r') as f:
        data = json.load(f)

    if isinstance(data, list):
        data = {'alerts': data, 'trades': []}

    data['alerts'], dedup_changed = dedup_alerts(data.setdefault('alerts', []))
    trades = data.setdefault('trades', [])
    alerts = data['alerts']

    active_alerts = [a for a in alerts if a.get('active', True)]
    active_trades = [t for t in trades if t.get('active', True)]
    if not active_alerts and not active_trades:
        if dedup_changed:
            with open('alerts.json', 'w') as f:
                json.dump(data, f, indent=2)
        return

    coins = {a['coin'] for a in active_alerts} | {t['coin'] for t in active_trades}
    prices = get_prices(list(coins))
    if not prices:
        print("Preise konnten nicht abgerufen werden."); return

    for coin, price in prices.items():
        print(f"{coin}: {fmt(price)}")

    now = datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')
    changed  = dedup_changed
    changed |= check_alerts(alerts, prices, now)
    changed |= check_trades(trades, prices, now)

    if changed:
        with open('alerts.json', 'w') as f:
            json.dump(data, f, indent=2)

if __name__ == '__main__':
    main()
