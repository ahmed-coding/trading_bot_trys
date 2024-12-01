from backtesting import Backtest, Strategy
from backtesting.lib import crossover
# from backtesting.test import GOOG  # مثال على بيانات افتراضية يمكنك استبدالها ببيانات Binance
import pandas as pd
import numpy as np
from binance.client import Client
import statistics
from binance.exceptions import BinanceAPIException
import ta 


api_key = 'of6qt1T1MpGvlgma1qxwFTLdrGNNVsMj0fKf8LZy1sMf3OqTrwHC7BCRIkgsSsda'
api_secret = 'MZuALJiqyWMoQ0WkPE6tqWdToGLTHLsap5m95qhPIDtizy1FPD0TQBXNvyQBhgFf'


# api_key = 'tweOjH1Keln44QaxLCr3naevRPgF3j3sYuOpaAg9B7nUT74MyURemvivEUcihfkt'
# api_secret = 'XLlku378D8aZzYg9JjOTtUngA8Q73xBCyy7jGVbqRYSoEICsGBfWC0cIsRptLHxb'

# تهيئة الاتصال ببايننس واستخدام Testnet
client = Client(api_key, api_secret,requests_params={'timeout':90})
# client.API_URL = 'https://testnet.binance.vision/api'


current_prices = {}
active_trades = {}
# إدارة المحفظة 0
balance = 25 # الرصيد المبدئي للبوت
investment=6 # حجم كل صفقة
base_profit_target=0.005 # نسبة الربح
# base_profit_target=0.005 # نسبة الربح
# base_stop_loss=0.1 # نسبة الخسارة
# base_stop_loss=0.000 # نسبة الخسارة
timeout=60 # وقت انتهاء وقت الصفقة
commission_rate = 0.002 # نسبة العمولة للمنصة
excluded_symbols = set()  # قائمة العملات المستثناة بسبب أخطاء متكررة
# bot_settings=Settings()
symbols_to_trade =[]
last_trade_time = {}
klines_interval=Client.KLINE_INTERVAL_3MINUTE
klines_limit=1
top_symbols=[]
count_top_symbols=70
analize_period=8
black_list=[
        # 'XRPUSDT',
        # 'ETHUSDT', 'BTCUSDT', 'SOLUSDT', 'ENSUSDT', 'BNBUSDT', 'FILUSDT',
        # 'AVAXUSDT', 'LTCUSDT', 'UNIUSDT', 'ARUSDT', 'LINKUSDT', 'TAOUSDT', 'ORDIUSDT',
        # 'APTUSDT', 'BCHUSDT', 'ETCUSDT', 
        # 'MKRUSDT', 'WBTCUSDT', 'ZENUSDT', 'INJUSDT', 'TRBUSDT', 'ICPUSDT', 'SSVUSDT', 'AAVEUSDT', 
    ]


def get_top_symbols(limit=20, profit_target=0.007, rsi_threshold=70):
    tickers = client.get_ticker()
    sorted_tickers = sorted(tickers, key=lambda x: float(x['quoteVolume']), reverse=True)
    top_symbols = []
    
    for ticker in sorted_tickers:
        if ticker['symbol'].endswith("USDT") and ticker['symbol'] not in black_list :
        # if ticker['symbol'].endswith("USDT") and ticker['symbol'] not in excluded_symbols and not 'BTTC' in str(ticker['symbol']):
            try:
                klines = client.get_klines(symbol=ticker['symbol'], interval=klines_interval, limit=klines_limit)
                # closing_prices = [float(kline[4]) for kline in klines]
                # stddev = statistics.stdev(closing_prices)
                if klines is None or klines == []:
                    print(f"the data in symbol {symbol} is empty") 
                    continue
                # حساب مؤشر RSI
                # rsi = calculate_rsi(closing_prices,period=klines_limit)
                
                # اختيار العملة بناءً على التذبذب ومؤشر RSI
                # avg_price = sum(closing_prices) / len(closing_prices)
                # volatility_ratio = stddev / avg_price

                # if stddev < 0.04 and volatility_ratio >= profit_target :
                top_symbols.append(ticker['symbol'])
                    # print(f"تم اختيار العملة {ticker['symbol']} بنسبة تذبذب {volatility_ratio:.4f} و RSI {rsi:.2f}")
                
                if len(top_symbols) >= limit:
                    break
            except BinanceAPIException as e:
                print(f"خطأ في جلب بيانات {ticker['symbol']}: {e}")
                excluded_symbols.add(ticker['symbol'])
    return top_symbols



def bol_h(df):
    return ta.volatility.BollingerBands(pd.Series(df)).bollinger_hband() 

def bol_l(df):
    return ta.volatility.BollingerBands(pd.Series(df)).bollinger_lband() 


# حساب مؤشر RSI
def calculate_rsi(data, period=14):
    """حساب RSI متوافق مع مكتبة Backtesting"""
    deltas = pd.Series(data).diff()  # تحويل البيانات إلى pandas Series للتوافق
    gains = deltas.where(deltas > 0, 0.0)
    losses = -deltas.where(deltas < 0, 0.0)
    avg_gain = gains.rolling(window=period).mean()
    avg_loss = losses.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# تعريف الاستراتيجية
