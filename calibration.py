from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from Cls_Strategy import MeanReversionStrategyV2
from Mod_BTC import DEFAULT_DATE_FROM, DEFAULT_DATE_TO, df_sub_from_dates, load_btc_data
from backtest import BacktestConfig, Backtester
from report import build_calibration_report, build_trade_report
from scenarios import Scenario, extract_regime_scenarios


def _resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if "Timestamp" not in df.columns:
        raise ValueError("Timestamp column required for resampling.")
    base = df.copy()
    base["Timestamp"] = pd.to_datetime(base["Timestamp"], errors="coerce")
    base = base.dropna(subset=["Timestamp"]).sort_values("Timestamp").set_index("Timestamp")
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in base.columns:
        agg["Volume"] = "sum"
    resampled = base.resample(rule).agg(agg).dropna(subset=["Close"]).reset_index()
    return resampled


def _load_data(csv_path: str | None, resample_rule: str | None, cache_path: Path | None) -> pd.DataFrame:
    if resample_rule and resample_rule.lower() not in {"none", "no", "false"}:
        if cache_path and cache_path.exists():
            df = load_btc_data(csv_path=str(cache_path))
            return df
        df_raw = load_btc_data(csv_path=csv_path)
        df_res = _resample_ohlc(df_raw, resample_rule)
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            df_res.to_csv(cache_path, index=False)
        return df_res
    return load_btc_data(csv_path=csv_path)


def _score_stats(stats: Dict[str, float]) -> float:
    sharpe = stats.get("sharpe", 0.0) or 0.0
    total_return = stats.get("total_return", 0.0) or 0.0
    max_dd = abs(stats.get("max_drawdown", 0.0) or 0.0)
    win_rate = stats.get("win_rate", 0.0) or 0.0
    return sharpe + 0.4 * total_return - 1.0 * max_dd + 0.2 * (win_rate - 0.5)


def _candidate_grid() -> Tuple[Dict[str, List[Any]], Dict[str, List[Any]]]:
    strategy_grid = {
        "ma_window": [20, 30, 40, 60],
        "z_entry": [1.8, 2.0, 2.4, 2.8, 3.2],
        "z_exit": [0.2, 0.5, 0.7, 1.0],
        "trend_threshold": [0.005, 0.007, 0.01, 0.015],
        "trend_follow": [True, False],
        "rsi_oversold": [20, 25, 30],
        "rsi_overbought": [65, 70, 75, 80],
        "trend_rsi_long": [55, 60, 65],
        "trend_rsi_short": [40, 45, 50],
        "min_atr_pct": [0.0005, 0.001, 0.002],
        "max_atr_pct": [0.03, 0.04, 0.05],
        "max_hold_bars": [48, 96, 144, 192],
        "require_reversal": [True, False],
    }
    config_grid = {
        "risk_per_trade": [0.005, 0.01, 0.02, 0.04],
        "max_leverage": [1.0, 2.0, 3.0, 5.0],
        "atr_stop_mult": [2.0, 2.5, 3.0, 3.5],
        "atr_take_mult": [1.5, 2.0, 3.0, 4.0],
    }
    return strategy_grid, config_grid


def _sample_candidates(n: int, seed: int) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    rng = np.random.default_rng(seed)
    strategy_grid, config_grid = _candidate_grid()
    candidates: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    attempts = 0
    while len(candidates) < n and attempts < n * 25:
        attempts += 1
        strat = {k: rng.choice(v) for k, v in strategy_grid.items()}
        cfg = {k: rng.choice(v) for k, v in config_grid.items()}
        strat = {k: (v.item() if isinstance(v, np.generic) else v) for k, v in strat.items()}
        cfg = {k: (v.item() if isinstance(v, np.generic) else v) for k, v in cfg.items()}
        if strat["rsi_overbought"] <= strat["rsi_oversold"]:
            continue
        if strat["trend_rsi_long"] <= strat["trend_rsi_short"]:
            continue
        if strat["min_atr_pct"] >= strat["max_atr_pct"]:
            continue
        candidates.append((strat, cfg))
    if len(candidates) < n:
        raise RuntimeError("Not enough candidate parameter sets generated.")
    return candidates


