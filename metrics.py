from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def compute_returns(equity: pd.Series) -> pd.Series:
    return equity.pct_change().fillna(0.0)


def compute_drawdown(equity: pd.Series):
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_dd = float(drawdown.min()) if len(drawdown) else 0.0
    return drawdown, max_dd


def infer_periods_per_year(timestamps: pd.Series) -> float:
    if timestamps is None or timestamps.isnull().all():
        return 252.0
    ts = pd.to_datetime(timestamps, errors="coerce").dropna()
    if len(ts) < 2:
        return 252.0
    deltas = ts.diff().dropna().dt.total_seconds()
    median_seconds = float(deltas.median())
    if median_seconds <= 0:
        return 252.0
    seconds_per_year = 365.0 * 24.0 * 60.0 * 60.0
    return seconds_per_year / median_seconds


def summarize_trades(trades: pd.DataFrame) -> Dict[str, float]:
    if trades is None or trades.empty:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_trade": 0.0,
            "expectancy": 0.0,
        }

    pnl = trades["pnl"].astype(float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    win_rate = float(len(wins) / len(trades)) if len(trades) else 0.0
    profit_factor = float(wins.sum() / abs(losses.sum())) if len(losses) else float("inf")
    avg_trade = float(pnl.mean())
    expectancy = float(pnl.mean())

    return {
        "trades": int(len(trades)),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "avg_trade": avg_trade,
        "expectancy": expectancy,
    }