class RSIStrategy(Strategy):
    rsi_period = 8  # الفترة الزمنية لمؤشر RSI
    profit_target = 0.015  # الربح المستهدف كنسبة مئوية
    stop_loss = 0.02  # إيقاف الخسارة كنسبة مئوية

    def init(self):
        # حساب RSI وإضافته كإشارة
        self.rsi = self.I(calculate_rsi, self.data.Close, self.rsi_period)
        self.bol_h=self.I(bol_h, self.data.Close)
        self.bol_l=self.I(bol_l, self.data.Close)
    # def next(self):
    #     price = self.data.Close[-1]

    #     # فتح صفقة شراء بناءً على RSI
    #     if self.rsi[-1] > 25 and self.rsi[-1] < 45:
    #         self.buy(sl=price * (1 - self.stop_loss), tp=price * (1 + self.profit_target))

    #     # إغلاق جميع الصفقات عند تحقيق الهدف أو تجاوز الحد
    #     for trade in self.trades:
    #         if trade.is_long:
    #             if self.rsi[-1] > 50:  # شرط إضافي لإغلاق الصفقات
    #                 self.sell()
    # def next(self):
    #     price = self.data.Close[-1]
    #     stop_loss_price = price * (1 - self.stop_loss)
    #     take_profit_price = price * (1 + self.profit_target)
    #     # print(f"Price: {price}, Stop Loss: {stop_loss_price}, Take Profit: {take_profit_price}")

    #     # فتح صفقة شراء بناءً على RSI
    #     if self.rsi[-1] > 30 :
    #         # تأكد من أن إيقاف الخسارة أقل من السعر الحالي
    #         # تأكد من أن إيقاف الخسارة أقل من الربح المستهدف
    #         if stop_loss_price < price and take_profit_price > price:
    #             if stop_loss_price < price < take_profit_price:
    #                 # print(f"Opening Long Order: SL: {stop_loss_price}, TP: {take_profit_price}")

    #                 self.buy(sl=stop_loss_price, tp=take_profit_price)

    #     # إغلاق جميع الصفقات عند تحقيق الهدف أو تجاوز الحد
    #     for trade in self.trades:
    #         if trade.is_long:
    #             if self.rsi[-1] > 70:  # شرط إضافي لإغلاق الصفقات
    #                 self.sell()
                    
                    
    def next(self):
        price = self.data.Close[-1]
        stop_loss_price = price * (1 - self.stop_loss)
        take_profit_price = price * (1 + self.profit_target)
        if self.data.Close[-3] > self.bol_l[-3] and self.data.Close[-2] < self.bol_l[-2]:
            if not self.position:
                self.buy(sl=stop_loss_price, tp=take_profit_price)
                
        
        
        if self.data.Close[-3] < self.bol_h[-3] and self.data.Close[-2] > self.bol_h[-2]:
            for trade in self.trades:
                if trade.is_long:
                    self.position.close()


# تحميل البيانات التاريخية (استخدام Binance أو بيانات جاهزة)
def fetch_binance_data(symbol, interval, start_date, end_date):
    # from binance.client import Client
    # client = Client(api_key="your_api_key", api_secret="your_api_secret")
    klines = client.get_historical_klines(symbol, interval, start_date)
    data = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                                         'close_time', 'quote_asset_volume', 'number_of_trades', 
                                         'taker_buy_base', 'taker_buy_quote', 'ignore'])
    data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
    data['open'] = data['open'].astype(float)
    data['high'] = data['high'].astype(float)
    data['low'] = data['low'].astype(float)
    data['close'] = data['close'].astype(float)
    data['volume'] = data['volume'].astype(float)
    return data[['timestamp', 'open', 'high', 'low', 'close', 'volume']].rename(columns={
        'timestamp': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'
    }).set_index('Date')


def extract_stats(stats):
    trades = stats['# Trades']  # عدد الصفقات
    win_rate = stats['Win Rate [%]']  # نسبة الربح
    best_trade = stats['Best Trade [%]']  # أفضل صفقة
    worst_trade = stats['Worst Trade [%]']  # أسوأ صفقة
    max_duration = stats['Max. Trade Duration']  
    avg_duration = stats['Max. Trade Duration']  

    return trades, win_rate, best_trade, worst_trade, max_duration, avg_duration


result=[]
# تنفيذ الباكتيست
if __name__ == "__main__":
    # استخدم بيانات Binance أو بيانات جاهزة
    for symbol in get_top_symbols(100):
        # data = fetch_binance_data(symbol, Client.KLINE_INTERVAL_3MINUTE, "48 hours ago UTC", "30 Nov 2023")
        data = fetch_binance_data(symbol, Client.KLINE_INTERVAL_3MINUTE, "12 hours ago UTC", "30 Nov 2023")

        # if data is None or data == []:
        #     # print(f"the data in symbol {symbol} is empty") 
        #     continue
        # تشغيل الباكتيست باستخدام Backtesting.py
        print(symbol)
        
        bt = Backtest(data, RSIStrategy, cash=1000000, commission=0.002)
        stats = bt.run() 
        trades, win_rate, best_trade, worst_trade, max_duration, avg_duration= extract_stats(stats)

        # print(stats.iloc[6])
        result.append([symbol, stats.iloc[6], trades, win_rate, best_trade, worst_trade, max_duration, avg_duration])
        # stats.plot()
        # print(stats)
        # bt.plot()
        # print(len(data))
        # طباعة النتائج
        # print(stats)


excel = pd.DataFrame(result)
excel.columns = ['Symbol', 'Return', 'Trades', 'Win Rate', 'Best Trade', 'Worst Trade','Max Duration','Avg Duration']
excel.loc[len(excel.index)] = ['Total', excel['Return'].sum(), '', '', '', '','', '']

# excel.to_excel('result.xlsx')

excel.to_csv('result.csv')
