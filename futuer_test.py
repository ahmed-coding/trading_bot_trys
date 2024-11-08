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
from config import API_TEST_KEY, API_TEST_SECRET, Settings, API_KEY, API_SECRET

session = requests.Session()
session.headers.update({'timeout': '90'})


# Initialize Binance Futures Client

current_prices = {}
active_trades = {}
balance = 1000  # initial bot balance
investment = 100  # investment per trade
base_profit_target = 0.0032  # profit percentage
base_stop_loss = 0.01  # stop-loss percentage
timeout = 15  # trade timeout
commission_rate = 0.002  # platform commission
excluded_symbols = set()  # symbols excluded due to frequent errors
bot_settings = Settings()
symbols_to_trade = []
last_trade_time = {}
leverage=10


client = Client(API_KEY, API_SECRET, testnet=True)
client.futures_change_leverage(symbol='BTCUSDT', leverage=leverage)  # Default leverage; modify as needed
# client.FUTURES_API_URL = 'https://fapi.binance.com'


# client.FUTURES_API_URL = 'https://testnet.binance.vision/api'




csv_file = 'update_trades_log_test.csv'
if not os.path.exists(csv_file):
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['الرمز', 'الكمية', 'السعر الابتدائي', 'سعر الهدف', 'سعر الإيقاف', 'وقت الاغلاق', 'وقت الفتح',
                         'نسبة الربح', 'نسبة الخسارة', 'المهلة', 'الربح', 'النتيجة', 'الرصيد المتبقي'])

def calculate_rsi(prices, period=14):  
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [d for d in deltas if d > 0]
    losses = [-d for d in deltas if d < 0]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    rsi = 100 - (100 / (1 + rs))
    return rsi

def adjust_quantity(symbol, quantity):
    """Adjusts quantity to match Binance's lot size requirements."""
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            step_size = float(s['filters'][1]['stepSize'])
            quantity = math.floor(quantity / step_size) * step_size
            return round(quantity, int(-math.log10(step_size)))
    return quantity

def adjust_balance(amount, action="buy"):
    global balance, commission_rate
    commission = amount * commission_rate
    if action == "buy":
        balance -= (amount - (commission * 0.5))
    elif action == "sell":
        balance += amount - (commission * 0.5)
    print(f"Updated balance after {action} - Remaining balance: {balance}")
    return balance

def load_open_trades_from_portfolio():
    global balance, commission_rate, base_profit_target, base_stop_loss
    positions = client.futures_account()['positions']
    for position in positions:
        symbol = position['symbol']
        if float(position['positionAmt']) > 0:
            try:
                price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
                quantity = float(position['positionAmt'])
                avg_volatility = statistics.stdev([float(kline[4]) for kline in client.futures_klines(
                    symbol=symbol, interval=Client.KLINE_INTERVAL_30MINUTE, limit=20)])
                profit_target = base_profit_target + avg_volatility + commission_rate
                stop_loss = base_stop_loss + avg_volatility * 0.5 + commission_rate
                target_price = price * (1 + profit_target)
                stop_price = price * (1 - stop_loss)
                active_trades[symbol] = {
                    'quantity': quantity,
                    'initial_price': price,
                    'target_price': target_price,
                    'stop_price': stop_price,
                    'start_time': time.time(),
                    'timeout': 30
                }
                print(f"Loaded open trade for {symbol} from portfolio.")
            except Exception as e:
                print(f"Error loading trade for {symbol}: {e}")



def get_top_symbols(limit=10, profit_target=0.009, rsi_threshold=70):
    tickers = client.get_ticker()
    sorted_tickers = sorted(tickers, key=lambda x: float(x['quoteVolume']), reverse=True)
    top_symbols = []
    for ticker in sorted_tickers:
        if ticker['symbol'].endswith("USDT") and ticker['symbol'] not in excluded_symbols:
            try:
                klines = client.futures_klines(symbol=ticker['symbol'], interval=Client.KLINE_INTERVAL_5MINUTE, limit=20)
                closing_prices = [float(kline[4]) for kline in klines]
                stddev = statistics.stdev(closing_prices)
                rsi = calculate_rsi(closing_prices)
                avg_price = sum(closing_prices) / len(closing_prices)
                volatility_ratio = stddev / avg_price
                if stddev < 0.04 and volatility_ratio >= profit_target and rsi < rsi_threshold:
                    top_symbols.append(ticker['symbol'])
                    print(f"Selected {ticker['symbol']} with volatility ratio {volatility_ratio:.4f} and RSI {rsi:.2f}")
                if len(top_symbols) >= limit:
                    break
            except BinanceAPIException as e:
                print(f"Error fetching data for {ticker['symbol']}: {e}")
                excluded_symbols.add(ticker['symbol'])
    return top_symbols

