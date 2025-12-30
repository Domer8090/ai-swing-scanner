import yfinance as yf
import pandas as pd
import ta
import requests
import json
import csv
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import warnings
warnings.filterwarnings("ignore")

# =============================
# CONFIG
# =============================
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1455354899150667839/vaMCrKJOURYETwVb4x9y3ELSpzVxPJSLwJxXF7-DjPCcyNmczeukJhikQK6IcbljDqQW"

TREND_TF = "4h"
MEANREV_TF = "1h"
LOOKBACK = "6mo"
MIN_PRICE = 20
MAX_WORKERS = 8

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

# =============================
# FILE SYSTEM
# =============================
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
CSV_FILE = LOG_DIR / f"scan_{timestamp}.csv"

MEMORY_FILE = Path("trade_memory.json")
trade_memory = json.loads(MEMORY_FILE.read_text()) if MEMORY_FILE.exists() else {}

csv_rows = []
summary = {"trend": [], "meanrev": [], "errors": []}

# =============================
# DISCORD
# =============================
def send_discord(message=None, file_path=None):
    payload = {}
    files = {}

    if message:
        payload["content"] = message

    if file_path:
        files["file"] = open(file_path, "rb")

    requests.post(DISCORD_WEBHOOK, data=payload, files=files)

# =============================
# HELPERS
# =============================
def remember(ticker, setup):
    trade_memory[ticker] = setup
    MEMORY_FILE.write_text(json.dumps(trade_memory, indent=2))

def seen(ticker, setup):
    return trade_memory.get(ticker) == setup

def log_csv(ticker, module, status, details=""):
    csv_rows.append([
        ticker, module, status, details,
        datetime.now().strftime("%H:%M:%S")
    ])

def load_data(ticker, tf):
    df = yf.download(ticker, period=LOOKBACK, interval=tf, progress=False)
    if df.empty:
        return pd.DataFrame()

    # FORCE 1D SERIES (fixes ta bug)
    for col in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]:
        if col in df.columns:
            df[col] = df[col].squeeze()

    return df


# =============================
# SCAN FUNCTION
# =============================
def scan_ticker(ticker):
    try:
        df = load_data(ticker, TREND_TF)
        if df.empty or len(df) < 200:
            return

        close = df["Close"].squeeze()
        low = df["Low"].squeeze()



        df["EMA20"] = ta.trend.ema_indicator(close, 20)
        df["EMA50"] = ta.trend.ema_indicator(close, 50)
        df["SMA200"] = ta.trend.sma_indicator(close, 200)
        df["RSI"] = ta.momentum.rsi(close, 14)
        df = df.dropna()

        last, prev = df.iloc[-1], df.iloc[-2]

        trend_ok = (
            last["Close"] > last["SMA200"] and
            last["EMA20"] > last["EMA50"] > last["SMA200"]
        )

        pullback = (
            (prev["Close"] > prev["EMA20"] and last["Close"] <= last["EMA20"]) or
            (prev["Close"] > prev["EMA50"] and last["Close"] <= last["EMA50"])
        )

        rsi_ok = 38 <= last["RSI"] <= 60

        if trend_ok and pullback and rsi_ok:
            if not seen(ticker, "TREND"):
                remember(ticker, "TREND")
                summary["trend"].append(ticker)
                log_csv(ticker, "Trend", "Detected")
                send_discord(f"📈 **TREND SETUP** — {ticker}")
            return

        # Mean Reversion
        df_mr = load_data(ticker, MEANREV_TF)
        if df_mr.empty:
            return

        close_mr = df_mr["Close"].squeeze()
        rsi = ta.momentum.rsi(close_mr, 14).dropna().iloc[-1]

        if rsi < 20 or rsi > 80:
            if not seen(ticker, "MEANREV"):
                remember(ticker, "MEANREV")
                summary["meanrev"].append(ticker)
                log_csv(ticker, "MeanRev", "Detected", f"RSI={rsi:.1f}")
                send_discord(f"⚡ **MEAN REVERSION** — {ticker} | RSI {rsi:.1f}")

    except Exception as e:
        summary["errors"].append(ticker)
        log_csv(ticker, "Error", "Failed", str(e))

# =============================
# RUN
# =============================
print("🚀 Hybrid Swing Scanner Running...\n")

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = [executor.submit(scan_ticker, t) for t in TICKERS]
    for _ in tqdm(as_completed(futures), total=len(futures)):
        pass

# =============================
# WRITE CSV
# =============================
with open(CSV_FILE, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Ticker","Module","Status","Details","Time"])
    writer.writerows(csv_rows)

# =============================
# SEND CSV TO DISCORD
# =============================
send_discord("📁 **Scan CSV Log Attached**", file_path=CSV_FILE)

# =============================
# SUMMARY
# =============================
summary_msg = (
    f"📊 **SCAN COMPLETE**\n\n"
    f"📈 Trend: {len(summary['trend'])} → {summary['trend']}\n"
    f"⚡ MeanRev: {len(summary['meanrev'])} → {summary['meanrev']}\n"
    f"❌ Errors: {len(summary['errors'])}\n"
    f"🗂 Log: `{CSV_FILE.name}`"
)
send_discord(summary_msg)
