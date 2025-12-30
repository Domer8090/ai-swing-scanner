# data.py

import yfinance as yf
import pandas as pd

def load_data(ticker, interval):
    df = yf.download(
        ticker,
        period="1y",
        interval=interval,
        progress=False
    )

    if df.empty:
        return pd.DataFrame()

    # 👇 CRITICAL FIX (no 2D arrays)
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    df.columns = df.columns.get_level_values(0)

    return df
