import yfinance as yf
import pandas as pd
import ta
import requests
from datetime import datetime
import os
import warnings
import json
from pathlib import Path

MEMORY_FILE = Path("trade_memory.json")

if MEMORY_FILE.exists():
    trade_memory = json.loads(MEMORY_FILE.read_text())
else:
    trade_memory = {}


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

def log_ok(msg):
    print(f"   ✅ {msg}")

def log_warn(msg):
    print(f"   ⚠️  {msg}")

def log_no(msg):
    print(f"   ❌ {msg}")

def seen_before(ticker, setup):
    return trade_memory.get(ticker) == setup

def remember_trade(ticker, setup):
    trade_memory[ticker] = setup
    MEMORY_FILE.write_text(json.dumps(trade_memory, indent=2))


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
# DISCORD
# =============================
def send_discord(msg):
    if DISCORD_WEBHOOK:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})


# =============================
# DATA LOADER (ULTIMATE FIX)
# =============================
def load_data(ticker, timeframe):
    df = yf.download(
        ticker,
        period=LOOKBACK,
        interval=timeframe,
        progress=False,
        auto_adjust=False,
        group_by="column"
    )

    if df.empty:
        return df

    # Ensure flat columns (kills MultiIndex)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Force 1D Series for OHLCV
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.Series(
                df[col].values.ravel(),
                index=df.index
            )

    return df.dropna()


# =============================
# MAIN LOOP
# =============================
for ticker in TICKERS:
    print(f"\n🔍 Scanning {ticker}")

    try:
        # =============================
        # TREND MODULE (4H)
        # =============================
        df_trend = load_data(ticker, TREND_TF)

        if df_trend.empty:
            log_no("No trend data")
            continue

        if len(df_trend) < 250:
            log_no("Insufficient trend candles")
            continue

        last_price = float(df_trend["Close"].iloc[-1])
        if last_price < MIN_PRICE:
            log_no("Below minimum price filter")
            continue

        close = df_trend["Close"]
        low = df_trend["Low"]

        df_trend["EMA20"] = ta.trend.ema_indicator(close, 20)
        df_trend["EMA50"] = ta.trend.ema_indicator(close, 50)
        df_trend["SMA200"] = ta.trend.sma_indicator(close, 200)
        df_trend["RSI"] = ta.momentum.rsi(close, 14)

        df_trend = df_trend.dropna()

        last = df_trend.iloc[-1]
        prev = df_trend.iloc[-2]

        trend_bias = (
            last["Close"] > last["SMA200"] and
            last["EMA20"] > last["EMA50"] > last["SMA200"]
        )

        pullback = (
            prev["Close"] > prev["EMA20"] and
            last["Close"] <= last["EMA20"]
        )

        rsi_ok = 40 <= last["RSI"] <= 55

        if trend_bias and pullback and rsi_ok:
            swing_low = low.loc[df_trend.index].tail(6).min()
            entry = float(last["Close"])
            stop = swing_low * 0.995
            risk = entry - stop

            if risk <= 0:
                log_no("Trend detected but invalid risk")
            else:
                log_ok("TREND setup detected")
                send_discord(
                    f"📈 **TREND SETUP**\n"
                    f"Ticker: {ticker}\n"
                    f"Entry: ${entry:.2f}\n"
                    f"Stop: ${stop:.2f}\n"
                    f"TF: 4H"
                )
            continue
        else:
            reasons = []
            if not trend_bias:
                reasons.append("trend bias failed")
            if not pullback:
                reasons.append("no EMA20 pullback")
            if not rsi_ok:
                reasons.append("RSI not in 40–55")

            log_no("Trend module: " + ", ".join(reasons))

        # =============================
        # MEAN REVERSION MODULE (1H)
        # =============================
        df_mr = load_data(ticker, MEANREV_TF)

        if df_mr.empty or len(df_mr) < 200:
            log_no("No mean-reversion data")
            continue

        close = df_mr["Close"]
        df_mr["EMA20"] = ta.trend.ema_indicator(close, 20)
        df_mr["RSI"] = ta.momentum.rsi(close, 14)

        df_mr = df_mr.dropna()
        last = df_mr.iloc[-1]

        rsi_val = float(last["RSI"])

        if rsi_val < 10 or rsi_val > 90:
            log_ok("MEAN-REVERSION setup detected")
            send_discord(
                f"⚡ **MEAN REVERSION SETUP**\n"
                f"Ticker: {ticker}\n"
                f"RSI: {rsi_val:.1f}\n"
                f"TF: 1H"
            )
        else:
            log_no(f"Mean reversion RSI neutral ({rsi_val:.1f})")

    except Exception as e:
        print(f"   ❌ ERROR: {e}")


print("\n✅ Scan complete.")
