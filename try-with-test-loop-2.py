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


# api_key = 'tweOjH1Keln44QaxLCr3naevRPgF3j3sYuOpaAg9B7nUT74MyURemvivEUcihfkt'
# api_secret = 'XLlku378D8aZzYg9JjOTtUngA8Q73xBCyy7jGVbqRYSoEICsGBfWC0cIsRptLHxb'

# تهيئة الاتصال ببايننس واستخدام Testnet
client = Client(api_key, api_secret)
# client.API_URL = 'https://testnet.binance.vision/api'


# client = Client(api_key, api_secret)
current_prices = {}
active_trades = {}
# إدارة المحفظة 
balance = 101  # الرصيد المبدئي للبوت
investment=10 # حجم كل صفقة
base_profit_target=0.0032 # نسبة الربح
base_stop_loss=0.001 # نسبة الخسارة
timeout=10 # وقت انتهاء وقت الصفقة
commission_rate = 0.001 # نسبة العمولة للمنصة
excluded_symbols = set()  # قائمة العملات المستثناة بسبب أخطاء متكررة

# ملف CSV لتسجيل التداولات
csv_file = 'trades_log.csv'
if not os.path.exists(csv_file):
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['الرمز', 'الكمية', 'السعر الابتدائي', 'سعر الهدف', 'سعر الإيقاف', 'الوقت', 'النتيجة', 'الرصيد المتبقي'])


def adjust_balance(amount, action="buy"):
    """
    ضبط الرصيد بناءً على العملية (شراء أو بيع) وخصم العمولة.
    
    :param amount: مبلغ الصفقة.
    :param commission_rate: نسبة العمولة.
    :param action: نوع العملية - "buy" أو "sell".
    :return: الرصيد بعد التعديل.
    """
    global balance, commission_rate
    commission = amount * commission_rate
    if action == "buy":
        balance -= (amount + commission)  # خصم المبلغ + العمولة
    elif action == "sell":
        balance += amount - commission  # إضافة المبلغ بعد خصم العمولة
    
    print(f"تم تحديث الرصيد بعد {action} - الرصيد المتبقي: {balance}")
    return balance

# تحميل الصفقات المفتوحة من المحفظة
def load_open_trades_from_portfolio():
    global balance
    account_info = client.get_account()
    for asset in account_info['balances']:
        if float(asset['free']) > 0:
            symbol = asset['asset'] + 'USDC'
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
                # balance -= quantity * price  # تعديل الرصيد بناءً على الصفقات الحالية
            except Exception as e:
                print(f"خطأ في تحميل الصفقة لـ {symbol}: {e}")


# تحميل الصفقات المفتوحة من المحفظة
def load_open_trades_from_portfolio():
    global balance, commission_rate, base_profit_target,base_stop_loss
    account_info = client.get_account()
    for asset in account_info['balances']:
        if 'BNB' in str(asset['asset']):
            continue
        if float(asset['free']) > 0:
            symbol = asset['asset'] + 'USDC'
            try:
                price = float(client.get_symbol_ticker(symbol=symbol)['price'])
                quantity = float(asset['free'])
                avg_volatility = statistics.stdev([float(kline[4]) for kline in client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_30MINUTE, limit=20)])
                # تضمين العمولات وتعديل أهداف الربح والخسارة
                # commission_rate = 0.001  # 0.1% assuming BNB discount is active
                profit_target = base_profit_target + avg_volatility + commission_rate
                stop_loss = base_stop_loss + avg_volatility * 0.5 + commission_rate
                target_price = price * (1 + profit_target)
                stop_price = price * (1 - stop_loss)
                quantity = adjust_quantity(symbol, investment / price)
                # commission_rate = 0.001
                target_price =commission_rate+ price * 1.002  # هدف ربح سريع
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
                # balance -= quantity * price  # تعديل الرصيد بناءً على الصفقات الحالية
            except Exception as e:
                print(f"خطأ في تحميل الصفقة لـ {symbol}: {e}")


