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
balance = 10  # الرصيد المبدئي للبوت
excluded_symbols = set()  # قائمة العملات المستثناة بسبب أخطاء متكررة

# ملف CSV لتسجيل التداولات
csv_file = 'trades_log.csv'
error_log_file = 'error_log.csv'

# إنشاء ملف السجل إذا لم يكن موجودًا
if not os.path.exists(csv_file):
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['الرمز', 'الكمية', 'السعر الابتدائي', 'سعر الهدف', 'سعر الإيقاف', 'الوقت', 'النتيجة', 'الرصيد المتبقي'])

if not os.path.exists(error_log_file):
    with open(error_log_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['الرمز', 'الخطأ', 'الوقت'])

if not os.path.exists(csv_file):
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['الرمز', 'الكمية', 'السعر الابتدائي', 'سعر الهدف', 'سعر الإيقاف', 'الوقت', 'النتيجة', 'الرصيد المتبقي'])


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



# دالة الحصول على أفضل العملات بناءً على حجم التداول واستقرار السوق ونسبة الربح المستهدفة
def get_top_symbols(limit=10, profit_target=0.003):
    tickers = client.get_ticker()
    sorted_tickers = sorted(tickers, key=lambda x: float(x['quoteVolume']), reverse=True)
    top_symbols = []
    for ticker in sorted_tickers:
        if ticker['symbol'].endswith("USDT") and ticker['symbol'] not in excluded_symbols:
            try:
                klines = client.get_klines(symbol=ticker['symbol'], interval=Client.KLINE_INTERVAL_1HOUR, limit=24)
                closing_prices = [float(kline[4]) for kline in klines]
                stddev = statistics.stdev(closing_prices)
                
                avg_price = sum(closing_prices) / len(closing_prices)
                volatility_ratio = stddev / avg_price

                if stddev < 0.02 and volatility_ratio >= profit_target:
                    top_symbols.append(ticker['symbol'])
                    print(f"تم اختيار العملة {ticker['symbol']} بنسبة تذبذب {volatility_ratio:.4f}")
                
                if len(top_symbols) >= limit:
                    break
            except BinanceAPIException as e:
                print(f"خطأ في جلب بيانات {ticker['symbol']}: {e}")
                excluded_symbols.add(ticker['symbol'])
    return top_symbols

# تحسين دالة ضبط الكمية adjust_quantity لتتوافق مع Notional و LOT_SIZE
def adjust_quantity(symbol, investment, price):
    step_size = get_lot_size(symbol)
    notional = investment * price
    if step_size is None or notional < 10:  # الحد الأدنى لقيمة الصفقة
        return None
    precision = int(round(-math.log(step_size, 10), 0))
    quantity = round(investment / price, precision)
    return quantity if quantity * price >= 10 else None

# دالة get_lot_size لجلب حجم اللوت للرمز المحدد
def get_lot_size(symbol):
    try:
        exchange_info = client.get_symbol_info(symbol)
        for filter in exchange_info['filters']:
            if filter['filterType'] == 'LOT_SIZE':
                return float(filter['stepSize'])
    except BinanceAPIException as e:
        log_error(symbol, f"خطأ في جلب حجم اللوت: {e}")
    return None

