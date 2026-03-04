import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

from Cls_Strategy import Strategy

DATE_FORMAT = "%d-%m-%Y %H:%M:%S"
DEFAULT_DATE_FROM = "28-11-2019 00:00:00"
DEFAULT_DATE_TO = "28-11-2019 10:00:00"
date_from = DEFAULT_DATE_FROM
date_to = DEFAULT_DATE_TO

def timer(function):

    def fct_in_between(*args, **kwargs):
        start = time.time()
        res = function(*args, **kwargs)
        end = time.time()
        print("--- %s seconds ---" % (end - start))
        return res
        
    return fct_in_between

def df_sub_from_dates(data, date_from, date_to):
    obj_date_from = pd.to_datetime(date_from, format=DATE_FORMAT, errors="coerce")
    obj_date_to = pd.to_datetime(date_to, format=DATE_FORMAT, errors="coerce")
    if obj_date_from is pd.NaT or obj_date_to is pd.NaT:
        raise ValueError(f"Dates invalides. Format attendu: {DATE_FORMAT}")

    sub_data = data[(data["Timestamp"] > obj_date_from) & (data["Timestamp"] < obj_date_to)]
    return sub_data.ffill()


def _generate_synthetic_btc(date_from, date_to, freq="1min"):
    start = pd.to_datetime(date_from, format=DATE_FORMAT)
    end = pd.to_datetime(date_to, format=DATE_FORMAT)
    idx = pd.date_range(start=start, end=end, freq=freq)
    rng = np.random.default_rng(42)
    steps = rng.normal(loc=0.0, scale=2.0, size=len(idx))
    price = 10000 + np.cumsum(steps)
    df = pd.DataFrame({"Timestamp": idx, "Close": price})
    return df


def load_btc_data(csv_path=None, date_from=DEFAULT_DATE_FROM, date_to=DEFAULT_DATE_TO):
    if csv_path is None:
        env_path = os.getenv("BTC_CSV_PATH")
        csv_path = Path(env_path) if env_path else (Path(__file__).resolve().parent / "data" / "btc_1min_sample.csv")
    else:
        csv_path = Path(csv_path)

    if csv_path and csv_path.exists():
        df = pd.read_csv(csv_path)
        if "Timestamp" in df.columns:
            if pd.api.types.is_numeric_dtype(df["Timestamp"]):
                df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="s", errors="coerce")
            else:
                df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        elif "Date" in df.columns:
            df["Timestamp"] = pd.to_datetime(df["Date"], errors="coerce")
        else:
            raise ValueError("Le CSV doit contenir une colonne 'Timestamp' ou 'Date'.")

        if "Close" not in df.columns and "close" in df.columns:
            df["Close"] = df["close"]
        if "Close" not in df.columns:
            raise ValueError("Le CSV doit contenir une colonne 'Close'.")

        df = df.dropna(subset=["Timestamp", "Close"])
    else:
        df = _generate_synthetic_btc(date_from, date_to)

    period_14 = 14
    period_50 = 50
    df["MA_14"] = df["Close"].ewm(com=period_14 - 1, adjust=True).mean()
    df["MA_50"] = df["Close"].ewm(com=period_50 - 1, adjust=True).mean()
    return df

def sub_bitcoin_historic(window=14, threshold=0.02):  
    sub_data = df_sub_from_dates(data, DEFAULT_DATE_FROM, DEFAULT_DATE_TO)
    #local_min_idx = argrelmin(sub_data["Close"])

    # lookthrough to find signals     
    mean_rev = Strategy(sub_data, ma_window=window, threshold=threshold)
    df_meanR = mean_rev.generate_signals()
    df_meanR_signal = df_meanR[df_meanR["Signal"] != 0]
    
    buy, _ = df_meanR_signal[df_meanR_signal["Signal"] == 1].shape
    sell, _ = df_meanR_signal[df_meanR_signal["Signal"] == -1].shape
    return buy, sell

data = load_btc_data()
