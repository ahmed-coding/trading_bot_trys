
import time
from binance.client import Client
# import pandas_ta as ta


# حساب RSI
def calculate_rsi(prices, period=8):
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [d for d in deltas if d > 0]
    losses = [-d for d in deltas if d < 0]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    rsi = 100 - (100 / (1 + rs))
    return rsi


def should_open_trade(prices,period=8):
    rsi = calculate_rsi(prices,period=period)

    # RSI condition: Overbought (RSI > 70) signals a possible sell, Oversold (RSI < 30) signals a buy
    # if rsi > 70 or current_price > upper_band:
    #     return False  # Avoid opening a trade in overbought conditions

    # if rsi < 30 or current_price < lower_band:
    #     return True  # Open a buy trade in oversold conditions or if price crosses below lower Bollinger Band

    # return False  # No trade
    
    print(rsi)
    if rsi > 70 :
        return False  # Avoid opening a trade in overbought conditions

    if rsi < 20  :
        return True  # Open a buy trade in oversold conditions or if price crosses below lower Bollinger Band

    return False  # No trade




api_key = 'of6qt1T1MpGvlgma1qxwFTLdrGNNVsMj0fKf8LZy1sMf3OqTrwHC7BCRIkgsSsda'
api_secret = 'MZuALJiqyWMoQ0WkPE6tqWdToGLTHLsap5m95qhPIDtizy1FPD0TQBXNvyQBhgFf'

# api_key = 'tweOjH1Keln44QaxLCr3naevRPgF3j3sYuOpaAg9B7nUT74MyURemvivEUcihfkt'
# api_secret = 'XLlku378D8aZzYg9JjOTtUngA8Q73xBCyy7jGVbqRYSoEICsGBfWC0cIsRptLHxb'

# تهيئة الاتصال ببايننس واستخدام Testnet
client = Client(api_key, api_secret,)

symbol="BTCUSDT"
klines_interval="5m"
# price = float(client.get_symbol_ticker(symbol=symbol)['price'])
# klines = client.get_klines(symbol=symbol, interval=klines_interval, limit=41)
# closing_prices = [float(kline[4]) for kline in klines]
# avg_volatility = statistics.stdev(closing_prices)

# Ensure both strategies' conditions are met before opening a trade
# result= should_open_trade(closing_prices)

for i in range(20):
    klines = client.get_klines(symbol=symbol, interval=klines_interval, limit=6)
    closing_prices = [float(kline[4]) for kline in klines]
    should_open_trade(closing_prices,period=6)
    # print(ta.rsi(closing_prices,length=8))
    # print(42 < 40  and 42 > 50)
    time.sleep(0.3)
# print(42 > 40  and 42 < 50)
