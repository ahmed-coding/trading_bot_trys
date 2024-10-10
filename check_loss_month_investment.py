import ccxt
import pandas as pd
import numpy as np

# Exchange setup (Binance)
api_key = 'nHCAKjf112bSWMutN58GEevqhOZ2KqjP91IrW2xXMhbBHGIZuNU76QurKibiFNS9'
api_secret = '2HFcVh6bJrMNTqUCSJ1ZHjFdteyLxujXSdVXiCkIwt8huJvczA9WqH7mJDfq29yl'

exchange = ccxt.binance({
    'apiKey': api_key,
    'secret': api_secret,
})

# Define timeframes for analysis
mid_term_timeframe = '1w'  # Weekly candles for mid-term (4-6 months)
long_term_timeframe = '1M'  # Monthly candles for long-term (6-12 months)

# Moving averages settings
mid_window = 20  # 20-week moving average
long_window = 50  # 50-week moving average

# RSI settings
rsi_period = 14

# Loss threshold for issuing a sell signal
loss_threshold = 0.15  # 15% or more drop from recent high

def fetch_ohlcv(symbol, timeframe):
    """Fetch historical OHLCV data for the given symbol and timeframe"""
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

def calculate_rsi(df, period=rsi_period):
    """Calculate Relative Strength Index (RSI)"""
    delta = df['close'].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(window=period).mean()
    avg_loss = pd.Series(loss).rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    df['RSI'] = rsi
    return df

def moving_average_strategy(df, short_window, long_window):
    """Moving Average Crossover Strategy"""
    df['SMA_short'] = df['close'].rolling(window=short_window).mean()
    df['SMA_long'] = df['close'].rolling(window=long_window).mean()

    if df['SMA_short'].iloc[-1] > df['SMA_long'].iloc[-1]:
        return "buy"
    elif df['SMA_short'].iloc[-1] < df['SMA_long'].iloc[-1]:
        return "sell"
    else:
        return "hold"

def detect_price_loss(df):
    """Detect significant price loss from recent high"""
    highest_close = df['close'].max()
    current_price = df['close'].iloc[-1]
    loss_percentage = (highest_close - current_price) / highest_close

    # If the price has dropped more than the loss threshold
    if loss_percentage >= loss_threshold:
        return f"Sell (Price dropped {loss_percentage * 100:.2f}% from recent high)"
    else:
        return "No significant loss"

def detect_sell_signals(symbol):
    """Detect sell signals based on several conditions"""
    df = fetch_ohlcv(symbol, mid_term_timeframe)
    if df is None:
        return "Data Unavailable"
    
    df = calculate_rsi(df)
    
    # Moving average crossover signal
    ma_signal = moving_average_strategy(df, mid_window, long_window)
    
    # Check if there's a significant price loss
    price_loss_signal = detect_price_loss(df)

    # RSI signals for overbought or oversold conditions
    rsi_value = df['RSI'].iloc[-1]
    if rsi_value > 70:
        rsi_signal = "Sell (Overbought)"
    elif rsi_value < 30:
        rsi_signal = "Possibly Oversold (Hold)"
    else:
        rsi_signal = "No RSI sell signal"

    # Combining the signals to form a sell recommendation
    if ma_signal == "sell" or "Sell" in price_loss_signal or "Sell" in rsi_signal:
        return f"Sell Signal: {ma_signal}, {price_loss_signal}, {rsi_signal}"
    else:
        return "Hold"

def fetch_wallet_balances():
    """Fetch wallet balances for all cryptocurrencies in the user's account"""
    balances = exchange.fetch_balance()
    wallet = {}

    # Iterate through balances and only get assets with non-zero balances
    for currency, balance in balances['total'].items():
        if balance > 0:
            wallet[currency] = balance
    
    return wallet

def recommend_wallet_cryptos_to_sell():
    """Provide sell signals only for cryptocurrencies that are in the wallet"""
    sell_recommendations = []

    # Fetch wallet balances
    wallet = fetch_wallet_balances()

    # Iterate through the wallet holdings and apply sell signal detection
    for currency in wallet:
        symbol = f'{currency}/USDT'
        sell_signal = detect_sell_signals(symbol)
        
        if "Sell Signal" in sell_signal:
            sell_recommendations.append({
                "Symbol": symbol,
                "Sell Signal": sell_signal,
                "Balance": wallet[currency]
            })

    return pd.DataFrame(sell_recommendations)

# Run the bot and get sell recommendations for wallet holdings
sell_recommendations = recommend_wallet_cryptos_to_sell()

# Display sell recommendations
print(sell_recommendations)
