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
import numpy as np
import pandas as pd
import decimal
import ta
# import talib
# # import talib  # مكتبة تحليل فني
# talib.atexit.register

session = requests.Session()

session.headers.update({'timeout': '90'})  # مثال، قد لا تكون فعّالة

# إعداد مفاتيح API الخاصة بك


api_key = 'of6qt1T1MpGvlgma1qxwFTLdrGNNVsMj0fKf8LZy1sMf3OqTrwHC7BCRIkgsSsda'
api_secret = 'MZuALJiqyWMoQ0WkPE6tqWdToGLTHLsap5m95qhPIDtizy1FPD0TQBXNvyQBhgFf'


# api_key = 'tweOjH1Keln44QaxLCr3naevRPgF3j3sYuOpaAg9B7nUT74MyURemvivEUcihfkt'
# api_secret = 'XLlku378D8aZzYg9JjOTtUngA8Q73xBCyy7jGVbqRYSoEICsGBfWC0cIsRptLHxb'

# تهيئة الاتصال ببايننس واستخدام Testnet
client = Client(api_key, api_secret,requests_params={'timeout':90})
# client.API_URL = 'https://testnet.binance.vision/api'


# client = Client(api_key, api_secret)
current_prices = {}
active_trades = {}
# إدارة المحفظة 0
balance = 25 # الرصيد المبدئي للبوت
investment=6 # حجم كل صفقة
base_profit_target=0.005 # نسبة الربح
# base_profit_target=0.005 # نسبة الربح
base_stop_loss=0.1 # نسبة الخسارة
# base_stop_loss=0.000 # نسبة الخسارة
timeout=60 # وقت انتهاء وقت الصفقة
commission_rate = 0.002 # نسبة العمولة للمنصة
excluded_symbols = set()  # قائمة العملات المستثناة بسبب أخطاء متكررة
bot_settings=Settings()
symbols_to_trade =[]
last_trade_time = {}
klines_interval=Client.KLINE_INTERVAL_3MINUTE
klines_limit=14
top_symbols=[]
count_top_symbols=70
analize_period=8

start_date='3 hours ago UTC'


black_list=[
    'SANDUSDT',
    'BTTCUSDT',
    'XLMUSDT',
    # 'PNUTUSDT',
    # 'NEIROUSDT',
    'POWRUSDT',
    # 'NEIROUSDT',
    # 'FTMUSDT',
    'KDAUSDT',
    'POLYXUSDT',
    'SCUSDT',
    'ZRXUSDT',
]

white_list=[
    
]

# ملف CSV لتسجيل التداولات
csv_file = 'new_trades_log_test.csv'
if not os.path.exists(csv_file):
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['الرمز', 'الكمية', 'السعر الابتدائي', 'سعر الهدف', 'سعر الإيقاف', 'وقت الاغلاق', 'وقت الفتح','نسبة الربح','نسبة الخسارة','المهلة', 'الربح','النتيجة', 'الرصيد المتبقي'])



