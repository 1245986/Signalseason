import json
import os
import requests
from datetime import datetime

TG_TOKEN = os.environ['TG_TOKEN']
TG_CHAT  = os.environ['TG_CHAT']

CG_IDS = {
    'BTC':'bitcoin','ETH':'ethereum','BNB':'binancecoin',
    'SOL':'solana','XRP':'ripple','SUI':'sui','TAO':'bittensor',
    'KAS':'kaspa','NEAR':'near','DOGE':'dogecoin','AVAX':'avalanche-2',
    'LINK':'chainlink','ARB':'arbitrum','OP':'optimism',
    'TON':'the-open-network','PEPE':'pepe','WIF':'dogwifcoin',
}

def get_prices(coins):
    ids = [CG_IDS[c] for c in coins if c in CG_IDS]
    if not ids: return {}
    r = requests.get('https://api.coingecko.com/api/v3/simple/price',
                       params={'ids':','.join(ids),'vs_currencies':'usd'},timeout=10)
    r.raise_for_status()
    data = r.json()
    return {c: data[CG_IDS[c]]['usd'] for c in coins if c in CG_IDS and CG_IDS[c] in data}

def send_telegram(text):
    requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                    json={'chat_id':TG_CHAT,'text':text,'parse_mode':'HTML'},timeout=10)

def main():
    with open('alerts.json','r') as f:
        alerts = json.load(f)
    active = [a for a in alerts if a.get('active',True)]
    if not active: return
    try:
        prices = get_prices(list({a['coin'] for a in active}))
    except Exception as e:
        print(f"Fehler: {e}"); return
    changed = False
    now = datetime.now().strftime('%d.%m.%Y %H:%M')
    for alert in alerts:
        if not alert.get('active',True): continue
        coin = alert['coin']
        price = prices.get(coin)
        if price is None: print(f"Kein Preis: {coin}"); continue
        print(f"{coin}: ${price:,.2f}")
        target, direction = alert['price'], alert['direction']
        triggered = (direction=='above' and price>=target) or (direction=='below' and price<=target)
        if triggered:
            icon = '\U0001f7e2' if direction=='above' else '\U0001f534'
            arrow = '▲' if direction=='above' else '▼'
            msg = (f"{icon} <b>PREIS ALERT</b> - <b>{coin}</b>\n"
                   f"Ziel {arrow} ${target:,.0f} erreicht!\n"
                   f"Preis: <b>${price:,.2f}</b>\n<code>{now} UTC</code>")
            send_telegram(msg)
            alert['active'] = False
            changed = True
            print(f"Alert: {coin} {direction} ${target}")
    if changed:
        with open('alerts.json','w') as f:
            json.dump(alerts,f,indent=2)

if __name__ == '__main__':
    main()
