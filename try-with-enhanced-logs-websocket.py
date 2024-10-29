
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
# api_key = 'ylfzlXcNMinCdkrIwQ4hTiGvcWBfRiavo2luN3teqRPzxFj8YKCgmNBcreWfLHku'
# api_secret = 'kzObBE8vwRkeySLMClJv1h58EK7Jsh4s0LmmdS8WrF4jAaqxLXod4nt175iezxbk'


api_key = 'SR8yTMOMfCqYGHxrOUNBL1e4mTY2TTaEMNkZFIZ5glXhHeCCZKhN6CaA6CpmDkjT'

api_secret = 'tGlNOS1KwAsEu3q6EiqM62yDjrFmYj2l41D4bajYA3KeBcjedZuVFcD8ZQFRe5eI'

# تهيئة الاتصال ببايننس واستخدام Testnet
client = Client(api_key, api_secret)
# client.API_URL = 'https://testnet.binance.vision/api'

# إعداد WebSocket للأسعار الفورية لعدة عملات
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

# الحصول على أفضل العملات بناءً على حجم التداول مع استقرار السوق
def get_top_symbols(limit=5):
    try:
        tickers = client.get_ticker()
        sorted_tickers = sorted(tickers, key=lambda x: float(x['quoteVolume']), reverse=True)
        top_symbols = []
        for ticker in sorted_tickers:
            if ticker['symbol'].endswith("USDT"):
                klines = client.get_klines(symbol=ticker['symbol'], interval=Client.KLINE_INTERVAL_1HOUR, limit=24)
                closing_prices = [float(kline[4]) for kline in klines]
                stddev = statistics.stdev(closing_prices)
                if stddev < 0.02:
                    top_symbols.append(ticker['symbol'])
                if len(top_symbols) >= limit:
                    break
        print(f"{datetime.now()} - أفضل العملات للتداول: {top_symbols}")
        return top_symbols
    except Exception as e:
        print(f"{datetime.now()} - خطأ أثناء جلب أفضل العملات: {e}")
        return []

# تحديث قائمة الرموز بناءً على حجم التداول واستقرار السوق
symbols_to_trade = get_top_symbols(7)

def get_lot_size(symbol):
    try:
        exchange_info = client.get_symbol_info(symbol)
        for filter in exchange_info['filters']:
            if filter['filterType'] == 'LOT_SIZE':
                step_size = float(filter['stepSize'])
                return step_size
        return None
    except Exception as e:
        print(f"{datetime.now()} - خطأ في جلب حجم اللوت للرمز {symbol}: {e}")
        return None

def adjust_quantity(symbol, quantity):
    step_size = get_lot_size(symbol)
    if step_size is None:
        print(f"{datetime.now()} - لا يمكن تعديل الكمية بسبب غياب حجم اللوت للرمز {symbol}")
        return quantity
    precision = int(round(-math.log(step_size, 10), 0))
    return round(quantity, precision)

def open_trade_with_dynamic_target(symbol, investment=10, base_profit_target=0.0005, base_stop_loss=0.0001, timeout=1):
    global balance
    try:
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
    except Exception as e:
        print(f"{datetime.now()} - خطأ في فتح الصفقة للرمز {symbol}: {e}")

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
            with open(csv_file, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([symbol, trade['quantity'], trade['initial_price'], trade['target_price'], trade['stop_price'], datetime.now(), result, balance])
            del active_trades[symbol]

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

def on_open(ws):
    params = [f"{symbol.lower()}@trade" for symbol in symbols_to_trade]
    ws.send(json.dumps({"method": "SUBSCRIBE", "params": params, "id": 1}))

ws = websocket.WebSocketApp("wss://stream.binance.com:9443/ws", on_open=on_open, on_message=on_message)
print(f"تم بدء تشغيل البوت في {datetime.now()}")
websocket_thread = threading.Thread(target=ws.run_forever)
websocket_thread.start()
