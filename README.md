# TradingStrat_mean_reversion

A production-minded mean-reversion trading strategy with a realistic backtesting engine (next-bar execution, fees, slippage, SL/TP) plus **scenario-aware calibration** and **interactive HTML reporting**. This repository is built as a clean, professional showcase of quantitative trading engineering.

## What This Project Does

- Generates mean-reversion signals using a moving average deviation rule.
- Runs a realistic backtest with configurable risk, fees, slippage, stop-loss, and take-profit.
- Produces an equity curve, trade log, and key performance statistics.
- Calibrates parameters per **market regime** (trend/volatility scenarios) with train/test splits.
- Generates an interactive HTML report with entries, SL/TP, and prompt-based date filtering.
- Supports parameter sweeps to explore strategy sensitivity.

## Business Value

- **Faster decision-making:** The backtest provides a clear, reproducible view of risk and performance.
- **Risk-aware research:** Built-in stop-loss / take-profit and transaction cost modeling reduce over-optimistic results.
- **Regime-aware calibration:** Contextual scenarios show how the strategy behaves across different market regimes.
- **Research to production mindset:** Clean structure, metrics, and tests make it easy to extend into real systems.
- **Client-ready deliverable:** Clear outputs (trade log, equity curve, stats, HTML report) for reporting and presentations.

## Professional Highlights

- Realistic execution assumptions (next-bar, fees, slippage).
- Risk-based position sizing (risk per trade, leverage caps).
- Comprehensive metrics (Sharpe, drawdown, CAGR, win rate, profit factor).
- Scenario-based calibration with train/test validation.
- Interactive HTML reporting with entry/SL/TP overlays.
- Test coverage and CI workflow for reliability.

## Executive Summary

**Project objective:**  
Build and evaluate a robust mean-reversion strategy with realistic execution and risk controls.

**Key KPIs (sample run on BTC_USD 15m, aggressive return profile):**
- Total return: `47.11%`
- CAGR: `10909.68%`
- Sharpe: `3.53`
- Max drawdown: `-31.02%`
- Win rate: `51.92%`
- Profit factor: `1.27`
- Number of trades: `104`

Sample window: `2026-01-14` to `2026-02-13`. The aggressive return profile targets higher returns at the cost of higher drawdown. Use the balanced profile for tighter risk. Results vary by dataset and regime.

**How to export charts and reports:**
- Export equity curve: `python main.py --export-equity equity.csv --no-plot`
- Export trade log: `python main.py --export-trades trades.csv --no-plot`

You can then plot these in your preferred tool (Excel, Python, Tableau) for client-ready visuals.

## Results (Aggressive Profile)

Sample run on a **30-day BTC_USD 15m window** to demonstrate the reporting format.

**Backtest configuration**

| Parameter | Value |
| --- | --- |
| Asset | `BTC_USD` |
| Timeframe | `15m` |
| Date range | `2026-01-14 11:30 UTC` to `2026-02-13 11:30 UTC` |
| Initial cash | `10,000` |
| Risk per trade | `10%` |
| Max leverage | `5.0x` |
| Fee (bps) | `2` |
| Slippage (bps) | `1` |
| Stop-loss | `ATR x 2.5` |
| Take-profit | `ATR x 4.0` |

Command used (replace with your dataset path):
```bash
python main.py --csv data/BTC_USD_15m.csv --date-from "2026-01-14 11:30:00+00:00" --date-to "2026-02-13 11:30:00+00:00" --no-plot --profile aggressive_return
```

**Performance summary**

| Metric | Value |
| --- | --- |
| Total return | `47.11%` |
| CAGR | `10909.68%` |
| Volatility | `178.13%` |
| Sharpe | `3.53` |
| Max drawdown | `-31.02%` |

Note: CAGR is annualized and can look exaggerated on short windows.

**Trade statistics**

| Metric | Value |
| --- | --- |
| Trades | `104` |
| Win rate | `51.92%` |
| Profit factor | `1.27` |
| Avg trade | `45.30` |
| Expectancy | `45.30` |

## Results (Balanced Profile)

This profile trades the same logic with lower risk and tighter drawdown on the same window.

| Metric | Value |
| --- | --- |
| Total return | `10.08%` |
| CAGR | `222.27%` |
| Volatility | `36.16%` |
| Sharpe | `3.42` |
| Max drawdown | `-7.03%` |
| Trades | `104` |
| Win rate | `51.92%` |
| Profit factor | `1.33` |

## Scenario Calibration Highlights (Contextual)

Calibration runs a train/test split **per market regime** (trend + volatility). Below are **encouraging highlights** from a 15m resample over `2012-01-01` to `2026-03-04`. Full results are in the calibration report.

| Scenario | Train Return | Train Sharpe | Train Max DD | Test Return | Test Sharpe | Test Max DD | Test Win Rate | Test Trades |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `range_highvol_1` | `13.52%` | `16.11` | `-0.55%` | `0.13%` | `0.55` | `-1.87%` | `42.86%` | `7` |
| `range_midvol_1` | `1.78%` | `3.56` | `-1.27%` | `0.30%` | `1.11` | `-1.83%` | `80.00%` | `5` |

Note: Scenario calibration is context-dependent. Some regimes can underperform; the report makes this explicit.

## Quickstart

```bash
pip install -r requirements.txt
python main.py --no-plot
```

## Usage

