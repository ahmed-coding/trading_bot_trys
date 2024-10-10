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

# Define timeframe for short and long term
short_term_timeframe = '1h'  # 1-hour candles for short term
long_term_timeframe = '1d'   # 1-day candles for long term

# Moving averages settings
short_window = 14  # Short-term moving average
long_window = 50   # Long-term moving average

# RSI settings
rsi_period = 14

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

def moving_average_strategy(df):
    """Moving Average Crossover Strategy"""
    df['SMA_short'] = df['close'].rolling(window=short_window).mean()
    df['SMA_long'] = df['close'].rolling(window=long_window).mean()

    if df['SMA_short'].iloc[-1] > df['SMA_long'].iloc[-1]:
        return "buy"
    elif df['SMA_short'].iloc[-1] < df['SMA_long'].iloc[-1]:
        return "sell"
    else:
        return "hold"

def analyze_short_term(symbol):
    """Analyze short-term investment potential based on technical analysis"""
    df = fetch_ohlcv(symbol, short_term_timeframe)
    if df is None:
        return "Data Unavailable"

    df = calculate_rsi(df)

    ma_signal = moving_average_strategy(df)
    rsi_value = df['RSI'].iloc[-1]

    # Short-term recommendation based on RSI and MA crossover
    if ma_signal == "buy" and rsi_value < 30:
        return "Strong Buy (Oversold)"
    elif ma_signal == "buy":
        return "Buy"
    elif ma_signal == "sell" and rsi_value > 70:
        return "Strong Sell (Overbought)"
    else:
        return "Hold"

def analyze_long_term(symbol):
    """Analyze long-term investment potential based on fundamentals and price trend"""
    df = fetch_ohlcv(symbol, long_term_timeframe)
    if df is None:
        return "Data Unavailable"

    df = calculate_rsi(df)

    ma_signal = moving_average_strategy(df)
    market_cap = exchange.fetch_ticker(symbol)['quoteVolume']  # A proxy for market cap

    # Long-term recommendation based on market cap, RSI, and moving average trend
    if market_cap > 1e9 and ma_signal == "buy" and df['RSI'].iloc[-1] < 50:
        return "Long-term Buy (Strong Market)"
    elif market_cap < 1e9:
        return "High-risk Investment"
    elif ma_signal == "sell":
        return "Sell"
    else:
        return "Hold"

def recommend_all_cryptos():
    """Provide recommendations for all available cryptocurrencies in short and long term"""
    recommendations = []
    
    # Fetch all markets available on the exchange
    markets = exchange.load_markets()
    
    for symbol in markets:
        # Filter symbols to focus on USDT pairs (or other base currencies)
        if '/USDT' in symbol:
            short_term_recommendation = analyze_short_term(symbol)
            long_term_recommendation = analyze_long_term(symbol)
            
            recommendations.append({
                "Symbol": symbol,
                "Short-term": short_term_recommendation,
                "Long-term": long_term_recommendation
            })
    
    return pd.DataFrame(recommendations)

# Run the bot and get recommendations for all available cryptocurrencies
recommendations = recommend_all_cryptos()

# Display recommendations
print(recommendations)
