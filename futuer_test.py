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
import requests
from config import API_KEY, API_SECRET,Settings
# import talib  # مكتبة تحليل فني



session = requests.Session()

session.headers.update({'timeout': '90'})  # مثال، قد لا تكون فعّالة

# إعداد مفاتيح API الخاصة بك


api_key = '78a36f71dd1472372e97ba6dbdfc6455028d67d13bab0084c33c29230bb2337b'
api_secret = '160e0b56bac4dd7be0e2fe57c2e242d912b1b511ae6e59315670247b765b03bf'


# api_key = 'tweOjH1Keln44QaxLCr3naevRPgF3j3sYuOpaAg9B7nUT74MyURemvivEUcihfkt'
# api_secret = 'XLlku378D8aZzYg9JjOTtUngA8Q73xBCyy7jGVbqRYSoEICsGBfWC0cIsRptLHxb'

# تهيئة الاتصال ببايننس واستخدام Testnet
client = Client(api_key, api_secret,testnet=True)
# client.API_URL = 'https://testnet.binance.vision/api'


# client = Client(api_key, api_secret)
current_prices = {}
active_trades = {}
# إدارة المحفظة 0
balance = 1000  # الرصيد المبدئي للبوت
investment=10 # حجم كل صفقة
base_profit_target=0.004 # نسبة الربح
# base_profit_target=0.005 # نسبة الربح
# base_stop_loss=0.008 # نسبة الخسارة
base_stop_loss=0.0065 # نسبة الخسارة
timeout=30 # وقت انتهاء وقت الصفقة
commission_rate = 0.002 # نسبة العمولة للمنصة
excluded_symbols = set()  # قائمة العملات المستثناة بسبب أخطاء متكررة
bot_settings=Settings()
symbols_to_trade =[]
last_trade_time = {}
klines_interval=Client.KLINE_INTERVAL_5MINUTE
klines_limit=12
top_symbols=[]
count_top_symbols=30
leverage=3
marginType="ISOLATED"


# ملف CSV لتسجيل التداولات
csv_file = 'update_trades_log_test_futuers.csv'
if not os.path.exists(csv_file):
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['الرمز', 'الكمية', 'السعر الابتدائي', 'سعر الهدف', 'سعر الإيقاف', 'وقت الاغلاق', 'وقت الفتح','نسبة الربح','نسبة الخسارة','المهلة', 'الربح','النتيجة', 'الرصيد المتبقي'])


# حساب RSI
def calculate_rsi(prices, period=14):
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [d for d in deltas if d > 0]
    losses = [-d for d in deltas if d < 0]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_bollinger_bands(prices, period=20, multiplier=2):
    sma = sum(prices[-period:]) / period  # Simple Moving Average (SMA)
    std_dev = statistics.stdev(prices[-period:])  # Standard deviation for last 'period' prices
    upper_band = sma + (std_dev * multiplier)
    lower_band = sma - (std_dev * multiplier)
    return upper_band, lower_band


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
        balance -= (amount -( commission * 0.5))  # خصم المبلغ + العمولة
    elif action == "sell":
        balance += amount - (commission * 0.5) # إضافة المبلغ بعد خصم العمولة
    
    print(f"تم تحديث الرصيد بعد {action} -بمبلغ {amount} - الرصيد المتبقي: {balance}")
    if balance < investment:
        print(f"{datetime.now()} - الرصيد الحالي لم يعُد كافٍ لفتح صفقة جديدة.")

    return balance


# ضبط الرصيد بعد عملية تداول
# def adjust_balance(amount, action="buy"):
#     global balance
#     commission = amount * commission_rate
#     balance += (amount - commission * 0.5) if action == "sell" else -amount + (commission * 0.5)
#     print(f"تم تحديث الرصيد بعد {action} - الرصيد المتبقي: {balance}")
#     return balance

# تحميل الصفقات المفتوحة من المحفظة
def load_open_trades_from_portfolio():
    global balance, commission_rate, base_profit_target,base_stop_loss
    account_info = client.get_account()
    for asset in account_info['balances']:
        if 'BNB' in str(asset['asset']):
            continue
        if float(asset['free']) > 0:
            symbol = asset['asset'] + 'USDT'
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



