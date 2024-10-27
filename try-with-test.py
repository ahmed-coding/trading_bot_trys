# تثبيت المكتبات المطلوبة
# pip install python-binance pandas ta-lib schedule

from binance.client import Client
import pandas as pd
import talib as ta
import schedule
import time

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

# دالة لفتح صفقة مع إعداد إيقاف الخسارة
def open_trade_with_stop_loss(symbol, investment=10, profit_target=0.005, stop_loss=0.0025):
    price = float(client.get_symbol_ticker(symbol=symbol)['price'])
    target_price = price * (1 + profit_target)
    stop_price = price * (1 - stop_loss)
    quantity = investment / price
    
    order = client.order_market_buy(
        symbol=symbol,
        quantity=quantity
    )
    
    print(f"تم فتح صفقة شراء لـ {symbol} بسعر {price}, بهدف {target_price} وإيقاف خسارة عند {stop_price}")
    
    while True:
        current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
        
        if current_price >= target_price:
            client.order_market_sell(
                symbol=symbol,
                quantity=quantity
            )
            print(f"تم جني الأرباح لـ {symbol} عند السعر {current_price}")
            break
        
        elif current_price <= stop_price:
            client.order_market_sell(
                symbol=symbol,
                quantity=quantity
            )
            print(f"تم إيقاف الخسارة لـ {symbol} عند السعر {current_price}")
            break

# دالة لتشغيل البوت على العملات المناسبة
def execute_bot():
    rising_coins = fetch_rising_coins()
    potential_trades = [coin['symbol'] for coin in rising_coins if fetch_and_analyze(coin['symbol'])]
    
    for symbol in potential_trades:
        try:
            open_trade_with_stop_loss(symbol)
        except Exception as e:
            print(f"خطأ في فتح صفقة لـ {symbol}: {e}")

# جدولة تشغيل البوت كل دقيقة
schedule.every(1).minutes.do(execute_bot)

while True:
    schedule.run_pending()
    time.sleep(1)