def open_trade_with_dynamic_target(symbol, investment=2.5, base_profit_target=0.002, base_stop_loss=0.0005, timeout=30):
    global balance, commission_rate
    price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
    klines = client.futures_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_5MINUTE, limit=5)
    closing_prices = [float(kline[4]) for kline in klines]
    avg_volatility = statistics.stdev(closing_prices)
    profit_target = base_profit_target + avg_volatility + commission_rate
    stop_loss = base_stop_loss + avg_volatility * 0.5 + commission_rate
    target_price = price * (1 + profit_target)
    stop_price = price * (1 - stop_loss)
    quantity = adjust_quantity(symbol, investment / price)
    
    # Deciding whether to open a buy or sell position based on the RSI indicator
    rsi = calculate_rsi(closing_prices)
    if rsi < 30:  # If RSI is below 30, consider buying (market is oversold)
        side = "BUY"
    elif rsi > 70:  # If RSI is above 70, consider selling (market is overbought)
        side = "SELL"
    else:
        # If RSI is between 30 and 70, we might decide based on other conditions like volatility
        volatility_ratio = avg_volatility / price
        if volatility_ratio > 0.01:  # If volatility is high, open buy if price is dropping, or sell if rising
            side = "SELL" if closing_prices[-1] > closing_prices[0] else "BUY"
        else:
            side = "BUY"  # Default to buying in uncertain conditions
            
    try:
        # Open the chosen position (BUY or SELL)
        client.futures_create_order(symbol=symbol, side=side, type="MARKET", quantity=quantity)

        active_trades[symbol] = {
            'quantity': quantity,
            'initial_price': price,
            'target_price': target_price,
            'stop_price': stop_price,
            'start_time': time.time(),
            'timeout': timeout * 60,
            'investment': investment - (investment * commission_rate)
        }
        adjust_balance(investment, action=side.lower())
        print(f"{datetime.now()} - Opened {side} trade for {symbol} at {price}, target {target_price}, stop-loss {stop_price}")
    except BinanceAPIException as e:
        if 'NOTIONAL' in str(e) or 'Invalid symbol' in str(e):
            excluded_symbols.add(symbol)
        print(f"Error opening trade for {symbol}: {e}")

def sell_trade(symbol, trade_quantity):
    try:
        available_quantity = abs(float(client.futures_position_information(symbol=symbol)[0]['positionAmt']))
        if available_quantity < trade_quantity:
            print(f"Insufficient available quantity for {symbol}.")
            return 0
        client.futures_create_order(symbol=symbol, side="SELL", type="MARKET", quantity=available_quantity)
        print(f"Executed sell for {symbol} with quantity {available_quantity}")
        return available_quantity
    except BinanceAPIException as e:
        print(f"Error selling {symbol}: {e}")
        return 0

# Rest of the code remains the same, with futures adjustments as needed in each function

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
                # excluded_symbols.add(symbol)
            elif time.time() - trade['start_time'] >= trade['timeout']:
                sold_quantity = sell_trade(symbol, trade['quantity'])
                # excluded_symbols.add(symbol)
                result = 'انتهاء المهلة' if sold_quantity > 0 else None
                

            # إذا تم تنفيذ عملية البيع بنجاح، تحديث الرصيد مع خصم العمولة
            if result and sold_quantity > 0:
                total_sale = sold_quantity * current_price
                commission = total_sale * commission_rate
                net_sale = total_sale - commission  # صافي البيع بعد خصم العمولة
                init_price = trade['initial_price'] * sold_quantity
                earnings = trade['quantity'] * current_price - trade['initial_price'] * trade['quantity']

                # تحديث الرصيد بناءً على نوع العملية (البيع)
                adjust_balance(total_sale, action="sell")

                print(f"{datetime.now()} - تم {result} الصفقة لـ {symbol} عند السعر {current_price} وربح {earnings}")
                with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow([symbol, sold_quantity, trade['initial_price'], trade['target_price'], trade['stop_price'], datetime.now(),trade['start_time'],base_profit_target, base_stop_loss, str(timeout)+'m', earnings, result, balance])
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
        symbols_to_trade = get_top_symbols(10)
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


# Run bot
def run_bot():
    global symbols_to_trade
    symbols_to_trade = get_top_symbols(10)
    threading.Thread(target=update_symbols_periodically, args=(900,)).start()
    threading.Thread(target=update_prices).start()
    threading.Thread(target=monitor_trades).start()
    print(f"Bot started at {datetime.now()}")

if __name__ == "__main__":
    if bot_settings.bot_status() != '0':
        run_bot()
    print("Bot is turned off")