def check_bnb_balance(min_bnb_balance=0.0001):  # تقليل الحد الأدنى المطلوب
    # تحقق من رصيد BNB للتأكد من تغطية الرسوم
    account_info = client.get_asset_balance(asset='BNB')
    if account_info:
        bnb_balance = float(account_info['free'])
        return bnb_balance >= min_bnb_balance
    return False


# تعديل دالة اختيار أفضل العملات لتشمل مؤشر RSI
def get_top_symbols(limit=20, profit_target=0.01, rsi_threshold=70):
    tickers = client.get_ticker()
    sorted_tickers = sorted(tickers, key=lambda x: float(x['quoteVolume']), reverse=True)
    top_symbols = []
    
    for ticker in sorted_tickers:
        if ticker['symbol'].endswith("USDT") and ticker['symbol'] not in excluded_symbols and not 'BTTC' in str(ticker['symbol']):
        # if ticker['symbol'].endswith("USDT") and ticker['symbol'] not in excluded_symbols and not 'BTTC' in str(ticker['symbol']):
            try:
                klines = client.get_klines(symbol=ticker['symbol'], interval=klines_interval, limit=klines_limit)
                closing_prices = [float(kline[4]) for kline in klines]
                stddev = statistics.stdev(closing_prices)
                
                # حساب مؤشر RSI
                rsi = calculate_rsi(closing_prices)
                
                # اختيار العملة بناءً على التذبذب ومؤشر RSI
                avg_price = sum(closing_prices) / len(closing_prices)
                volatility_ratio = stddev / avg_price

                if stddev < 0.04 and volatility_ratio >= profit_target and rsi < rsi_threshold:
                    top_symbols.append(ticker['symbol'])
                    print(f"تم اختيار العملة {ticker['symbol']} بنسبة تذبذب {volatility_ratio:.4f} و RSI {rsi:.2f}")
                
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
    precision = int(-math.log10(step_size))  # حساب دقة الكمية بناءً على step_size
    adjusted_quantity = round(quantity, precision)
    print(f"Adjusting quantity for {symbol}: {quantity} -> {adjusted_quantity}")
    return adjusted_quantity



def get_lot_size(symbol):
    exchange_info = client.get_symbol_info(symbol)
    for filter in exchange_info['filters']:
        if filter['filterType'] == 'LOT_SIZE':
            step_size = float(filter['stepSize'])
            print(f"Step size for {symbol}: {step_size}")
            return step_size
    print(f"No LOT_SIZE filter found for {symbol}")
    return None


# def open_trade_with_dynamic_target(symbol, investment=2.5, base_profit_target=0.002, base_stop_loss=0.0005, timeout=3):
#     global balance, commission_rate
#     # trading_status= bot_settings.trading_status()
#     # if trading_status =="0":
#     #     print("the trading is of can't open more trad")
#     #     return

#     price = float(client.get_symbol_ticker(symbol=symbol)['price'])
#     avg_volatility = statistics.stdev([float(kline[4]) for kline in client.get_klines(symbol=symbol, interval=klines_interval, limit=klines_limit)])
    
#     # تضمين العمولات وتعديل أهداف الربح والخسارة
#     profit_target = base_profit_target + avg_volatility + commission_rate
#     # print(f"profit_target: {profit_target}")
#     stop_loss = base_stop_loss + avg_volatility * 0.5 + commission_rate
#     # print(f"stop_loss: {stop_loss}")
#     target_price = price * (1 + profit_target)
#     stop_price = price * (1 - stop_loss)
#     quantity = adjust_quantity(symbol, investment / price)
#     notional_value = quantity * price

#     if balance < investment:
#         print(f"{datetime.now()} - الرصيد الحالي غير كافٍ لفتح صفقة جديدة.")
#         return

#     if not check_bnb_balance():
#         print(f"{datetime.now()} - الرصيد غير كافٍ من BNB لتغطية الرسوم. يرجى إيداع BNB.")
#         return

