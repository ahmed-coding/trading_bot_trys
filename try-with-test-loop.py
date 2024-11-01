import json
from binance.client import Client
from datetime import datetime
import math
import time
import csv
import os
import statistics
from binance.exceptions import BinanceAPIException
import threading

# إعداد مفاتيح API الخاصة بك

api_key = 'of6qt1T1MpGvlgma1qxwFTLdrGNNVsMj0fKf8LZy1sMf3OqTrwHC7BCRIkgsSsda'
api_secret = 'MZuALJiqyWMoQ0WkPE6tqWdToGLTHLsap5m95qhPIDtizy1FPD0TQBXNvyQBhgFf'

client = Client(api_key, api_secret)
current_prices = {}
active_trades = {}
balance = 15  # الرصيد المبدئي للبوت
excluded_symbols = set()  # Symbols to skip due to recurring errors

# ملف CSV لتسجيل التداولات
csv_file = 'trades_log.csv'
if not os.path.exists(csv_file):
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['الرمز', 'الكمية', 'السعر الابتدائي', 'سعر الهدف', 'سعر الإيقاف', 'الوقت', 'النتيجة', 'الرصيد المتبقي'])

# الحصول على أفضل العملات بناءً على حجم التداول مع استقرار السوق
def get_top_symbols(limit=10):
    tickers = client.get_ticker()
    sorted_tickers = sorted(tickers, key=lambda x: float(x['quoteVolume']), reverse=True)
    top_symbols = []
    for ticker in sorted_tickers:
        if ticker['symbol'].endswith("USDT"):
            klines = client.get_klines(symbol=ticker['symbol'], interval=Client.KLINE_INTERVAL_1HOUR, limit=24)
            closing_prices = [float(kline[4]) for kline in klines]
            stddev = statistics.stdev(closing_prices)
            if stddev < 0.02 and ticker['symbol'] not in excluded_symbols:
                top_symbols.append(ticker['symbol'])
            if len(top_symbols) >= limit:
                break
    return top_symbols

symbols_to_trade = get_top_symbols(10)

# دالة ضبط الكمية بناءً على دقة السوق و LOT_SIZE
def adjust_quantity(symbol, quantity):
    step_size = get_lot_size(symbol)
    if step_size is None:
        return quantity
    precision = int(round(-math.log(step_size, 10), 0))
    return round(quantity, precision)

def get_lot_size(symbol):
    try:
        exchange_info = client.get_symbol_info(symbol)
        for filter in exchange_info['filters']:
            if filter['filterType'] == 'LOT_SIZE':
                return float(filter['stepSize'])
    except BinanceAPIException as e:
        print(f"خطأ في جلب حجم اللوت لـ {symbol}: {e}")
    return None

# تحقق من الحد الأدنى للقيمة Notional
def meets_min_notional(symbol, price, quantity):
    try:
        min_notional = float([f['minNotional'] for f in client.get_symbol_info(symbol)['filters'] if f['filterType'] == 'MIN_NOTIONAL'][0])
        return quantity * price >= min_notional
    except (IndexError, KeyError, BinanceAPIException):
        return False

def open_trade_with_dynamic_target(symbol, investment=2, base_profit_target=0.0005, base_stop_loss=0.0001, timeout=1):
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

def check_trade_conditions():
    global balance
    for symbol, trade in list(active_trades.items()):
        try:
            current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
            current_prices[symbol] = current_price
        except BinanceAPIException as e:
            
            print(f"خطأ في تحديث السعر لـ {symbol}: {e}")
            if 'NOTIONAL' in str(e) or 'Invalid symbol' in str(e):
                excluded_symbols.add(symbol)  # Exclude symbols causing frequent errors
            continue

        result = None
        try:
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

        except BinanceAPIException as e:
            print(f"خطأ في بيع {symbol}: {e}")
            if 'NOTIONAL' in str(e) or 'Invalid symbol' in str(e):
                excluded_symbols.add(symbol)  # Exclude symbols causing frequent errors
            continue

        if result:
            print(f"{datetime.now()} - تم {result} الصفقة لـ {symbol} عند السعر {current_price}")
            with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow([symbol, trade['quantity'], trade['initial_price'], trade['target_price'], trade['stop_price'], datetime.now(), result, balance])
            del active_trades[symbol]

def update_prices():
    while True:
        for symbol in symbols_to_trade:
            if symbol in excluded_symbols:
                continue
            try:
                current_prices[symbol] = float(client.get_symbol_ticker(symbol=symbol)['price'])
                if symbol not in active_trades:
                    open_trade_with_dynamic_target(symbol)
            except BinanceAPIException as e:
                print(f"خطأ في تحديث السعر لـ {symbol}: {e}")
                if 'NOTIONAL' in str(e) or 'Invalid symbol' in str(e):
                    excluded_symbols.add(symbol)  # Exclude symbols causing frequent errors

def monitor_trades():
    while True:
        check_trade_conditions()


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


# load_open_trades_from_portfolio()

print(f"تم بدء تشغيل البوت في {datetime.now()}")
price_thread = threading.Thread(target=update_prices)
trade_thread = threading.Thread(target=monitor_trades)
price_thread.start()
trade_thread.start()