# سجل الأخطاء في error_log.csv
def log_error(symbol, error_message):
    with open(error_log_file, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([symbol, error_message, datetime.now()])

def check_bnb_balance(min_bnb_balance=0.001):  # تقليل الحد الأدنى المطلوب
    # تحقق من رصيد BNB للتأكد من تغطية الرسوم
    account_info = client.get_asset_balance(asset='BNB')
    if account_info:
        bnb_balance = float(account_info['free'])
        return bnb_balance >= min_bnb_balance
    return False

# تحسين دالة check_trade_conditions
def check_trade_conditions():
    global balance
    for symbol, trade in list(active_trades.items()):
        try:
            current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
            current_prices[symbol] = current_price
        except BinanceAPIException as e:
            log_error(symbol, f"خطأ في تحديث السعر: {e}")
            excluded_symbols.add(symbol)
            continue

        if current_price >= trade['target_price'] or current_price <= trade['stop_price']:
            sell_trade(symbol, trade['quantity'], "ربح" if current_price >= trade['target_price'] else "خسارة")

# تعديل دالة open_trade_with_dynamic_target
def open_trade_with_dynamic_target(symbol, investment=1.5):
    global balance
    price = float(client.get_symbol_ticker(symbol=symbol)['price'])
    quantity = adjust_quantity(symbol, investment, price)
    
    if quantity is None:
        log_error(symbol, "الكمية غير كافية لفتح صفقة")
        excluded_symbols.add(symbol)
        return

    # تحقق من الرصيد الكافي
    if balance < investment:
        print(f"{datetime.now()} - الرصيد الحالي غير كافٍ لفتح صفقة جديدة.")
        return

    try:
        client.order_market_buy(symbol=symbol, quantity=quantity)
        balance -= investment
        active_trades[symbol] = {'quantity': quantity, 'initial_price': price}
    except BinanceAPIException as e:
        log_error(symbol, f"خطأ في فتح الصفقة: {e}")
        excluded_symbols.add(symbol)


def sell_trade(symbol, trade_quantity):
    try:
        # الحصول على الكمية المتاحة في المحفظة
        balance_info = client.get_asset_balance(asset=symbol.replace("USDT", ""))
        available_quantity = float(balance_info['free'])
        
        # التحقق من أن الكمية المتاحة كافية وتلبي الحد الأدنى لـ NOTIONAL
        if available_quantity >= trade_quantity:
            # تنفيذ أمر بيع باستخدام الكمية المتاحة
            client.order_market_sell(symbol=symbol, quantity=available_quantity)
            print(f"تم تنفيذ عملية البيع لـ {symbol} بكمية {available_quantity}")
            return available_quantity
        else:
            print(f"الكمية غير كافية للبيع لـ {symbol}. الكمية المتاحة: {available_quantity}")
            return 0
    except BinanceAPIException as e:
        print(f"خطأ في بيع {symbol}: {e}")
        return 0

# def check_trade_conditions():
#     global balance
#     for symbol, trade in list(active_trades.items()):
#         try:
#             current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
#             current_prices[symbol] = current_price
#         except BinanceAPIException as e:
#             print(f"خطأ في تحديث السعر لـ {symbol}: {e}")
#             if 'NOTIONAL' in str(e) or 'Invalid symbol' in str(e):
#                 excluded_symbols.add(symbol)  # Exclude symbols causing frequent errors
#             continue

#         result = None
#         sold_quantity = 0  # الكمية التي تم بيعها فعليًا
#         try:
#             if current_price >= trade['target_price']:
#                 sold_quantity = sell_trade(symbol, trade['quantity'])
#                 result = 'ربح' if sold_quantity > 0 else None
#             elif current_price <= trade['stop_price']:
#                 sold_quantity = sell_trade(symbol, trade['quantity'])
#                 result = 'خسارة' if sold_quantity > 0 else None
#             elif time.time() - trade['start_time'] >= trade['timeout']:
#                 sold_quantity = sell_trade(symbol, trade['quantity'])
#                 result = 'انتهاء المهلة' if sold_quantity > 0 else None

#             # إذا تم تنفيذ عملية البيع بنجاح، تحديث الرصيد وإزالة الصفقة من الصفقات المفتوحة
#             if result and sold_quantity > 0:
#                 balance += sold_quantity * current_price
#                 print(f"{datetime.now()} - تم {result} الصفقة لـ {symbol} عند السعر {current_price}")
#                 with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
#                     writer = csv.writer(file)
#                     writer.writerow([symbol, sold_quantity, trade['initial_price'], trade['target_price'], trade['stop_price'], datetime.now(), result, balance])
#                 del active_trades[symbol]

#         except BinanceAPIException as e:
#             print(f"خطأ في بيع {symbol}: {e}")
#             if 'NOTIONAL' in str(e) or 'Invalid symbol' in str(e):
#                 excluded_symbols.add(symbol)  # Exclude symbols causing frequent errors
#             continue

# تحديث قائمة الرموز بشكل دوري
def update_symbols_periodically(interval=600):
    global symbols_to_trade
    while True:
        symbols_to_trade = get_top_symbols(10, profit_target=0.003)
        print(f"{datetime.now()} - تم تحديث قائمة العملات للتداول: {symbols_to_trade}")
        time.sleep(interval)

# مراقبة تحديث الأسعار وفتح الصفقات
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

# مراقبة حالة الصفقات المغلقة
def monitor_trades():
    while True:
        check_trade_conditions()

# load_open_trades_from_portfolio()

# بدء التحديث الدوري لقائمة العملات
symbols_to_trade = get_top_symbols(5, profit_target=0.003)
symbol_update_thread = threading.Thread(target=update_symbols_periodically, args=(900,))
symbol_update_thread.start()

# تشغيل خيوط تحديث الأسعار ومراقبة الصفقات
price_thread = threading.Thread(target=update_prices)
trade_thread = threading.Thread(target=monitor_trades)
price_thread.start()
trade_thread.start()

print(f"تم بدء تشغيل البوت في {datetime.now()}")