#     # تنفيذ أمر شراء
#     try:
#         order = client.order_market_buy(symbol=symbol, quantity=quantity)
#         commission = investment * commission_rate
#         # تخزين تفاصيل الصفقة في active_trades
#         active_trades[symbol] = {
#             'quantity': quantity,
#             'initial_price': price,
#             'target_price': target_price,
#             'stop_price': stop_price,
#             'start_time': time.time(),
#             'timeout': timeout * 60,
#             'investment': investment - commission
#         }
#         # balance -= investment
#         adjust_balance(investment, action="buy")
#         print(f"{datetime.now()} - تم فتح صفقة شراء لـ {symbol} بسعر {price}, بهدف {target_price} وإيقاف خسارة عند {stop_price}")
#     except BinanceAPIException as e:
#         if 'NOTIONAL' in str(e) or 'Invalid symbol' in str(e) or 'Market is closed' in str(e):
#                 excluded_symbols.add(symbol)
#         print(f"خطأ في فتح الصفقة لـ {symbol}: {e}")


# التحقق مما إذا كان يمكن التداول على الرمز بناءً على فترة الانتظار
def can_trade(symbol):
    if symbol in last_trade_time and time.time() - last_trade_time[symbol] < 300:  # انتظار 5 دقائق
        print(f"تخطى التداول على {symbol} - لم تمر 5 دقائق منذ آخر صفقة.")
        return False
    return True

# def should_open_trade(prices):
#     rsi = calculate_rsi(prices)
#     if rsi > 70:
#         return False  # سوق مشبع بالشراء (لا تفتح صفقة شراء)
#     elif rsi < 30:
#         return True  # سوق مشبع بالبيع (افتح صفقة شراء)
#     return False

def should_open_trade(prices):
    """
    Determine whether to open a trade and on which side (LONG/SHORT).
    Returns:
        - 'LONG': If conditions for a buy trade are met.
        - 'SHORT': If conditions for a sell trade are met.
        - None: If no trade should be opened.
    """
    rsi = calculate_rsi(prices)
    upper_band, lower_band = calculate_bollinger_bands(prices)
    current_price = prices[-1]

    # LONG Trade Conditions (Buy Side):
    # - RSI is below 20 (Oversold condition).
    # - Current price is below the lower Bollinger Band.
    if rsi < 30 :
        return "LONG"

    # SHORT Trade Conditions (Sell Side):
    # - RSI is above 70 (Overbought condition).
    # - Current price is above the upper Bollinger Band.
    if rsi > 70 :
        return "SHORT"
    # if rsi < 20 or current_price < lower_band:
    #     return "LONG"

    # # SHORT Trade Conditions (Sell Side):
    # # - RSI is above 70 (Overbought condition).
    # # - Current price is above the upper Bollinger Band.
    # if rsi > 70 or current_price > upper_band:
    #     return "SHORT"

    # No trade conditions met
    return None


# Determine if a Bollinger Bands reversal condition is met for opening trades
def should_open_trade_bollinger(prices):
    upper_band, lower_band = calculate_bollinger_bands(prices)
    current_price = prices[-1]
    
    # Enter long trade if the price crosses below the lower Bollinger Band
    if current_price < lower_band:
        return True  # Indicates a potential buying signal
    # Avoid trade if the price is at the upper Bollinger Band (indicating overbought conditions)
    elif current_price > upper_band:
        return False  # Indicates avoiding trade
    return False


def is_symbol_tradable(symbol):
    exchange_info = client.futures_exchange_info()
    for s in exchange_info['symbols']:
        if s['symbol'] == symbol and s['status'] == "TRADING":
            return True
    excluded_symbols.add(symbol)
    return False




def get_exchange_info():
    return client.futures_exchange_info()

def get_symbol_info(symbol):
    exchange_info = get_exchange_info()
    for s in exchange_info['symbols']:
        if s['symbol'] == symbol:
            return s
    return None

def get_step_size(symbol):
    info = get_symbol_info(symbol)
    for f in info['filters']:
        if f['filterType'] == 'LOT_SIZE':
            return float(f['stepSize'])

def get_tick_size(symbol):
    info = get_symbol_info(symbol)
    for f in info['filters']:
        if f['filterType'] == 'PRICE_FILTER':
            return float(f['tickSize'])

def get_price_limits(symbol):
    info = get_symbol_info(symbol)
    for f in info['filters']:
        if f['filterType'] == 'PERCENT_PRICE':
            return float(f['minPrice']), float(f['maxPrice'])


def adjust_precision(value, step_size):
    # Adjust the value to match the step size
    precision = len(str(step_size).split(".")[1]) if "." in str(step_size) else 0
    return float(f"{{:.{precision}f}}".format(value))


