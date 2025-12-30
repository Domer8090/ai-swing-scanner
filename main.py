# main.py

from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from pathlib import Path
import json, csv
from datetime import datetime

from config import *
from data import load_data
from indicators import *
from discord_alerts import send_discord

# ========================
# Trade Memory
# ========================
MEMORY_FILE = Path("trade_memory.json")
trade_memory = json.loads(MEMORY_FILE.read_text()) if MEMORY_FILE.exists() else {}

def seen_before(ticker, setup):
    return trade_memory.get(ticker) == setup

def remember_trade(ticker, setup):
    trade_memory[ticker] = setup
    MEMORY_FILE.write_text(json.dumps(trade_memory, indent=2))

# ========================
# CSV Logging
# ========================
Path("logs").mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
CSV_FILE = Path("logs") / f"scan_{timestamp}.csv"
csv_rows = []

def log_csv(ticker, module, status, details=""):
    csv_rows.append([
        ticker, module, status, details,
        datetime.now().strftime("%H:%M:%S")
    ])

# ========================
# Summary
# ========================
summary = {
    "trend": [],
    "meanrev": [],
    "skipped": [],
    "errors": []
}

# ========================
# Core Scan
# ========================
def scan_ticker(ticker):
    try:
        # ---- Trend ----
        df = load_data(ticker, TREND_TF)
        if df.empty or len(df) < 250:
            summary["skipped"].append(ticker)
            return

        df = add_trend_indicators(df)
        last, prev = df.iloc[-1], df.iloc[-2]

        trend_ok = (
            last["Close"] > last["SMA200"] and
            last["EMA20"] > last["EMA50"] > last["SMA200"]
        )

        pullback = prev["Close"] > prev["EMA20"] and last["Close"] <= last["EMA20"]
        rsi_ok = 40 <= last["RSI"] <= 55

        if trend_ok and pullback and rsi_ok:
            if not seen_before(ticker, "TREND"):
                remember_trade(ticker, "TREND")
                summary["trend"].append(ticker)
                log_csv(ticker, "Trend", "Detected")
                send_discord(f"📈 **TREND SETUP** — {ticker}")
            return

        # ---- Mean Reversion ----
        df = load_data(ticker, MEANREV_TF)
        df = add_meanrev_indicators(df)

        rsi = df.iloc[-1]["RSI"]
        if rsi < 10 or rsi > 90:
            if not seen_before(ticker, "MEANREV"):
                remember_trade(ticker, "MEANREV")
                summary["meanrev"].append(ticker)
                log_csv(ticker, "MeanRev", "Detected", f"RSI {rsi:.1f}")
                send_discord(f"⚡ **MEAN REVERSION** — {ticker} | RSI {rsi:.1f}")

    except Exception as e:
        summary["errors"].append(ticker)
        log_csv(ticker, "Error", "Failed", str(e))

# ========================
# Run Scanner
# ========================
print("\n🚀 Hybrid Swing Scanner Running...\n")

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
    futures = [exe.submit(scan_ticker, t) for t in TICKERS]
    for _ in tqdm(as_completed(futures), total=len(futures)):
        pass

# ========================
# Write CSV
# ========================
with open(CSV_FILE, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Ticker", "Module", "Status", "Details", "Time"])
    writer.writerows(csv_rows)

# ========================
# Discord Summary
# ========================
send_discord(
    f"📊 **SCAN COMPLETE**\n"
    f"📈 Trend: {len(summary['trend'])} → {summary['trend']}\n"
    f"⚡ MeanRev: {len(summary['meanrev'])} → {summary['meanrev']}\n"
    f"⏭ Skipped: {len(summary['skipped'])}\n"
    f"❌ Errors: {len(summary['errors'])}\n"
    f"🗂 Log: `{CSV_FILE.name}`"
)
