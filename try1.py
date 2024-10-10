import tkinter as tk
from tkinter import ttk
import ccxt
import pandas as pd
import time

# Exchange setup
api_key = 'nHCAKjf112bSWMutN58GEevqhOZ2KqjP91IrW2xXMhbBHGIZuNU76QurKibiFNS9'
api_secret = '2HFcVh6bJrMNTqUCSJ1ZHjFdteyLxujXSdVXiCkIwt8huJvczA9WqH7mJDfq29yl'

exchange = ccxt.binance({
    'apiKey': api_key,
    'secret': api_secret,
})

# List of cryptocurrencies to monitor
symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT','PEPE/USDT']

# Moving averages settings
short_window = 10  # Short-term moving average
long_window = 30   # Long-term moving average

def fetch_ohlcv(symbol, timeframe='1m'):
    """Fetch historical OHLCV data for the given symbol"""
    bars = exchange.fetch_ohlcv(symbol, timeframe)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def moving_average_strategy(df):
    """Moving Average Crossover Strategy"""
    df['SMA_short'] = df['close'].rolling(window=short_window).mean()
    df['SMA_long'] = df['close'].rolling(window=long_window).mean()

    # Buy signal: Short-term MA crosses above long-term MA
    if df['SMA_short'].iloc[-1] > df['SMA_long'].iloc[-1]:
        return "buy"
    # Sell signal: Short-term MA crosses below long-term MA
    elif df['SMA_short'].iloc[-1] < df['SMA_long'].iloc[-1]:
        return "sell"
    else:
        return "hold"

def update_signals():
    """Update the trading signals for each cryptocurrency"""
    for symbol in symbols:
        df = fetch_ohlcv(symbol)
        signal = moving_average_strategy(df)
        table.insert("", "end", values=(symbol, df['close'].iloc[-1], signal))

def refresh_data():
    """Refresh the data and update GUI"""
    for row in table.get_children():
        table.delete(row)
    update_signals()

# GUI setup
root = tk.Tk()
root.title("Crypto Trading Bot")

frame = ttk.Frame(root, padding="10")
frame.grid(row=0, column=0)

# Table for displaying data
columns = ("Symbol", "Current Price", "Signal")
table = ttk.Treeview(frame, columns=columns, show="headings")
table.heading("Symbol", text="Symbol")
table.heading("Current Price", text="Current Price")
table.heading("Signal", text="Signal")

table.grid(row=0, column=0, sticky="nsew")

# Scrollbar
scrollbar = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
table.configure(yscroll=scrollbar.set)
scrollbar.grid(row=0, column=1, sticky="ns")

# Button to refresh data
refresh_button = ttk.Button(frame, text="Refresh Data", command=refresh_data)
refresh_button.grid(row=1, column=0, pady=10)

# Periodically refresh data every 60 seconds
def auto_refresh():
    refresh_data()
    root.after(60000, auto_refresh)

# Start refreshing automatically
root.after(1000, auto_refresh)

# Run the GUI
root.mainloop()