```bash
python main.py --csv C:\data\btc.csv --date-from "28-11-2019 00:00:00" --date-to "28-11-2019 10:00:00"
```

Useful options:
- `--initial-cash`
- `--risk-per-trade`
- `--max-leverage`
- `--fee-bps`
- `--slippage-bps`
- `--stop-loss` / `--take-profit`
- `--export-trades` (CSV)
- `--export-equity` (CSV)
- `--strategy legacy` (runs the original SMA threshold strategy)
- `--risk-profile` (conservative | balanced | aggressive)
- `--profile` (none | balanced_sharpe | aggressive_return | defensive_drawdown | high_win_rate)
- `--custom-profile` (path to JSON preset for `--profile custom`)
- `--compare-profiles` (export a comparison table across profiles)
- `--results-dir` (output folder for automatic exports)
- `--no-save` (disable automatic exports)

## Calibration (Scenario-Aware)

Run contextual calibration (trend/volatility regimes) with train/test splits and HTML reports:
```bash
python calibration.py --csv data/BTC_USD_1m.csv --date-from "01-01-2012 10:00:00" --date-to "04-03-2026 00:00:00" --samples 20
```

Optional:
- `--resample` (default `15min`)
- `--samples` (number of candidate parameter sets)
- `--scenario-min-days` (minimum regime length)
- `--scenario-top-n` (top segments per regime)

## Data Requirements

The CSV must contain:
- `Timestamp` (timestamp or date)
- `Close`

If `Open`, `High`, `Low` are missing, they are derived from `Close`.
If no CSV is provided, synthetic data is generated for the requested period.

## Stored Outputs

Each run automatically saves:
- `summary_YYYYMMDD_HHMMSS.json` (config + stats)
- `trades_YYYYMMDD_HHMMSS.csv` (includes entry price, SL, TP, fees, exit reason)
- `equity_YYYYMMDD_HHMMSS.csv`
- `report_YYYYMMDD_HHMMSS.html` (interactive chart with entry/SL/TP)

Default output folder: `outputs/` (override with `--results-dir`).

Profile comparison exports:
- `compare_profiles_YYYYMMDD_HHMMSS.csv`
- `compare_profiles_YYYYMMDD_HHMMSS.md`
- `compare_profiles_YYYYMMDD_HHMMSS.html`

Calibration exports:
- `calibration_YYYYMMDD_HHMMSS.json`
- `calibration_report_YYYYMMDD_HHMMSS.html`
- `scenario_<name>_YYYYMMDD_HHMMSS.html` (per scenario trade report)

## How The Strategy Is Implemented

- `Cls_Strategy.py` implements a **hybrid mean-reversion + trend-following** regime.
- Mean reversion uses a z-score of price vs moving average.
- Trend regime uses EMA slope (fast vs slow) to follow momentum when the market is directional.
- Volatility filters, RSI confirmation, and cooldowns reduce over-trading.
- Max holding time caps reduce tail risk in sideways markets.
- `backtest.py` consumes the target-position signal and simulates execution with realistic costs and risk constraints.

## Use-Case Profiles

Profiles are presets for strategy + risk parameters. Use them to match business goals.

- `balanced_sharpe`: prioritizes Sharpe with controlled drawdown.
- `aggressive_return`: targets higher returns, accepts higher drawdown.
- `defensive_drawdown`: minimizes drawdown, fewer trades.
- `high_win_rate`: maximizes win rate, lower expectancy.

Example:
```bash
python main.py --profile balanced_sharpe --no-plot
```

Custom profile example:
```json
{
  "description": "Custom client profile",
  "strategy": {
    "ma_window": 30,
    "z_entry": 2.6,
    "z_exit": 0.4,
    "trend_threshold": 0.01,
    "trend_follow": true,
    "rsi_oversold": 25,
    "rsi_overbought": 70,
    "min_atr_pct": 0.001,
    "max_atr_pct": 0.04,
    "max_hold_bars": 144,
    "require_reversal": false
  },
  "config": {
    "risk_per_trade": 0.03,
    "max_leverage": 2.0,
    "atr_stop_mult": 2.5,
    "atr_take_mult": 4.0
  }
}
```

Run custom profile:
```bash
python main.py --profile custom --custom-profile custom_profile.json --no-plot
```

Profile comparison table:
```bash
python main.py --compare-profiles --no-plot
```

## Repository Structure

- `Cls_Strategy.py` - Mean-reversion signal generation
- `backtest.py` - Backtest engine and execution model
- `metrics.py` - Performance metrics
- `Mod_BTC.py` - Data loader / synthetic data generator
- `Mod_HPC_environment.py` - Parameter sweep simulations (Dask)
- `calibration.py` - Scenario-aware calibration runner
- `scenarios.py` - Regime extraction (trend/volatility scenarios)
- `report.py` - Interactive HTML reports
- `main.py` - CLI entry point
- `tests/` - Unit tests
- `.github/workflows/ci.yml` - CI pipeline

## Skills Demonstrated

- Quantitative strategy design and signal engineering
- Backtesting with realistic execution assumptions
- Risk management and position sizing
- Statistical performance analysis (Sharpe, drawdown, CAGR)
- Regime detection and scenario-based calibration
- Python engineering best practices (tests, CI, clean architecture)
- Data handling and validation

## Disclaimer

This project is for educational and research purposes only. It is not financial advice.