# دالة الحصول على أفضل العملات بناءً على حجم التداول واستقرار السوق ونسبة الربح المستهدفة
def get_top_symbols(limit=10, profit_target=0.003):
    tickers = client.get_ticker()
    sorted_tickers = sorted(tickers, key=lambda x: float(x['quoteVolume']), reverse=True)
    top_symbols = []
    for ticker in sorted_tickers:
        if ticker['symbol'].endswith("USDC") and ticker['symbol'] not in excluded_symbols:
            try:
                klines = client.get_klines(symbol=ticker['symbol'], interval=Client.KLINE_INTERVAL_5MINUTE, limit=30)
                closing_prices = [float(kline[4]) for kline in klines]
                stddev = statistics.stdev(closing_prices)
                
                avg_price = sum(closing_prices) / len(closing_prices)
                volatility_ratio = stddev / avg_price

                if stddev < 0.03 and volatility_ratio >= profit_target:
                    top_symbols.append(ticker['symbol'])
                    print(f"تم اختيار العملة {ticker['symbol']} بنسبة تذبذب {volatility_ratio:.4f}")
                
                if len(top_symbols) >= limit:
                    break
            except BinanceAPIException as e:
                print(f"خطأ في جلب بيانات {ticker['symbol']}: {e}")
                excluded_symbols.add(ticker['symbol'])
    return top_symbols

# دالة ضبط الكمية بناءً على دقة السوق
def adjust_quantity(symbol, quantity):
    step_size = get_lot_size(symbol)
    if step_size is None:
        return quantity
    precision = int(round(-math.log(step_size, 10), 0))
    return round(quantity, precision)

def get_lot_size(symbol):
    exchange_info = client.get_symbol_info(symbol)
    for filter in exchange_info['filters']:
        if filter['filterType'] == 'LOT_SIZE':
            step_size = float(filter['stepSize'])
            return step_size
    return None


def check_bnb_balance(min_bnb_balance=0.001):  # تقليل الحد الأدنى المطلوب
    # تحقق من رصيد BNB للتأكد من تغطية الرسوم
    account_info = client.get_asset_balance(asset='BNB')
    if account_info:
        bnb_balance = float(account_info['free'])
        return bnb_balance >= min_bnb_balance
    return False

def open_trade_with_dynamic_target(symbol, investment=2.5, base_profit_target=0.002, base_stop_loss=0.0005, timeout=3):
    global balance, commission_rate
    price = float(client.get_symbol_ticker(symbol=symbol)['price'])
    avg_volatility = statistics.stdev([float(kline[4]) for kline in client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_15MINUTE, limit=20)])
    
    # تضمين العمولات وتعديل أهداف الربح والخسارة
    profit_target = base_profit_target + avg_volatility + commission_rate
    stop_loss = base_stop_loss + avg_volatility * 0.5 + commission_rate
    target_price = price * (1 + profit_target)
    stop_price = price * (1 - stop_loss)
    quantity = adjust_quantity(symbol, investment / price)
    notional_value = quantity * price

    if balance < investment:
        print(f"{datetime.now()} - الرصيد الحالي غير كافٍ لفتح صفقة جديدة.")
        return

    if not check_bnb_balance():
        print(f"{datetime.now()} - الرصيد غير كافٍ من BNB لتغطية الرسوم. يرجى إيداع BNB.")
        return

    # تنفيذ أمر شراء
    try:
        order = client.order_market_buy(symbol=symbol, quantity=quantity)
        commission = investment * commission_rate
        # تخزين تفاصيل الصفقة في active_trades
        active_trades[symbol] = {
            'quantity': quantity,
            'initial_price': price,
            'target_price': target_price,
            'stop_price': stop_price,
            'start_time': time.time(),
            'timeout': timeout * 60,
            'investment': investment - commission
        }
        # balance -= investment
        adjust_balance(investment, action="buy")
        print(f"{datetime.now()} - تم فتح صفقة شراء لـ {symbol} بسعر {price}, بهدف {target_price} وإيقاف خسارة عند {stop_price}")
    except BinanceAPIException as e:
        if 'NOTIONAL' in str(e) or 'Invalid symbol' in str(e):
                excluded_symbols.add(symbol)
        print(f"خطأ في فتح الصفقة لـ {symbol}: {e}")

import math

