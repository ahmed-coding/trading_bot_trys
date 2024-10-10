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

# Minimum profit threshold (10%)
profit_threshold = 0.10

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

def potential_profit_and_price(df):
    """Calculate potential price growth from past trends and expected price"""
    highest_close = df['close'].max()
    current_price = df['close'].iloc[-1]
    
    # Estimate potential growth percentage
    profit_percentage = (highest_close - current_price) / current_price
    
    # Calculate the expected price based on potential profit
    expected_price = current_price * (1 + profit_percentage)
    
    return profit_percentage, expected_price

def calculate_stop_loss_take_profit(current_price):
    """Calculate stop-loss and take-profit based on current price"""
    stop_loss = current_price * 0.95  # 5% below the current price
    take_profit = current_price * 1.10  # 10% above the current price
    return stop_loss, take_profit

def time_estimation():
    """Estimate time expectation based on current timeframe (15m or 30m)"""
    # For simplicity, returning either 15m or 30m
    return "15m - 30m"

def analyze_15m_profit(symbol):
    """Analyze 15-minute trading signals, profit potential, stop-loss, take-profit, and time estimation"""
    df = fetch_ohlcv(symbol, timeframe)
    if df is None:
        return "Data Unavailable", 0, 0, 0, 0, 0
    
    # Calculate technical indicators
    df = calculate_rsi(df)
    ma_signal = moving_average_strategy(df, short_window, long_window)
    
    # Calculate potential profit and expected price
    profit, expected_price = potential_profit_and_price(df)
    
    # Calculate stop-loss and take-profit
    current_price = df['close'].iloc[-1]
    stop_loss, take_profit = calculate_stop_loss_take_profit(current_price)
    
    # Get the time estimation (15m or 30m)
    time_frame = time_estimation()

    # Generate buy signal only if profit is greater than the threshold
    if profit >= profit_threshold:
        return f"Buy (Potential {profit * 100:.2f}% Profit)", profit, expected_price, stop_loss, take_profit, time_frame
    else:
        return "Hold", profit, expected_price, stop_loss, take_profit, time_frame

def recommend_15m_cryptos_with_profit():
    """Provide 15-minute trading signals with profit potential, stop-loss, take-profit, and time estimation"""
    recommendations = []
    
    # Fetch all tradable markets on the exchange
    markets = exchange.load_markets()
    
    for symbol in markets:
        market_data = markets[symbol]
        
        # Check if the market is active/tradable
        if market_data['active'] and '/USDT' in symbol:  # Filtering USDT pairs only
            signal, profit, expected_price, stop_loss, take_profit, time_frame = analyze_15m_profit(symbol)
            
            # Only add to recommendations if the potential profit is 10% or more
            if profit >= profit_threshold:
                recommendations.append({
                    "Symbol": symbol,
                    "Signal": signal,
                    "Potential Profit (%)": f"{profit * 100:.2f}",
                    "Expected Price": f"{expected_price:.2f}",
                    "Stop Loss": f"{stop_loss:.2f}",
                    "Take Profit": f"{take_profit:.2f}",
                    "Time": time_frame
                })
    
    return pd.DataFrame(recommendations)

# GUI using Tkinter
def display_recommendations():
    """Fetch and display 15-minute trading signals with profit potential, stop-loss, take-profit, and time estimation"""
    recommendations = recommend_15m_cryptos_with_profit()
    
    # Clear the treeview table
    for item in tree.get_children():
        tree.delete(item)

    # Insert new rows
    for index, row in recommendations.iterrows():
        tree.insert("", "end", values=(
            row["Symbol"], row["Signal"], row["Potential Profit (%)"], 
            row["Expected Price"], row["Stop Loss"], row["Take Profit"], row["Time"]
        ))

# Initialize Tkinter GUI
root = tk.Tk()
root.title("15-Minute Crypto Trading Signals with Stop Loss and Take Profit")

# Set up frame and table (Treeview)
frame = ttk.Frame(root, padding="10")
frame.grid(row=0, column=0)

# Table columns
columns = ("Symbol", "Signal", "Potential Profit (%)", "Expected Price", "Stop Loss", "Take Profit", "Time")
tree = ttk.Treeview(frame, columns=columns, show="headings")
tree.heading("Symbol", text="Symbol")
tree.heading("Signal", text="Signal")
tree.heading("Potential Profit (%)", text="Potential Profit (%)")
tree.heading("Expected Price", text="Expected Price")
tree.heading("Stop Loss", text="Stop Loss")
tree.heading("Take Profit", text="Take Profit")
tree.heading("Time", text="Time")

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
