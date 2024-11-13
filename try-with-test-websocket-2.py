import websocket
import json
from binance.client import Client
from datetime import datetime
import math
import time
import threading
import csv
import os
import statistics

# إعداد مفاتيح API الخاصة بك
# api_key = 'SR8yTMOMfCqYGHxrOUNBL1e4mTY2TTaEMNkZFIZ5glXhHeCCZKhN6CaA6CpmDkjT'
# api_secret = 'tGlNOS1KwAsEu3q6EiqM62yDjrFmYj2l41D4bajYA3KeBcjedZuVFcD8ZQFRe5eI'

api_key = 'tweOjH1Keln44QaxLCr3naevRPgF3j3sYuOpaAg9B7nUT74MyURemvivEUcihfkt'
api_secret = 'XLlku378D8aZzYg9JjOTtUngA8Q73xBCyy7jGVbqRYSoEICsGBfWC0cIsRptLHxb'


client = Client(api_key, api_secret)
client.API_URL = 'https://testnet.binance.vision/api'

current_prices = {}
active_trades = {}
trade_history = []
balance = 70  # الرصيد المبدئي للبوت

# ملف CSV لتسجيل التداولات
csv_file = 'trades_log.csv'
if not os.path.exists(csv_file):
    with open(csv_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['الرمز', 'الكمية', 'السعر الابتدائي', 'سعر الهدف', 'سعر الإيقاف', 'الوقت', 'النتيجة', 'الرصيد المتبقي'])

# تحديث قائمة العملات المتداولة بناءً على حجم التداول
def update_top_symbols(limit=10):
    tickers = client.get_ticker()
    sorted_tickers = sorted(tickers, key=lambda x: float(x['quoteVolume']), reverse=True)
    top_symbols = [ticker['symbol'] for ticker in sorted_tickers if ticker['symbol'].endswith("USDT")][:limit]
    return top_symbols

# تحميل الصفقات المفتوحة من المحفظة
def load_open_trades_from_portfolio():
    global balance
    account_info = client.get_account()
    for asset in account_info['balances']:
        if float(asset['free']) > 0:
            symbol = asset['asset'] + 'USDT'
            try:
                price = float(client.get_symbol_ticker(symbol=symbol)['price'])
                quantity = float(asset['free'])
                target_price = price * 1.0003  # هدف ربح سريع
                stop_price = price * 0.9995   # إيقاف خسارة سريع
                active_trades[symbol] = {
                    'quantity': quantity,
                    'initial_price': price,
                    'target_price': target_price,
                    'stop_price': stop_price,
                    'start_time': time.time(),
                    'timeout': 30  # المهلة الزمنية 30 ثانية
                }
                print(f"تم استعادة الصفقة المفتوحة لـ {symbol} من المحفظة.")
                balance -= quantity * price  # تعديل الرصيد بناءً على الصفقات الحالية
            except Exception as e:
                print(f"خطأ في تحميل الصفقة لـ {symbol}: {e}")

# دالة ضبط الكمية بناءً على دقة السوق
def adjust_quantity(symbol, quantity):
    step_size = get_lot_size(symbol)
    if step_size is None:
        return quantity
    precision = int(round(-math.log(step_size, 10), 0))
    return round(quantity, precision)

# دالة تحديد الكمية الصالحة للتداول لكل عملة
def get_lot_size(symbol):
    exchange_info = client.get_symbol_info(symbol)
    for filter in exchange_info['filters']:
        if filter['filterType'] == 'LOT_SIZE':
            step_size = float(filter['stepSize'])
            return step_size
    return None

# استراتيجية فتح صفقة مع هدف ديناميكي