def sell_trade(symbol, trade_quantity):
    
    try:
        # الحصول على الكمية المتاحة في المحفظة
        balance_info = client.get_asset_balance(asset=symbol.replace("USDC", ""))
        available_quantity = float(balance_info['free'])
        
        # التأكد من أن الكمية تلبي الحد الأدنى لـ LOT_SIZE وتعديل الدقة المناسبة
        step_size = get_lot_size(symbol)
        if available_quantity < step_size:
            print(f"{symbol} - الكمية المتاحة للبيع ({available_quantity}) أقل من الحد الأدنى المطلوب لـ LOT_SIZE ({step_size}).")
            return 0

        # ضبط الدقة للكمية حسب LOT_SIZE
        precision = int(round(-math.log(step_size, 10), 0))
        adjusted_quantity = round(math.floor(available_quantity / step_size) * step_size, precision)

        if adjusted_quantity < step_size:
            print(f"{symbol} - الكمية بعد التقريب ({adjusted_quantity}) لا تزال أقل من الحد الأدنى المطلوب لـ LOT_SIZE ({step_size}).")
            return 0

        # تنفيذ أمر البيع
        client.order_market_sell(symbol=symbol, quantity=adjusted_quantity)
        # sale_amount = adjusted_quantity * price
        # adjust_balance(sale_amount, commission_rate, action="sell")

        print(f"تم تنفيذ عملية البيع لـ {symbol} بكمية {adjusted_quantity}")
        return adjusted_quantity
    except BinanceAPIException as e:
        print(f"خطأ في بيع {symbol}: {e}")
        return 0


def check_trade_conditions():
    global balance
    for symbol, trade in list(active_trades.items()):
        try:
            current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
            current_prices[symbol] = current_price
        except BinanceAPIException as e:
            print(f"خطأ في تحديث السعر لـ {symbol}: {e}")
            if 'NOTIONAL' in str(e) or 'Invalid symbol' in str(e):
                excluded_symbols.add(symbol)
            continue

        result = None
        sold_quantity = 0
        total_sale = 0
        try:
            if current_price >= trade['target_price']:
                sold_quantity = sell_trade(symbol, trade['quantity'])
                result = 'ربح' if sold_quantity > 0 else None
            elif current_price <= trade['stop_price']:
                sold_quantity = sell_trade(symbol, trade['quantity'])
                result = 'خسارة' if sold_quantity > 0 else None
            elif time.time() - trade['start_time'] >= trade['timeout']:
                sold_quantity = sell_trade(symbol, trade['quantity'])
                result = 'انتهاء المهلة' if sold_quantity > 0 else None
                

            # إذا تم تنفيذ عملية البيع بنجاح، تحديث الرصيد مع خصم العمولة
            if result and sold_quantity > 0:
                total_sale = sold_quantity * current_price
                commission = total_sale * commission_rate
                net_sale = total_sale - commission  # صافي البيع بعد خصم العمولة
                # تحديث الرصيد بناءً على نوع العملية (البيع)
                adjust_balance(total_sale, action="sell")

                print(f"{datetime.now()} - تم {result} الصفقة لـ {symbol} عند السعر {current_price}")
                with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow([symbol, sold_quantity, trade['initial_price'], trade['target_price'], trade['stop_price'], datetime.now(), result, balance])
                del active_trades[symbol]

        except BinanceAPIException as e:
            print(f"خطأ في بيع {symbol}: {e}")
            if 'NOTIONAL' in str(e) or 'Invalid symbol' in str(e):
                excluded_symbols.add(symbol)
            continue

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
                print(f"تم تحديث السعر لعملة {symbol}: {current_prices[symbol]}")
                if symbol not in active_trades:
                    open_trade_with_dynamic_target(symbol,investment=investment,base_profit_target=base_profit_target,base_stop_loss=base_stop_loss,timeout=timeout)
            except BinanceAPIException as e:
                print(f"خطأ في تحديث السعر لـ {symbol}: {e}")
                if 'NOTIONAL' in str(e) or 'Invalid symbol' in str(e):
                    excluded_symbols.add(symbol)  # Exclude symbols causing frequent errors

# مراقبة حالة الصفقات المغلقة
def monitor_trades():
    while True:
        check_trade_conditions()

# load_open_trades_from_portfolio()


# load_open_trades_from_portfolio()
# بدء التحديث الدوري لقائمة العملات
symbols_to_trade = get_top_symbols(10, profit_target=0.003)
symbol_update_thread = threading.Thread(target=update_symbols_periodically, args=(900,))
symbol_update_thread.start()

# تشغيل خيوط تحديث الأسعار ومراقبة الصفقات
price_thread = threading.Thread(target=update_prices)
trade_thread = threading.Thread(target=monitor_trades)
price_thread.start()
trade_thread.start()

print(f"تم بدء تشغيل البوت في {datetime.now()}")
