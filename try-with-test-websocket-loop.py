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
from config import API_KEY, API_SECRET, API_TEST_KEY, API_TEST_SECRET, Settings
# from binance import websocket
import websocket

session = requests.Session()
session.headers.update({'timeout': '90'})  # قد تكون هذه الإعدادات غير فعّالة

# إعداد مفاتيح API الخاصة بك
client = Client(API_TEST_KEY, API_TEST_SECRET)
client.API_URL = 'https://testnet.binance.vision/api'

current_prices = {}
active_trades = {}
# إدارة المحفظة 0
balance = 59  # الرصيد المبدئي للبوت
investment = 6  # حجم كل صفقة
base_profit_target = 0.0045  # نسبة الربح
base_stop_loss = 0.008  # نسبة الخسارة
timeout = 25  # وقت انتهاء وقت الصفقة
commission_rate = 0.002  # نسبة العمولة للمنصة
excluded_symbols = set()  # قائمة العملات المستثناة بسبب أخطاء متكررة
bot_settings = Settings()
symbols_to_trade = []
last_trade_time = {}
klines_interval = Client.KLINE_INTERVAL_1MINUTE
klines_limit = 20
top_symbols = 20

# ملف CSV لتسجيل التداولات
csv_file = 'update_trades_log_websocket_test.csv'
if not os.path.exists(csv_file):
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['الرمز', 'الكمية', 'السعر الابتدائي', 'سعر الهدف', 'سعر الإيقاف', 'وقت الاغلاق', 'وقت الفتح','نسبة الربح','نسبة الخسارة','المهلة', 'الربح','النتيجة', 'الرصيد المتبقي'])

# دالة حساب RSI
def calculate_rsi(prices, period=14):
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [d for d in deltas if d > 0]
    losses = [-d for d in deltas if d < 0]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    rsi = 100 - (100 / (1 + rs))
    return rsi

# دالة حساب Bollinger Bands
def calculate_bollinger_bands(prices, period=20, multiplier=2):
    sma = sum(prices[-period:]) / period  # المتوسط المتحرك البسيط (SMA)
    std_dev = statistics.stdev(prices[-period:])  # الانحراف المعياري لآخر 'period' أسعار
    upper_band = sma + (std_dev * multiplier)
    lower_band = sma - (std_dev * multiplier)
    return upper_band, lower_band

# ضبط الرصيد بناءً على العملية (شراء أو بيع)
def adjust_balance(amount, action="buy"):
    global balance, commission_rate
    commission = amount * commission_rate
    if action == "buy":
        balance -= (amount - (commission * 0.5))  # خصم المبلغ + العمولة
    elif action == "sell":
        balance += amount - (commission * 0.5)  # إضافة المبلغ بعد خصم العمولة
    print(f"تم تحديث الرصيد بعد {action} - الرصيد المتبقي: {balance}")
    return balance

# تحميل الصفقات المفتوحة من المحفظة
def load_open_trades_from_portfolio():
    global balance, commission_rate, base_profit_target, base_stop_loss
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
                profit_target = base_profit_target + avg_volatility + commission_rate
                stop_loss = base_stop_loss + avg_volatility * 0.5 + commission_rate
                target_price = price * (1 + profit_target)
                stop_price = price * (1 - stop_loss)
                quantity = adjust_quantity(symbol, investment / price)
                target_price = commission_rate + price * 1.002  # هدف ربح سريع
                stop_price = price * 0.9995  # إيقاف خسارة سريع
                active_trades[symbol] = {
                    'quantity': quantity,
                    'initial_price': price,
                    'target_price': target_price,
                    'stop_price': stop_price,
                    'start_time': time.time(),
                    'timeout': 30  # المهلة الزمنية 30 ثانية
                }
                print(f"تم استعادة الصفقة المفتوحة لـ {symbol} من المحفظة.")
            except Exception as e:
                print(f"خطأ في تحميل الصفقة لـ {symbol}: {e}")

# تحديث الرموز باستخدام WebSocket
def on_message(ws, message):
    data = json.loads(message)
    symbol = data['s']  # الرمز
    price = float(data['c'])  # السعر الحالي
    current_prices[symbol] = price
    print(f"تم تحديث السعر لـ {symbol}: {price}")

    if symbol not in active_trades:
        open_trade_with_dynamic_target(symbol, investment=investment, base_profit_target=base_profit_target, base_stop_loss=base_stop_loss, timeout=timeout)

# دالة لتشغيل WebSocket
def start_websocket():
    stream_url = "wss://stream.binance.com:9443/ws/!miniTicker@arr"
    ws = websocket.WebSocketApp(stream_url, on_message=on_message)
    print("تم تشغيل WebSocket للاستماع للأسعار.")
    ws.run_forever()

