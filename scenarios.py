from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

import numpy as np
import pandas as pd


@dataclass
class Scenario:
    name: str
    label: str
    start: pd.Timestamp
    end: pd.Timestamp
    bars: int


def _infer_bars_per_day(timestamps: pd.Series) -> int:
    diffs = pd.to_datetime(timestamps, errors="coerce").diff().dropna()
    if diffs.empty:
        return 96
    median = diffs.median()
    if pd.isna(median) or median == pd.Timedelta(0):
        return 96
    return max(1, int(round(pd.Timedelta(days=1) / median)))


def _segment_labels(labels: Iterable[str]) -> List[int]:
    seg = []
    current = 0
    prev = None
    for label in labels:
        if label != prev:
            current += 1
        seg.append(current)
        prev = label
    return seg


def extract_regime_scenarios(
    data: pd.DataFrame,
    timestamp_col: str = "Timestamp",
    price_col: str = "Close",
    vol_window_days: int = 7,
    trend_fast_span: int = 48,
    trend_slow_span: int = 192,
    min_days: int = 90,
    top_n: int = 1,
    vol_quantiles: tuple[float, float] = (0.3, 0.7),
    trend_quantile: float = 0.7,
) -> List[Scenario]:
    df = data.copy()
    if timestamp_col not in df.columns:
        raise ValueError(f"Missing {timestamp_col} column for scenario extraction.")
    df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors="coerce")
    df = df.dropna(subset=[timestamp_col])
    df = df.sort_values(timestamp_col)

    if price_col not in df.columns:
        raise ValueError(f"Missing {price_col} column for scenario extraction.")
    price = df[price_col].astype(float)

    bars_per_day = _infer_bars_per_day(df[timestamp_col])
    vol_window = max(10, int(vol_window_days * bars_per_day))

    returns = price.pct_change()
    vol = returns.rolling(vol_window).std()

    ema_fast = price.ewm(span=trend_fast_span, adjust=False).mean()
    ema_slow = price.ewm(span=trend_slow_span, adjust=False).mean()
    trend_strength = (ema_fast - ema_slow) / price.replace(0.0, np.nan)
    trend_abs = trend_strength.abs()

    vol_low = vol.quantile(vol_quantiles[0])
    vol_high = vol.quantile(vol_quantiles[1])
    trend_high = trend_abs.quantile(trend_quantile)

    vol_label = np.where(vol >= vol_high, "highvol", np.where(vol <= vol_low, "lowvol", "midvol"))
    trend_label = np.where(
        trend_abs >= trend_high,
        np.where(trend_strength >= 0, "bull", "bear"),
        "range",
    )

    labels = []
    for t_label, v_label in zip(trend_label, vol_label):
        if pd.isna(t_label):
            labels.append(None)
        else:
            labels.append(f"{t_label}_{v_label}")

    df["regime_label"] = labels
    df = df.dropna(subset=["regime_label"])

    if df.empty:
        return []

    min_bars = max(10, int(min_days * bars_per_day))
    df["segment"] = _segment_labels(df["regime_label"].tolist())
    segments = (
        df.groupby("segment")
        .agg(
            label=("regime_label", "first"),
            start=(timestamp_col, "first"),
            end=(timestamp_col, "last"),
            bars=("regime_label", "size"),
        )
        .reset_index(drop=True)
    )

    segments = segments[segments["bars"] >= min_bars]
    if segments.empty:
        return []

    scenarios: List[Scenario] = []
    for label, group in segments.groupby("label"):
        top = group.sort_values("bars", ascending=False).head(top_n)
        for idx, row in enumerate(top.itertuples(index=False), start=1):
            name = f"{label}_{idx}"
            scenarios.append(
                Scenario(
                    name=name,
                    label=label,
                    start=row.start,
                    end=row.end,
                    bars=int(row.bars),
                )
            )

    scenarios = sorted(scenarios, key=lambda s: s.start)
    return scenarios