def validate_price(price, min_price, max_price):
    if price < min_price:
        return min_price
    elif price > max_price:
        return max_price
    return price


def open_trade_with_dynamic_target_futures(
    symbol, investment=2.5, leverage=10, base_profit_target=0.002, base_stop_loss=0.0005, timeout=30
):
    global balance, commission_rate

    if balance < investment:
        print(f"{datetime.now()} - {symbol} - الرصيد الحالي غير كافٍ لفتح صفقة جديدة.")
        return

    if not is_symbol_tradable(symbol):
        print(f"{datetime.now()} - {symbol} غير متاح للتداول في الوقت الحالي.")
        return

    try:
        price = float(client.get_symbol_ticker(symbol=symbol)['price'])
        klines = client.get_klines(symbol=symbol, interval=klines_interval, limit=8)
        closing_prices = [float(kline[4]) for kline in klines]
        avg_volatility = statistics.stdev(closing_prices)
    except BinanceAPIException as e:
        print(f"خطأ في جلب بيانات {symbol}: {e}")
        return

    if not should_open_trade(closing_prices):
        print(f"{datetime.now()} - لا توجد إشارات تداول لفتح صفقة لـ {symbol} في الوقت الحالي.")
        return

    profit_target = base_profit_target + avg_volatility + commission_rate
    stop_loss = base_stop_loss + avg_volatility * 0.5 + commission_rate
    target_price = price * (1 + profit_target)
    stop_price = price * (1 - stop_loss)

    try:
        quantity = adjust_quantity(symbol, (investment * leverage) / price)
    except Exception as e:
        print(f"خطأ في حساب الكمية لـ {symbol}: {e}")
        return

    try:
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
    except BinanceAPIException as e:
        print(f"خطأ في تعيين الرافعة المالية لـ {symbol}: {e}")
        return

    # فحص الفرق بين السعر المطلوب والسعر الحالي
    # price_diff = abs(price - target_price) / price
    # if price_diff > 0.01:  # 0.2% فرق مقبول، يمكنك تعديل هذا الرقم
    #     print(f"{datetime.now()} - فرق السعر كبير جدًا لـ {symbol}. سيتم تأجيل الصفقة.")
    #     return

    trade_side = "LONG" if should_open_trade(closing_prices) else "SHORT"

    try:
        order = client.futures_create_order(
            symbol=symbol,
            side="BUY" if trade_side == "LONG" else "SELL",
            type="LIMIT",
            price=target_price,
            quantity=quantity,
            marginType=marginType,
            positionSide=trade_side,
            timeInForce="GTC"
        )
        print(f"{datetime.now()} - تم فتح صفقة {trade_side} لـ {symbol} بسعر {price:.4f}")
        print(f"الهدف: {target_price:.4f}, وقف الخسارة: {stop_price:.4f}")
    except BinanceAPIException as e:
        print(f"خطأ في فتح الصفقة لـ {symbol}: {e}")


def close_trade_futures(symbol, position_side):
    """
    Close a specific position (LONG or SHORT) in futures trading.
    """
    try:
        current_price = float(client.futures_symbol_ticker(symbol=symbol)['price'])

        # Close the position
        client.futures_create_order(
            symbol=symbol,
            side="SELL" if position_side == "LONG" else "BUY",
            type="MARKET",
            quantity=active_trades[f"{symbol}_{position_side}"]['quantity'],
            positionSide=position_side
        )
        print(f"تم إغلاق الصفقة {position_side} لـ {symbol} بسعر {current_price}")
        del active_trades[f"{symbol}_{position_side}"]
    except BinanceAPIException as e:
        print(f"خطأ في إغلاق الصفقة {position_side} لـ {symbol}: {e}")


