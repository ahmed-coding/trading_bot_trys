import ccxt
import pandas as pd
import numpy as np
import tkinter as tk
from tkinter import ttk

# Exchange setup (Binance)
api_key = 'nHCAKjf112bSWMutN58GEevqhOZ2KqjP91IrW2xXMhbBHGIZuNU76QurKibiFNS9'
api_secret = '2HFcVh6bJrMNTqUCSJ1ZHjFdteyLxujXSdVXiCkIwt8huJvczA9WqH7mJDfq29yl'

exchange = ccxt.binance({
    'apiKey': api_key,
    'secret': api_secret,
})

# Define 15-minute timeframe for real-time trading
timeframe = '15m'

# Technical indicator settings
short_window = 7   # 7-period moving average for short term
long_window = 25   # 25-period moving average for long term
rsi_period = 14    # 14-period RSI for momentum analysis

def fetch_ohlcv(symbol, timeframe):
    """Fetch 15-minute interval OHLCV data for the given symbol"""
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

def analyze_15m_signal(symbol):
    """Analyze 15-minute trading signals using technical indicators"""
    df = fetch_ohlcv(symbol, timeframe)
    if df is None:
        return "Data Unavailable"
    
    # Calculate technical indicators
    df = calculate_rsi(df)
    ma_signal = moving_average_strategy(df, short_window, long_window)
    rsi_value = df['RSI'].iloc[-1]

    # Generate signals based on RSI and Moving Average Crossover
    if ma_signal == "buy" and rsi_value < 30:
        return "Strong Buy (Oversold)"
    elif ma_signal == "buy":
        return "Buy"
    elif ma_signal == "sell" and rsi_value > 70:
        return "Strong Sell (Overbought)"
    elif ma_signal == "sell":
        return "Sell"
    else:
        return "Hold"

def recommend_15m_cryptos():
    """Provide 15-minute trading signals for selected cryptocurrencies"""
    recommendations = []
    
    # List of cryptocurrencies to monitor (you can modify this list)
    symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'ADA/USDT', 'SOL/USDT']

    for symbol in symbols:
        signal = analyze_15m_signal(symbol)
        recommendations.append({
            "Symbol": symbol,
            "Signal": signal
        })
    
    return pd.DataFrame(recommendations)

# GUI using Tkinter
def display_recommendations():
    """Fetch and display 15-minute trading signals in the GUI"""
    recommendations = recommend_15m_cryptos()
    
    # Clear the treeview table
    for item in tree.get_children():
        tree.delete(item)

    # Insert new rows
    for index, row in recommendations.iterrows():
        tree.insert("", "end", values=(row["Symbol"], row["Signal"]))

# Initialize Tkinter GUI
root = tk.Tk()
root.title("15-Minute Crypto Trading Signals")

# Set up frame and table (Treeview)
frame = ttk.Frame(root, padding="10")
frame.grid(row=0, column=0)

# Table columns
columns = ("Symbol", "Signal")
tree = ttk.Treeview(frame, columns=columns, show="headings")
tree.heading("Symbol", text="Symbol")
tree.heading("Signal", text="Signal")

tree.grid(row=0, column=0, sticky="nsew")

# Scrollbar for the table
scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
tree.configure(yscroll=scrollbar.set)
scrollbar.grid(row=0, column=1, sticky="ns")

# Refresh button to fetch and display 15-minute trading signals
refresh_button = ttk.Button(frame, text="Refresh Data", command=display_recommendations)
refresh_button.grid(row=1, column=0, pady=10)

# Run the GUI loop
root.mainloop()
