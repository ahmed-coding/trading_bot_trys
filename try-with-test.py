# تثبيت المكتبات المطلوبة
# pip install python-binance pandas ta-lib schedule

from binance.client import Client
import pandas as pd
import talib as ta
import schedule
import time
import math
from datetime import datetime



print(f"تم بدء تشغيل البوت في {datetime.now()}")

# إعداد مفاتيح API الخاصة بك
api_key = 'tweOjH1Keln44QaxLCr3naevRPgF3j3sYuOpaAg9B7nUT74MyURemvivEUcihfkt'
api_secret = 'XLlku378D8aZzYg9JjOTtUngA8Q73xBCyy7jGVbqRYSoEICsGBfWC0cIsRptLHxb'

# إضافة معلمة base_url لربط Testnet
client = Client(api_key, api_secret)
client.API_URL = 'https://testnet.binance.vision/api'

# تهيئة الاتصال ببايننس
# client = Client(api_key, api_secret)

# دالة لجلب العملات الصاعدة
def fetch_rising_coins():
    tickers = client.get_ticker()
    rising_coins = []
    for ticker in tickers:
        if ticker['symbol'].endswith('USDT') and float(ticker['priceChangePercent']) > 0:
            rising_coins.append({
                'symbol': ticker['symbol'],
                'price_change': ticker['priceChangePercent']
            })
    return rising_coins

# دالة للتحليل باستخدام المتوسط المتحرك
def fetch_and_analyze(symbol):
    klines = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1MINUTE, limit=10)
    df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                                       'close_time', 'quote_asset_volume', 'num_trades', 
                                       'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 
                                       'ignore'])
    df['close'] = df['close'].astype(float)
    df['SMA'] = ta.SMA(df['close'], timeperiod=5)
    
    if df['close'].iloc[-1] > df['SMA'].iloc[-1]:
        return True
    else:
        return False


def get_lot_size(symbol):
    # الحصول على قواعد التداول للرمز المحدد
    exchange_info = client.get_symbol_info(symbol)
    for filter in exchange_info['filters']:
        if filter['filterType'] == 'LOT_SIZE':
            step_size = float(filter['stepSize'])
            return step_size
    return None

def adjust_quantity(symbol, quantity):
    step_size = get_lot_size(symbol)
    if step_size is None:
        return quantity
    # تحديد الدقة بناءً على step_size لكل عملة
    precision = int(round(-math.log(step_size, 10), 0))
    return round(quantity, precision)



# تعديل دالة فتح الصفقات مع تحسينات الهدف والمهلة الزمنية
def open_trade_with_stop_loss(symbol, investment=10, profit_target=0.003, stop_loss=0.0015, timeout=2):
    price = float(client.get_symbol_ticker(symbol=symbol)['price'])
    target_price = price * (1 + profit_target)
    stop_price = price * (1 - stop_loss)
    quantity = adjust_quantity(symbol, investment / price)
    
    # تنفيذ أمر شراء
    order = client.order_market_buy(
        symbol=symbol,
        quantity=quantity
    )
    
    print(f"{datetime.now()} - تم فتح صفقة شراء لـ {symbol} بسعر {price}, بهدف {target_price} وإيقاف خسارة عند {stop_price}")
    
    # بدء التوقيت
    start_time = time.time()
    timeout_seconds = timeout * 60
    
    while True:
        current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
        
        if current_price >= target_price:
            client.order_market_sell(
                symbol=symbol,
                quantity=quantity
            )
            print(f"{datetime.now()} - تم جني الأرباح لـ {symbol} عند السعر {current_price}")
            break
        
        elif current_price <= stop_price:
            client.order_market_sell(
                symbol=symbol,
                quantity=quantity
            )
            print(f"{datetime.now()} - تم إيقاف الخسارة لـ {symbol} عند السعر {current_price}")
            break
        
        elif time.time() - start_time >= timeout_seconds:
            client.order_market_sell(
                symbol=symbol,
                quantity=quantity
            )
            print(f"{datetime.now()} - انتهت المهلة الزمنية لـ {symbol} وتم إغلاق الصفقة عند السعر {current_price}")
            break
        
        time.sleep(1)


# # تحديث دالة فتح الصفقة لتتضمن دقة الكمية
# def open_trade_with_stop_loss(symbol, investment=10, profit_target=0.005, stop_loss=0.0025):
#     import math
#     price = float(client.get_symbol_ticker(symbol=symbol)['price'])
#     target_price = price * (1 + profit_target)
#     stop_price = price * (1 - stop_loss)
    
#     # حساب الكمية وضبطها
#     quantity = investment / price
#     quantity = adjust_quantity(symbol, quantity)
    
#     order = client.order_market_buy(
#         symbol=symbol,
#         quantity=quantity
#     )
    
#     print(f"تم فتح صفقة شراء لـ {symbol} بسعر {price}, بهدف {target_price} وإيقاف خسارة عند {stop_price}")
    
#     while True:
#         current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
        
#         if current_price >= target_price:
#             client.order_market_sell(
#                 symbol=symbol,
#                 quantity=quantity
#             )
#             print(f"تم جني الأرباح لـ {symbol} عند السعر {current_price}")
#             break
        
#         elif current_price <= stop_price:
#             client.order_market_sell(
#                 symbol=symbol,
#                 quantity=quantity
#             )
#             print(f"تم إيقاف الخسارة لـ {symbol} عند السعر {current_price}")
#             break



# # دالة لفتح صفقة مع إعداد إيقاف الخسارة
# def open_trade_with_stop_loss(symbol, investment=10, profit_target=0.005, stop_loss=0.0025):
#     price = float(client.get_symbol_ticker(symbol=symbol)['price'])
#     target_price = price * (1 + profit_target)
#     stop_price = price * (1 - stop_loss)
#     quantity = investment / price
    
#     order = client.order_market_buy(
#         symbol=symbol,
#         quantity=quantity
#     )
    
#     print(f"تم فتح صفقة شراء لـ {symbol} بسعر {price}, بهدف {target_price} وإيقاف خسارة عند {stop_price}")
    
#     while True:
#         current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
        
#         if current_price >= target_price:
#             client.order_market_sell(
#                 symbol=symbol,
#                 quantity=quantity
#             )
#             print(f"تم جني الأرباح لـ {symbol} عند السعر {current_price}")
#             break
        
#         elif current_price <= stop_price:
#             client.order_market_sell(
#                 symbol=symbol,
#                 quantity=quantity
#             )
#             print(f"تم إيقاف الخسارة لـ {symbol} عند السعر {current_price}")
#             break

# دالة لتشغيل البوت على العملات المناسبة
def execute_bot():
    rising_coins = fetch_rising_coins()
    potential_trades = [coin['symbol'] for coin in rising_coins if fetch_and_analyze(coin['symbol'])]
    
    for symbol in potential_trades:
        try:
            open_trade_with_stop_loss(symbol)
        except Exception as e:
            print(f"خطأ في فتح صفقة لـ {symbol}: {e}")


execute_bot()  # بدء فوري عند تشغيل البرنامج
# schedule.every(1).minutes.do(execute_bot)

# جدولة تشغيل البوت كل دقيقة
schedule.every(1).minutes.do(execute_bot)

while True:
    schedule.run_pending()
    time.sleep(1)
