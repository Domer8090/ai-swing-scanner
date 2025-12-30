# indicators.py

import ta

def add_trend_indicators(df):
    df["EMA20"] = ta.trend.ema_indicator(df["Close"], 20)
    df["EMA50"] = ta.trend.ema_indicator(df["Close"], 50)
    df["SMA200"] = ta.trend.sma_indicator(df["Close"], 200)
    df["RSI"] = ta.momentum.rsi(df["Close"], 14)
    return df.dropna()

def add_meanrev_indicators(df):
    df["RSI"] = ta.momentum.rsi(df["Close"], 14)
    return df.dropna()