def open_trade_with_dynamic_target(symbol, investment=5, base_profit_target=0.0005, base_stop_loss=0.0001, timeout=1):
    global balance
    price = float(client.get_symbol_ticker(symbol=symbol)['price'])
    avg_volatility = statistics.stdev([float(kline[4]) for kline in client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_15MINUTE, limit=20)])
    
    profit_target = base_profit_target + avg_volatility
    stop_loss = base_stop_loss + avg_volatility * 0.5
    target_price = price * (1 + profit_target)
    stop_price = price * (1 - stop_loss)
    quantity = adjust_quantity(symbol, investment / price)

    if balance < investment:
        print(f"{datetime.now()} - الرصيد الحالي غير كافٍ لفتح صفقة جديدة.")
        return
    
    # تنفيذ أمر شراء
    order = client.order_market_buy(
        symbol=symbol,
        quantity=quantity
    )
    balance -= investment  # تعديل الرصيد بعد فتح الصفقة

    # تخزين تفاصيل الصفقة في active_trades
    active_trades[symbol] = {
        'quantity': quantity,
        'initial_price': price,
        'target_price': target_price,
        'stop_price': stop_price,
        'start_time': time.time(),
        'timeout': timeout * 60
    }
    print(f"{datetime.now()} - تم فتح صفقة شراء لـ {symbol} بسعر {price}, بهدف {target_price} وإيقاف خسارة عند {stop_price}")

# دالة فحص حالة الصفقات المفتوحة وإغلاقها
def check_trade_conditions():
    global balance
    for symbol, trade in list(active_trades.items()):
        current_price = current_prices.get(symbol)
        if current_price is None:
            continue

        result = None
        if current_price >= trade['target_price']:
            client.order_market_sell(symbol=symbol, quantity=trade['quantity'])
            result = 'ربح'
            balance += trade['quantity'] * current_price
        elif current_price <= trade['stop_price']:
            client.order_market_sell(symbol=symbol, quantity=trade['quantity'])
            result = 'خسارة'
            balance += trade['quantity'] * current_price
        elif time.time() - trade['start_time'] >= trade['timeout']:
            client.order_market_sell(symbol=symbol, quantity=trade['quantity'])
            result = 'انتهاء المهلة'
            balance += trade['quantity'] * current_price

        if result:
            print(f"{datetime.now()} - تم {result} الصفقة لـ {symbol} عند السعر {current_price}")
            # تسجيل النتيجة في ملف CSV
            with open(csv_file, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([symbol, trade['quantity'], trade['initial_price'], trade['target_price'], trade['stop_price'], datetime.now(), result, balance])
            del active_trades[symbol]

# تهيئة WebSocket لتحديث الأسعار وتنفيذ الصفقات
def on_message(ws, message):
    data = json.loads(message)
    if 's' in data and 'p' in data:
        symbol = data['s']
        price = float(data['p'])
        previous_price = current_prices.get(symbol)
        if previous_price is None or abs(price - previous_price) / previous_price > 0.001:
            current_prices[symbol] = price
            print(f"{datetime.now()} - تحديث فوري للسعر {symbol}: {price}")
            if symbol not in active_trades:
                open_trade_with_dynamic_target(symbol)
        check_trade_conditions()

# تحديث قائمة العملات المتداولة بانتظام
def periodic_update_top_symbols(interval=300):
    while True:
        global symbols_to_trade
        symbols_to_trade = update_top_symbols(10)
        print(f"تحديث قائمة العملات المتداولة: {symbols_to_trade}")
        time.sleep(interval)

# تهيئة WebSocket عند التشغيل
def on_open(ws):
    params = [f"{symbol.lower()}@trade" for symbol in symbols_to_trade]
    ws.send(json.dumps({"method": "SUBSCRIBE", "params": params, "id": 1}))

# تشغيل WebSocket والخيوط المساعدة
symbols_to_trade = update_top_symbols(10)  # إعداد العملات المتداولة في البداية
load_open_trades_from_portfolio()  # تحميل الصفقات المفتوحة عند بدء التشغيل

ws = websocket.WebSocketApp("wss://stream.binance.com:9443/ws", on_open=on_open, on_message=on_message)
print(f"تم بدء تشغيل البوت في {datetime.now()}")
websocket_thread = threading.Thread(target=ws.run_forever)
symbol_update_thread = threading.Thread(target=periodic_update_top_symbols)
websocket_thread.start()
symbol_update_thread.start()
