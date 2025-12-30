import yfinance as yf
import pandas as pd
import numpy as np
import ta
import os
import csv
import json
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from utils.market import market_is_open

if not market_is_open():
    print("⏭ Market closed — scan skipped")
    exit()


# =========================
# CONFIG
# =========================

TICKERS = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","NFLX",
    "AMD","INTC","AVGO","CRM","ADBE","ORCL","QCOM","CSCO",
    "JPM","BAC","WFC","GS","MS","V","MA","AXP",
    "KO","PEP","MCD","SBUX","COST","WMT"
]

TIMEFRAME_TREND = "1d"
TIMEFRAME_MEANREV = "1h"
LOOKBACK = "1y"
MAX_WORKERS = 8

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")  # set in GitHub Secrets
MEMORY_FILE = "trade_memory.json"
LOG_DIR = "logs"

os.makedirs(LOG_DIR, exist_ok=True)

# =========================
# MEMORY
# =========================

if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "r") as f:
        MEMORY = json.load(f)
else:
    MEMORY = {}

def remember(key):
    MEMORY[key] = datetime.utcnow().isoformat()
    with open(MEMORY_FILE, "w") as f:
        json.dump(MEMORY, f, indent=2)

def seen(key):
    return key in MEMORY

# =========================
# DATA LOADER (CRITICAL FIX)
# =========================

def load_data(ticker, tf):
    df = yf.download(
        ticker,
        period=LOOKBACK,
        interval=tf,
        progress=False,
        auto_adjust=False
    )

    if df.empty:
        return pd.DataFrame()

    # 🔥 flatten MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 🔥 force 1D Series
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.Series(df[col].values, index=df.index)

    return df.dropna()

# =========================
# STRATEGIES
# =========================

def trend_strategy(ticker):
    df = load_data(ticker, TIMEFRAME_TREND)
    if df.empty or len(df) < 100:
        return None

    close = df["Close"]
    ema20 = ta.trend.ema_indicator(close, 20)
    ema50 = ta.trend.ema_indicator(close, 50)

    ema20, ema50 = ema20.align(ema50, join="inner")
    close = close.loc[ema20.index]

    if close.iloc[-1] > ema20.iloc[-1] > ema50.iloc[-1]:
        return "EMA Bull Trend"

    return None

def mean_reversion_strategy(ticker):
    df = load_data(ticker, TIMEFRAME_MEANREV)
    if df.empty or len(df) < 50:
        return None

    close = df["Close"]
    rsi = ta.momentum.rsi(close, 14).dropna()

    if rsi.empty:
        return None

    if rsi.iloc[-1] < 30:
        return f"RSI Oversold ({round(rsi.iloc[-1],1)})"

    return None

# =========================
# DISCORD
# =========================

def send_discord(title, lines):
    if not DISCORD_WEBHOOK:
        return

    content = f"**{title}**\n" + "\n".join(lines)
    requests.post(DISCORD_WEBHOOK, json={"content": content})

# =========================
# SCANNER
# =========================

def scan_ticker(ticker):
    now = datetime.utcnow().strftime("%H:%M:%S")
    results = []

    try:
        trend = trend_strategy(ticker)
        if trend:
            key = f"{ticker}_TREND"
            if not seen(key):
                remember(key)
                results.append((ticker, "Trend", "Detected", trend, now))
            else:
                results.append((ticker, "Trend", "Skipped", "Seen before", now))

        meanrev = mean_reversion_strategy(ticker)
        if meanrev:
            key = f"{ticker}_MEANREV"
            if not seen(key):
                remember(key)
                results.append((ticker, "MeanRev", "Detected", meanrev, now))
            else:
                results.append((ticker, "MeanRev", "Skipped", "Seen before", now))

        if not results:
            results.append((ticker, "None", "Skipped", "No setup", now))

    except Exception as e:
        results.append((ticker, "Error", "Failed", str(e), now))

    return results

# =========================
# MAIN
# =========================

def main():
    print("\n🚀 AI Swing Scanner Running...\n")

    all_rows = []
    trend_hits = []
    meanrev_hits = []
    errors = 0

    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M")
    csv_path = f"{LOG_DIR}/scan_{timestamp}.csv"

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(scan_ticker, t): t for t in TICKERS}

        for future in tqdm(as_completed(futures), total=len(TICKERS)):
            rows = future.result()
            for row in rows:
                all_rows.append(row)
                ticker, module, status, details, _ = row

                if status == "Detected" and module == "Trend":
                    trend_hits.append(f"{ticker} → {details}")
                elif status == "Detected" and module == "MeanRev":
                    meanrev_hits.append(f"{ticker} → {details}")
                elif module == "Error":
                    errors += 1

    # CSV LOG
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Ticker", "Module", "Status", "Details", "Time"])
        writer.writerows(all_rows)

    # TERMINAL SUMMARY
    print("\n📊 SCAN COMPLETE")
    print(f"📈 Trend: {len(trend_hits)} → {trend_hits}")
    print(f"⚡ MeanRev: {len(meanrev_hits)} → {meanrev_hits}")
    print(f"❌ Errors: {errors}")
    print(f"🗂 Log: {csv_path}\n")

    # DISCORD ALERTS
    if trend_hits:
        send_discord("📈 TREND SETUPS", trend_hits)

    if meanrev_hits:
        send_discord("⚡ MEAN REVERSION", meanrev_hits)

    send_discord(
        "📊 SCAN COMPLETE",
        [
            f"Trend: {len(trend_hits)}",
            f"MeanRev: {len(meanrev_hits)}",
            f"Errors: {errors}",
            f"Log: {os.path.basename(csv_path)}"
        ]
    )

if __name__ == "__main__":
    main()