def check_trade_conditions_futures_both_sides():
    """
    Monitor and manage conditions for both LONG and SHORT positions.
    """
    global balance
    for key, trade in list(active_trades.items()):
        symbol, position_side = key.rsplit("_", 1)
        try:
            current_price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
        except BinanceAPIException as e:
            print(f"خطأ في تحديث السعر لـ {symbol}: {e}")
            continue

        # Check for target, stop loss, or timeout conditions
        result = None
        try:
            if position_side == "LONG":
                if current_price >= trade['target_price']:
                    close_trade_futures(symbol, "LONG")
                    result = 'ربح (LONG)'
                elif current_price <= trade['stop_price']:
                    close_trade_futures(symbol, "LONG")
                    result = 'خسارة (LONG)'
            elif position_side == "SHORT":
                if current_price <= trade['target_price']:
                    close_trade_futures(symbol, "SHORT")
                    result = 'ربح (SHORT)'
                elif current_price >= trade['stop_price']:
                    close_trade_futures(symbol, "SHORT")
                    result = 'خسارة (SHORT)'

            # Handle timeout condition
            if time.time() - trade['start_time'] >= trade['timeout']:
                close_trade_futures(symbol, position_side)
                result = f'انتهاء المهلة ({position_side})'

            # if result:
            if result :
                total_sale = trade['quantity'] * current_price
                commission = total_sale * commission_rate
                net_sale = total_sale - commission
                earnings = trade['quantity'] * current_price - trade['initial_price'] * trade['quantity']
                adjust_balance(total_sale, action="sell")
                print(f"{datetime.now()} - تم {result} الصفقة لـ {symbol} عند السعر {current_price} وربح {earnings}")
                with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    start_time=trade['start_time']
                    
                    writer.writerow([symbol, trade['quantity'], trade['initial_price'], trade['target_price'], trade['stop_price'], datetime.now(),datetime.fromtimestamp(trade['start_time']), base_profit_target, base_stop_loss, str(timeout) + 'm', earnings, result, balance])
                # del active_trades[symbol]
                print(f"{datetime.now()} - تم {result} لـ {symbol} عند السعر {current_price}")
        except BinanceAPIException as e:
            print(f"خطأ في إدارة الصفقة {position_side} لـ {symbol}: {e}")


# تحديث قائمة الرموز بشكل دوري
def update_symbols_periodically(interval=600):
    global symbols_to_trade
    while True:
        symbols_to_trade = get_top_symbols(count_top_symbols)
        print(f"{datetime.now()} - تم تحديث قائمة العملات للتداول: {symbols_to_trade}")
        time.sleep(interval)

# مراقبة تحديث الأسعار وفتح الصفقات
def update_prices():
    global symbols_to_trade

    while True:
        for symbol in symbols_to_trade:
            if symbol in excluded_symbols:
                continue
            try:
                current_prices[symbol] = float(client.get_symbol_ticker(symbol=symbol)['price'])
                # print(f"تم تحديث السعر لعملة {symbol}: {current_prices[symbol]}")
                if symbol not in active_trades:
                    open_trade_with_dynamic_target_futures(symbol,investment=investment,leverage=leverage,base_profit_target=base_profit_target,base_stop_loss=base_stop_loss,timeout=timeout)
                    # open_trade_with_dynamic_target_futures_both_sides("BTCUSDT", investment=10, leverage=20, base_profit_target=0.005, base_stop_loss=0.001)

            except BinanceAPIException as e:
                print(f"خطأ في تحديث السعر لـ {symbol}: {e}")
                if 'NOTIONAL' in str(e) or 'Invalid symbol' in str(e):
                    excluded_symbols.add(symbol)  # Exclude symbols causing frequent errors
                    time.sleep(0.1)

# مراقبة حالة الصفقات المغلقة
def monitor_trades():
    while True:
        check_trade_conditions_futures_both_sides()
        time.sleep(0.1)


# load_open_trades_from_portfolio()


# load_open_trades_from_portfolio()
# بدء التحديث الدوري لقائمة العملات
def run_bot():
    global symbols_to_trade

    symbols_to_trade = get_top_symbols(5)
    symbol_update_thread = threading.Thread(target=update_symbols_periodically, args=(600,))
    symbol_update_thread.start()

    # تشغيل خيوط تحديث الأسعار ومراقبة الصفقات
    price_thread = threading.Thread(target=update_prices)
    trade_thread = threading.Thread(target=monitor_trades)
    price_thread.start()
    trade_thread.start()

    print(f"تم بدء تشغيل البوت في {datetime.now()}")
    
if __name__ == "__main__":
    if bot_settings.bot_status() != '0':
            run_bot()
            
            
    print("Bot is turn of")
        