def _json_default(obj: Any):
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    return str(obj)


def _run_backtest(
    data: pd.DataFrame,
    strategy_params: Dict[str, Any],
    base_config: BacktestConfig,
    config_overrides: Dict[str, Any],
) -> Backtester:
    strat = MeanReversionStrategyV2(data, **strategy_params)
    signals = list(strat.generate_signals()["target_position"])

    cfg = BacktestConfig(**asdict(base_config))
    for key, value in config_overrides.items():
        setattr(cfg, key, value)

    return Backtester(data, signals, cfg)


def _format_stats(stats: Dict[str, float]) -> Dict[str, float]:
    return {
        "total_return": float(stats.get("total_return", 0.0) or 0.0),
        "cagr": float(stats.get("cagr", 0.0) or 0.0),
        "volatility": float(stats.get("volatility", 0.0) or 0.0),
        "sharpe": float(stats.get("sharpe", 0.0) or 0.0),
        "max_drawdown": float(stats.get("max_drawdown", 0.0) or 0.0),
        "win_rate": float(stats.get("win_rate", 0.0) or 0.0),
        "profit_factor": float(stats.get("profit_factor", 0.0) or 0.0),
        "trades": int(stats.get("trades", 0) or 0),
    }


def calibrate_scenario(
    data: pd.DataFrame,
    scenario: Scenario,
    candidates: List[Tuple[Dict[str, Any], Dict[str, Any]]],
    base_config: BacktestConfig,
    train_split: float,
    results_dir: Path,
    stamp: str,
) -> Dict[str, Any]:
    scenario_df = data[(data["Timestamp"] >= scenario.start) & (data["Timestamp"] <= scenario.end)].copy()
    scenario_df = scenario_df.sort_values("Timestamp")
    if scenario_df.empty:
        raise ValueError(f"Scenario {scenario.name} has no data.")

    split_idx = int(len(scenario_df) * train_split)
    split_idx = max(1, min(split_idx, len(scenario_df) - 1))
    train_df = scenario_df.iloc[:split_idx].copy()
    test_df = scenario_df.iloc[split_idx:].copy()

    candidate_rows = []
    best = None

    for idx, (strategy_params, config_overrides) in enumerate(candidates, start=1):
        bt = _run_backtest(train_df, strategy_params, base_config, config_overrides)
        result = bt.run()
        stats = _format_stats(result.stats)
        score = _score_stats(stats)
        candidate_rows.append(
            {
                "rank": idx,
                "score": score,
                "strategy_params": strategy_params,
                "config": config_overrides,
                "train_stats": stats,
            }
        )
        if best is None or score > best["score"]:
            best = candidate_rows[-1]

    if best is None:
        raise RuntimeError(f"No candidates evaluated for scenario {scenario.name}.")

    test_bt = _run_backtest(test_df, best["strategy_params"], base_config, best["config"])
    test_result = test_bt.run()
    test_stats = _format_stats(test_result.stats)

    full_bt = _run_backtest(scenario_df, best["strategy_params"], base_config, best["config"])
    full_result = full_bt.run()

    trade_report = results_dir / f"scenario_{scenario.name}_{stamp}.html"
    build_trade_report(scenario_df, full_result.trades, trade_report, title=f"Scenario {scenario.name} Trade Report")

    summary = {
        "scenario": {
            "name": scenario.name,
            "label": scenario.label,
            "start": scenario.start.isoformat(),
            "end": scenario.end.isoformat(),
            "bars": scenario.bars,
        },
        "best": {
            "score": best["score"],
            "strategy_params": best["strategy_params"],
            "config": best["config"],
            "train_stats": best["train_stats"],
            "test_stats": test_stats,
        },
        "artifacts": {
            "trade_report": str(trade_report),
        },
        "top_candidates": sorted(candidate_rows, key=lambda r: r["score"], reverse=True)[:10],
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Scenario-aware calibration")
    parser.add_argument("--csv", dest="csv_path", default=None, help="Path to CSV with Timestamp/Close")
    parser.add_argument("--date-from", default=DEFAULT_DATE_FROM, help="Format: JJ-MM-AAAA HH:MM:SS")
    parser.add_argument("--date-to", default=DEFAULT_DATE_TO, help="Format: JJ-MM-AAAA HH:MM:SS")
    parser.add_argument("--results-dir", default="outputs", help="Output directory")
    parser.add_argument("--resample", default="15min", help="Resample rule (e.g. 15min, 30min, none)")
    parser.add_argument("--samples", type=int, default=20, help="Number of parameter candidates to test")
    parser.add_argument("--train-split", type=float, default=0.7, help="Train split ratio within each scenario")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenario-min-days", type=int, default=30)
    parser.add_argument("--scenario-top-n", type=int, default=1)
    parser.add_argument("--scenario-vol-window-days", type=int, default=7)
    parser.add_argument("--scenario-trend-fast", type=int, default=48)
    parser.add_argument("--scenario-trend-slow", type=int, default=192)
    parser.add_argument("--no-short", action="store_true", help="Disable shorts")
    args = parser.parse_args()

    results_root = Path(args.results_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = results_root / f"calibration_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cache_path = out_dir / "resampled.csv" if args.resample and args.resample.lower() not in {"none", "no"} else None
    df = _load_data(args.csv_path, args.resample, cache_path)

    sub_data = df_sub_from_dates(df, args.date_from, args.date_to)
    sub_data = sub_data.sort_values("Timestamp")

    scenarios = extract_regime_scenarios(
        sub_data,
        vol_window_days=args.scenario_vol_window_days,
        trend_fast_span=args.scenario_trend_fast,
        trend_slow_span=args.scenario_trend_slow,
        min_days=args.scenario_min_days,
        top_n=args.scenario_top_n,
    )
    if len(scenarios) < 3 and args.scenario_min_days > 7:
        scenarios = extract_regime_scenarios(
            sub_data,
            vol_window_days=args.scenario_vol_window_days,
            trend_fast_span=args.scenario_trend_fast,
            trend_slow_span=args.scenario_trend_slow,
            min_days=7,
            top_n=args.scenario_top_n,
        )
    if not scenarios:
        scenarios = [
            Scenario(
                name="full_period",
                label="full_period",
                start=sub_data["Timestamp"].min(),
                end=sub_data["Timestamp"].max(),
                bars=len(sub_data),
            )
        ]

    candidates = _sample_candidates(args.samples, args.seed)

    base_config = BacktestConfig(
        initial_cash=10_000.0,
        risk_per_trade=0.01,
        max_leverage=1.0,
        fee_bps=2.0,
        slippage_bps=1.0,
        allow_short=not args.no_short,
        signal_mode="target",
        use_atr_sl_tp=True,
    )

    scenario_results = []
    for scenario in scenarios:
        summary = calibrate_scenario(
            sub_data,
            scenario,
            candidates,
            base_config,
            train_split=args.train_split,
            results_dir=out_dir,
            stamp=stamp,
        )
        scenario_results.append(summary)

    calibration_path = out_dir / f"calibration_{stamp}.json"
    calibration_payload = {
        "run_at": datetime.now().isoformat(),
        "data": {
            "csv_path": args.csv_path,
            "date_from": args.date_from,
            "date_to": args.date_to,
            "rows": int(len(sub_data)),
            "resample": args.resample,
        },
        "scenarios": scenario_results,
    }
    calibration_path.write_text(
        json.dumps(calibration_payload, indent=2, ensure_ascii=True, default=_json_default),
        encoding="utf-8",
    )

    report_path = out_dir / f"calibration_report_{stamp}.html"
    build_calibration_report(
        scenario_results,
        report_path,
        title="Scenario Calibration Report",
        subtitle=f"Dataset: {args.csv_path or 'synthetic'} | Range: {args.date_from} to {args.date_to}",
    )

    print(f"Calibration complete. Outputs in {out_dir}")


if __name__ == "__main__":
    main()