def get_klines(symbol, interval, start_date):
    # klines = client.get_historical_klines(symbol, interval, start_date)
    return  client.get_historical_klines(symbol, interval, start_date)


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
def get_top_symbols(limit=20, profit_target=0.007, rsi_threshold=70):
    tickers = client.get_ticker()
    sorted_tickers = sorted(tickers, key=lambda x: float(x['quoteVolume']), reverse=True)
    top_symbols = []
    
    for ticker in sorted_tickers:
        if ticker['symbol'].endswith("USDT") and ticker['symbol'] not in excluded_symbols and ticker['symbol'] not in black_list :
        # if ticker['symbol'].endswith("USDT") and ticker['symbol'] not in excluded_symbols and not 'BTTC' in str(ticker['symbol']):
            try:
                klines = client.get_klines(symbol=ticker['symbol'], interval=klines_interval, limit=klines_limit)
                closing_prices = [float(kline[4]) for kline in klines]
                stddev = statistics.stdev(closing_prices)
                
                # حساب مؤشر RSI
                rsi = calculate_rsi(closing_prices,period=klines_limit)
                
                # اختيار العملة بناءً على التذبذب ومؤشر RSI
                avg_price = sum(closing_prices) / len(closing_prices)
                volatility_ratio = stddev / avg_price

                if stddev < 0.04 and volatility_ratio >= profit_target :
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
    # Adjust quantity to be a multiple of step_size
    precision = decimal.Decimal(str(step_size))
    quantity = decimal.Decimal(str(quantity))
    return float((quantity // precision) * precision)

def get_lot_size(symbol):
    exchange_info = client.get_symbol_info(symbol)
    for filter in exchange_info['filters']:
        if filter['filterType'] == 'LOT_SIZE':
            step_size = float(filter['stepSize'])
            return step_size
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
    if symbol in last_trade_time and time.time() - last_trade_time[symbol] < 30:  # انتظار 5 دقائق
        # print(f"تخطى التداول على {symbol} - لم تمر 5 دقائق منذ آخر صفقة.")
        return False
    return True


def bol_h(df):
    return ta.volatility.BollingerBands(pd.Series(df)).bollinger_hband() 

def bol_l(df):
    return ta.volatility.BollingerBands(pd.Series(df)).bollinger_lband() 




# def should_open_trade(prices):
#     rsi = calculate_rsi(prices)
#     if rsi > 70:
#         return False  # سوق مشبع بالشراء (لا تفتح صفقة شراء)
#     elif rsi < 30:
#         return True  # سوق مشبع بالبيع (افتح صفقة شراء)
#     return False

def should_open_trade(prices,period=14):
    rsi = calculate_rsi(prices,period=period)
    # upper_band, lower_band = calculate_bollinger_bands(prices)
    # current_price = prices[-1]

    # RSI condition: Overbought (RSI > 70) signals a possible sell, Oversold (RSI < 30) signals a buy
    # if rsi > 70 or current_price > upper_band:
    #     return False  # Avoid opening a trade in overbought conditions

    # if rsi < 30 or current_price < lower_band:
    #     return True  # Open a buy trade in oversold conditions or if price crosses below lower Bollinger Band

    # return False  # No trade
    
    
    if rsi > 50 :
        return False  # Avoid opening a trade in overbought conditions

    if rsi > 25  and rsi < 45:
        return True  # Open a buy trade in oversold conditions or if price crosses below lower Bollinger Band

    return False  # No trade



def should_close_trade(prices,period=14):
    
    rsi = calculate_rsi(prices,period=period)
    # upper_band, lower_band = calculate_bollinger_bands(prices)
    # current_price = prices[-1]

    # RSI condition: Overbought (RSI > 70) signals a possible sell, Oversold (RSI < 30) signals a buy
    # if rsi > 70 or current_price > upper_band:
    #     return False  # Avoid opening a trade in overbought conditions

    # if rsi < 30 or current_price < lower_band:
    #     return True  # Open a buy trade in oversold conditions or if price crosses below lower Bollinger Band

    # return False  # No trade
    
    
    if rsi > 50 or rsi < 15 :
        return True  # Avoid opening a trade in overbought conditions

    if rsi > 27  and rsi < 45:
        return False  # Open a buy trade in oversold conditions or if price crosses below lower Bollinger Band

    return False  # No trade


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


def check_btc_price():
    klines = client.get_klines(symbol="BTCUSDT", interval=klines_interval, limit=10)
    closing_prices = [float(kline[4]) for kline in klines]
    rsi = calculate_rsi(closing_prices,period=10)
    if rsi < 50:
        print (f"{datetime.now()} - لايمكن فتح صفقات جديدة الان بسبب انخفاظ سعر البيتكوين بمستوى RSI-{rsi}.")
    return True if rsi > 50 else False


def open_trade_with_dynamic_target(symbol, investment=2.5, base_profit_target=0.002, base_stop_loss=0.0005, timeout=30):
    global balance, commission_rate
    
    # trading_status= bot_settings.trading_status()
    # if trading_status =="0":
    #     # print("the trading is of can't open more trad")
    #     return
    # Ensure sufficient balance before opening the trade
    if balance < investment:
        # print(f"{datetime.now()} - {symbol} -الرصيد الحالي غير كافٍ لفتح صفقة جديدة.")
        return

    if not check_bnb_balance():
        # print(f"{datetime.now()} - الرصيد غير كافٍ من BNB لتغطية الرسوم. {symbol} يرجى إيداع BNB.")
        return
    
    if not can_trade(symbol=symbol):
        # print(f"{datetime.now()} -لقدم تم فتح صفقة حديثاً لعملة {symbol} سيتم الانتظار .")

        return
        
    price = float(client.get_symbol_ticker(symbol=symbol)['price'])
    klines = client.get_klines(symbol=symbol, interval=klines_interval, limit=analize_period)
    closing_prices = [float(kline[4]) for kline in klines]
    avg_volatility = statistics.stdev(closing_prices)

    # Ensure both strategies' conditions are met before opening a trade
    if not should_open_trade(closing_prices,analize_period):
        # print(f"لا يجب شراء {symbol} في الوقت الحالي ")
        return

    # Calculate dynamic profit target and stop loss based on volatility
    profit_target = base_profit_target + avg_volatility + commission_rate
    stop_loss = base_stop_loss + avg_volatility * 0.5 + commission_rate
    target_price = price * (1 + profit_target)
    stop_price = price * (1 - stop_loss)
    quantity = adjust_quantity(symbol, (investment) / price)



    try:
        # Execute the buy order
        order = client.order_market_buy(symbol=symbol, quantity=quantity)
        commission = investment * commission_rate
        active_trades[symbol] = {
            'quantity': quantity,
            'initial_price': price,
            'target_price': target_price,
            'stop_price': stop_price,
            'start_time': time.time(),
            'timeout': timeout * 60,
            'investment': investment - commission
        }
        adjust_balance(investment, action="buy")
        # last_trade_time[symbol] = time.time()  # Record the trade timestamp
        print(f"{datetime.now()} - تم فتح صفقة شراء لـ {symbol} بسعر {price}, بهدف {target_price} وإيقاف خسارة عند {stop_price}")
    except BinanceAPIException as e:
        if 'NOTIONAL' in str(e) or 'Invalid symbol' in str(e)  or 'Market is closed' in str(e):
            excluded_symbols.add(symbol)
        print(f"خطأ في فتح الصفقة لـ {symbol}: {e}")


def sell_trade(symbol, trade_quantity):
    
    try:
        # الحصول على الكمية المتاحة في المحفظة
        balance_info = client.get_asset_balance(asset=symbol.replace("USDT", ""))
        # available_quantity = float(balance_info['free'])
        available_quantity = trade_quantity
        current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])

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
        last_trade_time[symbol] = time.time()  # Record the trade timestamp
        # adjust_balance(sale_amount, commission_rate, action="sell")
        earnings = adjusted_quantity * current_price

        print(f"تم تنفيذ عملية البيع لـ {symbol} بكمية {adjusted_quantity} وربح {earnings}")
        return adjusted_quantity
    except BinanceAPIException as e:
        print(f"خطأ في بيع {symbol}: {e}")
        return 0

