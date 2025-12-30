import yfinance as yf
import pandas as pd
import ta
import requests
from datetime import datetime
import os
import warnings

warnings.filterwarnings("ignore")

# =============================
# CONFIG
# =============================
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

LOOKBACK = "6mo"
MIN_PRICE = 20

TREND_TF = "4h"
MEANREV_TF = "1h"

RR_TREND_1 = 2
RR_TREND_2 = 3

# =============================
# TICKERS
# =============================
TICKERS = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","NFLX","AVGO",
    "AMD","INTC","ADBE","CRM","ORCL","QCOM","CSCO","IBM","TXN","MU",
    "NOW","SHOP","SNOW","UBER","PANW","CRWD","NET","DDOG","OKTA","ZS",
    "BA","CAT","DE","GE","HON","LMT","RTX","NOC","GD","JPM","BAC",
    "WFC","GS","MS","V","MA","AXP","KO","PEP","MCD","SBUX","COST",
    "WMT","HD","LOW","NKE","XOM","CVX","COP","SLB","OXY","JNJ","PFE",
    "MRK","ABBV","LLY","UNH","ABT","TMO"
]

print("🚀 Hybrid Swing Trading Scanner Running...\n")

# =============================
# DISCORD FUNCTION
# =============================
def send_discord(msg):
    if DISCORD_WEBHOOK:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})

# =============================
# DATA LOADER
# =============================
def load_data(ticker, tf):
    df = yf.download(
        ticker,
        period=LOOKBACK,
        interval=tf,
        progress=False
    )
    return df.dropna()

# =============================
# MAIN LOOP
# =============================
for ticker in TICKERS:
    print(f"🔍 Scanning {ticker}")

    try:
        # =============================
        # TREND MODULE (4H)
        # =============================
        df_trend = load_data(ticker, TREND_TF)

        if df_trend.empty or len(df_trend) < 250:
            continue

        if float(df_trend["Close"].iloc[-1]) < MIN_PRICE:
            continue

        df_trend["EMA20"] = ta.trend.ema_indicator(df_trend["Close"], 20)
        df_trend["EMA50"] = ta.trend.ema_indicator(df_trend["Close"], 50)
        df_trend["SMA200"] = ta.trend.sma_indicator(df_trend["Close"], 200)
        df_trend["RSI"] = ta.momentum.rsi(df_trend["Close"], 14)

        df_trend = df_trend.dropna()

        last = df_trend.iloc[-1]
        prev = df_trend.iloc[-2]

        trend_bias = (
            last["Close"].item() > last["SMA200"].item() and
            last["EMA20"].item() > last["EMA50"].item() > last["SMA200"].item()
        )

        pullback = (
            prev["Close"].item() > prev["EMA20"].item() and
            last["Close"].item() <= last["EMA20"].item()
        )

        rsi_ok = 40 <= last["RSI"].item() <= 55

        if trend_bias and pullback and rsi_ok:
            swing_low = df_trend["Low"].tail(6).min().item()

            entry = last["Close"].item()
            stop = swing_low * 0.995
            risk = entry - stop

            if risk > 0:
                tp1 = entry + risk * RR_TREND_1
                tp2 = entry + risk * RR_TREND_2

                send_discord(
                    f"📈 **TREND SETUP**\n"
                    f"Ticker: {ticker}\n"
                    f"Entry: ${entry:.2f}\n"
                    f"Stop: ${stop:.2f}\n"
                    f"TP1: ${tp1:.2f}\n"
                    f"TP2: ${tp2:.2f}\n"
                    f"RSI: {last['RSI'].item():.1f}\n"
                    f"TF: 4H\n"
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )

                print("✅ Trend alert sent")
                continue

        # =============================
        # MEAN REVERSION MODULE (1H)
        # =============================
        df_mr = load_data(ticker, MEANREV_TF)

        if df_mr.empty or len(df_mr) < 200:
            continue

        df_mr["EMA20"] = ta.trend.ema_indicator(df_mr["Close"], 20)
        df_mr["EMA50"] = ta.trend.ema_indicator(df_mr["Close"], 50)
        df_mr["RSI"] = ta.momentum.rsi(df_mr["Close"], 14)

        df_mr = df_mr.dropna()
        last = df_mr.iloc[-1]

        rsi_val = last["RSI"].item()

        if rsi_val < 10 or rsi_val > 90:
            direction = "LONG" if rsi_val < 10 else "SHORT"
            target = last["EMA20"].item()

            send_discord(
                f"⚡ **MEAN REVERSION SETUP**\n"
                f"Ticker: {ticker}\n"
                f"Direction: {direction}\n"
                f"Entry: ${last['Close'].item():.2f}\n"
                f"Target (EMA20): ${target:.2f}\n"
                f"RSI: {rsi_val:.1f}\n"
                f"TF: 1H\n"
                f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

            print("⚡ Mean reversion alert sent")

    except Exception as e:
        print(f"❌ Error on {ticker}: {e}")

print("\n✅ Scan complete.")