# دالة لفتح صفقة مع أهداف ديناميكية
def open_trade_with_dynamic_target(symbol, investment=2.5, base_profit_target=0.002, base_stop_loss=0.0005, timeout=30):
    global balance, commission_rate

    price = float(client.get_symbol_ticker(symbol=symbol)['price'])
    klines = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1MINUTE, limit=8)
    closing_prices = [float(kline[4]) for kline in klines]
    avg_volatility = statistics.stdev(closing_prices)

    # تأكد من أن الشروط المناسبة قد تحققت قبل فتح الصفقة
    if not should_open_trade(closing_prices):
        print(f"لا يجب شراء {symbol} في الوقت الحالي ")
        return

    # حساب الهدف الديناميكي للربح وإيقاف الخسارة بناءً على التقلبات
    profit_target = base_profit_target + avg_volatility + commission_rate
    stop_loss = base_stop_loss + avg_volatility * 0.5 + commission_rate
    target_price = price * (1 + profit_target)
    stop_price = price * (1 - stop_loss)
    quantity = adjust_quantity(symbol, (investment) / price)

    # تأكد من أن الرصيد كافٍ قبل فتح الصفقة
    if balance < investment:
        print(f"{datetime.now()} - {symbol} - الرصيد الحالي غير كافٍ لفتح صفقة جديدة.")
        return

    if not check_bnb_balance():
        print(f"{datetime.now()} - الرصيد غير كافٍ من BNB لتغطية الرسوم. {symbol} يرجى إيداع BNB.")
        return

    try:
        # تنفيذ أمر الشراء
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
        last_trade_time[symbol] = time.time()  # تسجيل توقيت الصفقة
        print(f"{datetime.now()} - تم فتح صفقة شراء لـ {symbol} بسعر {price}, بهدف {target_price} وإيقاف خسارة عند {stop_price}")
    except BinanceAPIException as e:
        if 'NOTIONAL' in str(e) or 'Invalid symbol' in str(e) or 'Market is closed' in str(e):
            excluded_symbols.add(symbol)
        print(f"خطأ في فتح الصفقة لـ {symbol}: {e}")

# دالة لإغلاق الصفقة عند تحقق الهدف أو الإيقاف
def close_trade(symbol, result):
    global active_trades
    if symbol in active_trades:
        trade = active_trades.pop(symbol)
        print(f"تم إغلاق الصفقة لـ {symbol} - النتيجة: {result}")
        log_trade(symbol, trade['quantity'], trade['initial_price'], trade['target_price'], trade['stop_price'], time.time(), trade['start_time'], trade['timeout'], result)

# دالة لتسجيل العمليات في ملف CSV
def log_trade(symbol, quantity, initial_price, target_price, stop_price, end_time, start_time, timeout, result):
    with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([symbol, quantity, initial_price, target_price, stop_price, end_time, start_time, target_price - initial_price, stop_price - initial_price, timeout, result, 'صحيح' if result == 'ربح' else 'خسارة', balance])

# دالة لفحص التوازن وتحديد ما إذا كان يجب فتح الصفقة
def should_open_trade(closing_prices):
    if len(closing_prices) < 2:
        return False
    last_price = closing_prices[-1]
    prev_price = closing_prices[-2]
    return last_price > prev_price  # يمكن تعديل هذه الشروط لتناسب الاستراتيجية

# التحقق من رصيد BNB
def check_bnb_balance():
    balance_info = client.get_asset_balance(asset='BNB')
    return float(balance_info['free']) > 0.1  # تأكد من وجود BNB كافٍ لتغطية الرسوم

# دالة لضبط الكمية بناءً على الحجم الذي تريده
def adjust_quantity(symbol, quantity):
    min_qty = float(client.get_symbol_info(symbol)['filters'][2]['minQty'])
    step_size = float(client.get_symbol_info(symbol)['filters'][2]['stepSize'])
    adjusted_quantity = math.floor(quantity / step_size) * step_size
    return max(adjusted_quantity, min_qty)

# تشغيل WebSocket
if __name__ == "__main__":
    if bot_settings.bot_status() != '0':
        start_websocket()








a= [
    'PNUTUSDT',
    'ACTUSDT',
    'WIFUSDT',
    'AGLDUSDT',
    'HIVEUSDT',
    'MITHUSDT',
    'ERDUSDT',
    'MFTUSDT',
    'DOCKUSDT',
    'TCTUSDT',
    'BTSUSDT',
    'NBSUSDT',
    'UNIDOWNUSDT',
    'AAVEDOWNUSDT',
    'SUSHIUPUSDT',
    'RAMPUSDT',
    '1INCHUPUSDT',
    '1INCHDOWNUSDT',
    'TORNUSDT',
    'TVKUSDT',
    'VGXUSDT',
    'PLAUSDT',
    'OOKIUSDT',
    'MULTIUSDT',
    'MOBUSDT',
    'EPXUSDT'
    ]