def check_trade_conditions():
    global balance
    
    
    for symbol, trade in list(active_trades.items()):
        try:
            klines = client.get_klines(symbol=symbol, interval=klines_interval, limit=analize_period)
            closing_prices = [float(kline[4]) for kline in klines]
            
            current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
            current_prices[symbol] = current_price
        except BinanceAPIException as e:
            print(f"خطأ في تحديث السعر لـ {symbol}: {e}")
            continue

        # Check for target, stop loss, or timeout conditions
        result = None
        sold_quantity = 0
        total_sale = 0
        # close_all= bot_settings.colose_all_status()
        # if close_all =="0":
        #     # print("the trading is of can't open more trad")
        #     return
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
            # elif should_close_trade(closing_prices,analize_period):
            #     sold_quantity = sell_trade(symbol, trade['quantity'])
            #     result = 'إيقاف اجباري' if sold_quantity > 0 else None
                
            # Handle trade results and balance update
            if result and sold_quantity > 0:
                total_sale = sold_quantity * current_price
                commission = total_sale * commission_rate
                net_sale = total_sale - commission
                earnings = trade['quantity'] * current_price - trade['initial_price'] * trade['quantity']
                adjust_balance(total_sale, action="sell")
                print(f"{datetime.now()} - تم {result} الصفقة لـ {symbol} عند السعر {current_price} وربح {earnings}")
                with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    start_time=trade['start_time']
                    
                    writer.writerow([symbol, sold_quantity, trade['initial_price'], trade['target_price'], trade['stop_price'], datetime.now(),datetime.fromtimestamp(trade['start_time']), base_profit_target, base_stop_loss, str(timeout) + 'm', earnings, result, balance])
                del active_trades[symbol]
        except BinanceAPIException as e:
            if 'NOTIONAL' in str(e) or 'Invalid symbol' in str(e) or 'Market is closed' in str(e):
                excluded_symbols.add(symbol)
            print(f"خطأ في بيع {symbol}: {e}")
            continue

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
        # check_btc= check_btc_price()
        check_btc=True
        for symbol in symbols_to_trade:
            if symbol in excluded_symbols or symbol in black_list:
                continue
            try:
                current_prices[symbol] = float(client.get_symbol_ticker(symbol=symbol)['price'])
                # print(f"تم تحديث السعر لعملة {symbol}: {current_prices[symbol]}")
                if symbol not in active_trades and check_btc:
                    open_trade_with_dynamic_target(symbol,investment=investment,base_profit_target=base_profit_target,base_stop_loss=base_stop_loss,timeout=timeout)
            except BinanceAPIException as e:
                print(f"خطأ في تحديث السعر لـ {symbol}: {e}")
                if 'NOTIONAL' in str(e) or 'Invalid symbol' in str(e):
                    excluded_symbols.add(symbol)  # Exclude symbols causing frequent errors
                    time.sleep(0.1)

# مراقبة حالة الصفقات المغلقة
def monitor_trades():
    while True:
        check_trade_conditions()
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
        
