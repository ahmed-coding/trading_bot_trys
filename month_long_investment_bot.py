import ccxt
import pandas as pd
import numpy as np
import tkinter as tk
from tkinter import ttk
import time

# Exchange setup (Binance)
api_key = 'nHCAKjf112bSWMutN58GEevqhOZ2KqjP91IrW2xXMhbBHGIZuNU76QurKibiFNS9'
api_secret = '2HFcVh6bJrMNTqUCSJ1ZHjFdteyLxujXSdVXiCkIwt8huJvczA9WqH7mJDfq29yl'

exchange = ccxt.binance({
    'apiKey': api_key,
    'secret': api_secret,
    'timeout': 30000,  # Set a 30-second timeout for API requests
    'enableRateLimit': True  # Enable rate limiting
})

# Define 15-minute timeframe for real-time trading
timeframe = '15m'

# Technical indicator settings
short_window = 7   # 7-period moving average for short term
long_window = 25   # 25-period moving average for long term
rsi_period = 14    # 14-period RSI for momentum analysis

# Minimum profit threshold (50% for this bot)
profit_threshold = 0.50

def fetch_ohlcv(symbol, timeframe):
    """Fetch 15-minute interval OHLCV data for the given symbol"""
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except ccxt.RequestTimeout:
        print(f"Request timed out for {symbol}. Retrying...")
        time.sleep(1)  # Wait a second before retrying
        return fetch_ohlcv(symbol, timeframe)
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

def potential_profit_and_price(df):
    """Calculate potential price growth from past trends and expected price"""
    highest_close = df['close'].max()
    current_price = df['close'].iloc[-1]
    
    if current_price == 0:
        return 0, 0

    # Estimate potential growth percentage
    profit_percentage = (highest_close - current_price) / current_price
    
    # Calculate the expected price based on potential profit
    expected_price = current_price * (1 + profit_percentage)
    
    return profit_percentage, expected_price

def analyze_15m_profit(symbol):
    """Analyze 15-minute trading signals and profit potential"""
    df = fetch_ohlcv(symbol, timeframe)
    if df is None or df.empty:
        return "Data Unavailable", 0, 0
    
    # Calculate technical indicators
    df = calculate_rsi(df)
    ma_signal = moving_average_strategy(df, short_window, long_window)
    
    # Calculate potential profit and expected price
    profit, expected_price = potential_profit_and_price(df)

    # Generate buy signal only if profit is greater than the threshold
    if profit >= profit_threshold:
        return f"Buy (Potential {profit * 100:.2f}% Profit)", profit, expected_price
    else:
        return "Hold", profit, expected_price

def recommend_cryptos_with_high_growth():
    """Provide 15-minute trading signals with at least 50% profit potential and expected price"""
    recommendations = []
    
    # Fetch all available markets on the exchange (e.g., USDT pairs)
    markets = exchange.load_markets()
    
    for symbol in markets:
        # Only analyze symbols that are traded against USDT (or another base currency)
        if '/USDT' in symbol:
            signal, profit, expected_price = analyze_15m_profit(symbol)
            
            # Only add to recommendations if the potential profit is 50% or more
            if profit >= profit_threshold:
                recommendations.append({
                    "Symbol": symbol,
                    "Signal": signal,
                    "Potential Profit (%)": f"{profit * 100:.2f}",
                    "Expected Price": f"{expected_price:.2f}"
                })
    
    return pd.DataFrame(recommendations)

# GUI using Tkinter
def display_recommendations():
    """Fetch and display 15-minute trading signals with profit potential and expected price in the GUI"""
    recommendations = recommend_cryptos_with_high_growth()
    
    # Clear the treeview table
    for item in tree.get_children():
        tree.delete(item)

    # Insert new rows
    for index, row in recommendations.iterrows():
        tree.insert("", "end", values=(row["Symbol"], row["Signal"], row["Potential Profit (%)"], row["Expected Price"]))

# Initialize Tkinter GUI
root = tk.Tk()
root.title("Crypto Trading Signals with 50% Growth Potential")

# Set up frame and table (Treeview)
frame = ttk.Frame(root, padding="10")
frame.grid(row=0, column=0)

# Table columns
columns = ("Symbol", "Signal", "Potential Profit (%)", "Expected Price")
tree = ttk.Treeview(frame, columns=columns, show="headings")
tree.heading("Symbol", text="Symbol")
tree.heading("Signal", text="Signal")
tree.heading("Potential Profit (%)", text="Potential Profit (%)")
tree.heading("Expected Price", text="Expected Price")

tree.grid(row=0, column=0, sticky="nsew")

# Scrollbar for the table
scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
tree.configure(yscroll=scrollbar.set)
scrollbar.grid(row=0, column=1, sticky="ns")

# Refresh button to fetch and display trading signals with profit potential and expected price
refresh_button = ttk.Button(frame, text="Refresh Data", command=display_recommendations)
refresh_button.grid(row=1, column=0, pady=10)

# Run the GUI loop
root.mainloop()
