import yfinance as yf
import pandas as pd
import ta
import requests
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")


# =============================
# CONFIG
# =============================
import os
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")


TIMEFRAME = "4h"
LOOKBACK = "6mo"
MIN_PRICE = 20

RR_1 = 2
RR_2 = 3

# =============================
# LARGE CAP STOCKS (100+)
# =============================
TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "NFLX", "AVGO",
    "AMD", "INTC", "ADBE", "CRM", "ORCL", "QCOM", "CSCO", "IBM", "TXN", "MU",
    "NOW", "SHOP", "SNOW", "UBER", "PANW", "CRWD", "NET", "DDOG", "OKTA", "ZS",
    "BA", "CAT", "DE", "GE", "HON", "LMT", "RTX", "NOC", "GD", "JPM", "BAC",
    "WFC", "GS", "MS", "V", "MA", "AXP", "KO", "PEP", "MCD", "SBUX", "COST",
    "WMT", "HD", "LOW", "NKE", "XOM", "CVX", "COP", "SLB", "OXY", "JNJ", "PFE",
    "MRK", "ABBV", "LLY", "UNH", "ABT", "TMO"
]

print("📊 AI Swing Scanner is running...\n")


# =============================
# DISCORD ALERT FUNCTION
# =============================
def send_discord(message):
    payload = {"content": message}
    requests.post(DISCORD_WEBHOOK, json=payload)


# =============================
# MAIN LOOP
# =============================
for ticker in TICKERS:
    print(f"Scanning {ticker}...")

    try:
        df = yf.download(ticker,
                         period=LOOKBACK,
                         interval=TIMEFRAME,
                         progress=False)

        if df.empty or len(df) < 200:
            print("No data.\n")
            continue

        close = df["Close"].squeeze()
        high = df["High"].squeeze()
        low = df["Low"].squeeze()

        if close.iloc[-1] < MIN_PRICE:
            print("Below price filter.\n")
            continue

        df["EMA20"] = ta.trend.ema_indicator(close, 20)
        df["EMA50"] = ta.trend.ema_indicator(close, 50)
        df["EMA200"] = ta.trend.ema_indicator(close, 200)
        df["RSI"] = ta.momentum.rsi(close, 14)

        # 🔥 DROP NaN ROWS (CRITICAL FIX)
        df = df.dropna()

        last = df.iloc[-1]
        prev = df.iloc[-2]

        ema20 = last["EMA20"].item()
        ema50 = last["EMA50"].item()
        ema200 = last["EMA200"].item()
        rsi = last["RSI"].item()

        close_last = last["Close"].item()
        close_prev = prev["Close"].item()
        ema20_prev = prev["EMA20"].item()

        trend_ok = ema50 > ema200
        pullback = close_prev > ema20_prev and close_last <= ema20
        rsi_ok = 40 <= rsi <= 55

        if not (trend_ok and pullback and rsi_ok):
            print("No setup.\n")
            continue

        swing_low = low.tail(5).min()
        entry = last["Close"]
        stop = swing_low * 0.995

        risk = entry - stop
        if risk <= 0:
            print("Invalid risk.\n")
            continue

        tp1 = entry + risk * RR_1
        tp2 = entry + risk * RR_2

        message = (f"🚨 **SWING TRADE SETUP** 🚨\n\n"
                   f"📈 **Ticker:** {ticker}\n"
                   f"💵 **Entry:** ${entry:.2f}\n"
                   f"🛑 **Stop:** ${stop:.2f}\n"
                   f"🎯 **TP1 (1:2):** ${tp1:.2f}\n"
                   f"🎯 **TP2 (1:3):** ${tp2:.2f}\n"
                   f"📊 **RSI:** {last['RSI']:.1f}\n"
                   f"⏱ **Timeframe:** 4H\n"
                   f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        send_discord(message)
        print("✅ ALERT SENT\n")

    except Exception as e:
        print(f"❌ Error on {ticker}: {e}\n")
