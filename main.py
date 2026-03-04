import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from Cls_Strategy import MeanReversionStrategyV2, Strategy
from Mod_BTC import DEFAULT_DATE_FROM, DEFAULT_DATE_TO, df_sub_from_dates, load_btc_data
from backtest import BacktestConfig, Backtester
from report import build_trade_report


PROFILE_PRESETS = {
    "balanced_sharpe": {
        "description": "Balanced Sharpe vs drawdown",
        "strategy": {
            "ma_window": 30,
            "z_entry": 2.0,
            "z_exit": 0.7,
            "trend_threshold": 0.01,
            "trend_follow": True,
            "rsi_oversold": 25,
            "rsi_overbought": 65,
            "trend_rsi_long": 60,
            "trend_rsi_short": 45,
            "min_atr_pct": 0.001,
            "max_atr_pct": 0.04,
            "max_hold_bars": 144,
            "require_reversal": False,
        },
        "config": {
            "risk_per_trade": 0.02,
            "max_leverage": 1.0,
            "atr_stop_mult": 2.5,
            "atr_take_mult": 4.0,
        },
    },
    "aggressive_return": {
        "description": "Higher return target, higher drawdown",
        "strategy": {
            "ma_window": 30,
            "z_entry": 2.0,
            "z_exit": 0.7,
            "trend_threshold": 0.01,
            "trend_follow": True,
            "rsi_oversold": 25,
            "rsi_overbought": 65,
            "trend_rsi_long": 60,
            "trend_rsi_short": 45,
            "min_atr_pct": 0.001,
            "max_atr_pct": 0.04,
            "max_hold_bars": 144,
            "require_reversal": False,
        },
        "config": {
            "risk_per_trade": 0.10,
            "max_leverage": 5.0,
            "atr_stop_mult": 2.5,
            "atr_take_mult": 4.0,
        },
    },
    "defensive_drawdown": {
        "description": "Lower drawdown, fewer trades",
        "strategy": {
            "ma_window": 40,
            "z_entry": 2.8,
            "z_exit": 0.4,
            "trend_threshold": 0.007,
            "trend_follow": False,
            "rsi_oversold": 25,
            "rsi_overbought": 75,
            "trend_rsi_long": 55,
            "trend_rsi_short": 45,
            "min_atr_pct": 0.001,
            "max_atr_pct": 0.03,
            "max_hold_bars": 96,
            "require_reversal": True,
        },
        "config": {
            "risk_per_trade": 0.01,
            "max_leverage": 1.0,
            "atr_stop_mult": 3.0,
            "atr_take_mult": 2.0,
        },
    },
    "high_win_rate": {
        "description": "High win rate, lower expectancy",
        "strategy": {
            "ma_window": 60,
            "z_entry": 3.2,
            "z_exit": 0.2,
            "trend_threshold": 0.007,
            "trend_follow": False,
            "rsi_oversold": 20,
            "rsi_overbought": 80,
            "trend_rsi_long": 55,
            "trend_rsi_short": 45,
            "min_atr_pct": 0.001,
            "max_atr_pct": 0.04,
            "max_hold_bars": 48,
            "require_reversal": True,
        },
        "config": {
            "risk_per_trade": 0.01,
            "max_leverage": 1.0,
            "atr_stop_mult": 3.5,
            "atr_take_mult": 1.0,
        },
    },
}


def load_custom_profile(path: str | None):
    if not path:
        return None
    profile_path = Path(path)
    if not profile_path.exists():
        raise FileNotFoundError(f"Custom profile not found: {profile_path}")
    with profile_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def get_profile_overrides(profile_name: str, custom_profile: dict | None):
    if profile_name == "none":
        return None
    if profile_name == "custom":
        if not custom_profile:
            raise ValueError("Custom profile selected but --custom-profile is missing.")
        return custom_profile
    return PROFILE_PRESETS.get(profile_name)


def format_metric(value, pct=False):
    if value is None:
        return ""
    if pct:
        return f"{value * 100:.2f}%"
    return f"{value:.4f}"


def main():
    parser = argparse.ArgumentParser(description="Mean reversion demo")
    parser.add_argument("--csv", dest="csv_path", default=None, help="Chemin vers un CSV avec Timestamp/Close")
    parser.add_argument("--date-from", default=DEFAULT_DATE_FROM, help="Format: JJ-MM-AAAA HH:MM:SS")
    parser.add_argument("--date-to", default=DEFAULT_DATE_TO, help="Format: JJ-MM-AAAA HH:MM:SS")
    parser.add_argument("--no-plot", action="store_true", help="Désactive le plot")
    parser.add_argument("--strategy", choices=["v2", "legacy"], default="v2")
    parser.add_argument("--risk-profile", choices=["conservative", "balanced", "aggressive"], default="balanced")
    parser.add_argument(
        "--profile",
        choices=["none", "custom", *PROFILE_PRESETS.keys()],
        default="none",
        help="Use-case preset (overrides strategy + risk settings)",
    )
    parser.add_argument("--custom-profile", default=None, help="Path to a custom profile JSON")
    parser.add_argument("--compare-profiles", action="store_true", help="Run all profiles and export a comparison table")
    parser.add_argument("--results-dir", default="outputs", help="Dossier de sortie des resultats")
    parser.add_argument("--no-save", action="store_true", help="Desactive l'export automatique des resultats")
    parser.add_argument("--initial-cash", type=float, default=10_000.0)
    parser.add_argument("--risk-per-trade", type=float, default=0.01)
    parser.add_argument("--max-leverage", type=float, default=1.0)
    parser.add_argument("--fee-bps", type=float, default=2.0)
    parser.add_argument("--slippage-bps", type=float, default=1.0)
    parser.add_argument("--stop-loss", type=float, default=0.02)
    parser.add_argument("--take-profit", type=float, default=0.04)
    parser.add_argument("--no-short", action="store_true", help="Désactive les shorts")
    parser.add_argument("--export-trades", default=None, help="Chemin CSV pour exporter les trades")
    parser.add_argument("--export-equity", default=None, help="Chemin CSV pour exporter la courbe d'equity")
    args = parser.parse_args()

    data = load_btc_data(csv_path=args.csv_path, date_from=args.date_from, date_to=args.date_to)

    # Génération des signaux de prise de position
    sub_data = df_sub_from_dates(data, args.date_from, args.date_to)

    profile_name = args.profile
    custom_profile = load_custom_profile(args.custom_profile)
    profile_preset = get_profile_overrides(profile_name, custom_profile)
    strategy_kwargs = profile_preset["strategy"] if profile_preset else {}

    if args.strategy == "legacy":
        mean_rev = Strategy(sub_data)
        if not args.no_plot:
            mean_rev.plot_signal(smooth=True)
        signals_df = mean_rev.generate_signals()
        signals = list(signals_df["smooth_signal"])
        signal_mode = "entries"
        use_atr_sl_tp = False
        strategy_name = "legacy"
    else:
        mean_rev = MeanReversionStrategyV2(sub_data, **strategy_kwargs)
        if not args.no_plot:
            mean_rev.plot_signal()
        signals_df = mean_rev.generate_signals()
        signals = list(signals_df["target_position"])
        signal_mode = "target"
        use_atr_sl_tp = True
        strategy_name = "v2"

    # Backtest institution-grade (exécution next-bar, frais, slippage, SL/TP)
    config = BacktestConfig(
        initial_cash=args.initial_cash,
        risk_per_trade=args.risk_per_trade,
        max_leverage=args.max_leverage,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        stop_loss=args.stop_loss,
        take_profit=args.take_profit,
        allow_short=not args.no_short,
        signal_mode=signal_mode,
        use_atr_sl_tp=use_atr_sl_tp,
    )
    if use_atr_sl_tp:
        if args.risk_profile == "conservative":
            config.risk_per_trade = 0.01
            config.max_leverage = 1.0
            config.atr_stop_mult = 3.0
            config.atr_take_mult = 3.0
        elif args.risk_profile == "aggressive":
            config.risk_per_trade = 0.10
            config.max_leverage = 5.0
            config.atr_stop_mult = 2.5
            config.atr_take_mult = 4.0
        else:
            config.risk_per_trade = 0.02
            config.max_leverage = 1.0
            config.atr_stop_mult = 2.5
            config.atr_take_mult = 4.0

    if profile_preset and use_atr_sl_tp:
        overrides = profile_preset.get("config", {})
        for key, value in overrides.items():
            setattr(config, key, value)
    backtester = Backtester(sub_data, signals, config)
    result = backtester.run()

    stats = result.stats
    print("Backtest summary")
    print(f"- Total return: {stats.get('total_return', 0.0):.2%}")
    print(f"- CAGR: {stats.get('cagr', 0.0):.2%}")
    print(f"- Volatility: {stats.get('volatility', 0.0):.2%}")
    print(f"- Sharpe: {stats.get('sharpe', 0.0):.2f}")
    print(f"- Max drawdown: {stats.get('max_drawdown', 0.0):.2%}")
    print(f"- Trades: {stats.get('trades', 0)}")
    print(f"- Win rate: {stats.get('win_rate', 0.0):.2%}")
    print(f"- Profit factor: {stats.get('profit_factor', 0.0):.2f}")

    if args.export_trades:
        result.trades.to_csv(args.export_trades, index=False)
    if args.export_equity:
        result.equity_curve.to_csv(args.export_equity, index=False)

    if not args.no_save:
        out_dir = Path(args.results_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        trades_path = out_dir / f"trades_{stamp}.csv"
        equity_path = out_dir / f"equity_{stamp}.csv"
        summary_path = out_dir / f"summary_{stamp}.json"

        result.trades.to_csv(trades_path, index=False)
        result.equity_curve.to_csv(equity_path, index=False)

        summary = {
            "run_at": datetime.now().isoformat(),
            "strategy": {
                "name": strategy_name,
                "params": mean_rev.params(),
                "signal_mode": signal_mode,
                "profile": profile_name,
            },
            "data": {
                "csv_path": args.csv_path,
                "date_from": args.date_from,
                "date_to": args.date_to,
                "rows": int(len(sub_data)),
            },
            "config": asdict(config),
            "stats": result.stats,
            "artifacts": {
                "trades": str(trades_path),
                "equity": str(equity_path),
            },
        }
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=True)

        report_path = out_dir / f"report_{stamp}.html"
        build_trade_report(sub_data, result.trades, report_path, title="Backtest Trade Report")
        summary["artifacts"]["report"] = str(report_path)
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=True)

        print(f"Saved results to {out_dir}")

    if args.compare_profiles:
        out_dir = Path(args.results_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        compare_rows = []

        compare_profiles = list(PROFILE_PRESETS.items())
        if custom_profile:
            compare_profiles.append(("custom", custom_profile))

        for name, preset in compare_profiles:
            strat = MeanReversionStrategyV2(sub_data, **preset.get("strategy", {}))
            signals_cmp = list(strat.generate_signals()["target_position"])

            cfg = BacktestConfig(
                initial_cash=args.initial_cash,
                risk_per_trade=args.risk_per_trade,
                max_leverage=args.max_leverage,
                fee_bps=args.fee_bps,
                slippage_bps=args.slippage_bps,
                stop_loss=args.stop_loss,
                take_profit=args.take_profit,
                allow_short=not args.no_short,
                signal_mode="target",
                use_atr_sl_tp=True,
            )
            overrides = preset.get("config", {})
            for key, value in overrides.items():
                setattr(cfg, key, value)

            result_cmp = Backtester(sub_data, signals_cmp, cfg).run()
            stats = result_cmp.stats
            compare_rows.append(
                {
                    "profile": name,
                    "description": preset.get("description", ""),
                    "total_return": stats.get("total_return", 0.0),
                    "cagr": stats.get("cagr", 0.0),
                    "sharpe": stats.get("sharpe", 0.0),
                    "max_drawdown": stats.get("max_drawdown", 0.0),
                    "win_rate": stats.get("win_rate", 0.0),
                    "profit_factor": stats.get("profit_factor", 0.0),
                    "trades": stats.get("trades", 0),
                }
            )

        compare_csv = out_dir / f"compare_profiles_{stamp}.csv"
        compare_md = out_dir / f"compare_profiles_{stamp}.md"
        compare_html = out_dir / f"compare_profiles_{stamp}.html"

        with compare_csv.open("w", encoding="utf-8") as f:
            f.write("profile,description,total_return,cagr,sharpe,max_drawdown,win_rate,profit_factor,trades\n")
            for row in compare_rows:
                f.write(
                    f"{row['profile']},"
                    f"\"{row['description']}\","
                    f"{row['total_return']:.6f},"
                    f"{row['cagr']:.6f},"
                    f"{row['sharpe']:.6f},"
                    f"{row['max_drawdown']:.6f},"
                    f"{row['win_rate']:.6f},"
                    f"{row['profit_factor']:.6f},"
                    f"{row['trades']}\n"
                )

        lines = [
            "| Profile | Description | Total Return | CAGR | Sharpe | Max DD | Win Rate | Profit Factor | Trades |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for row in compare_rows:
            lines.append(
                f"| {row['profile']} | {row['description']} | "
                f"{format_metric(row['total_return'], pct=True)} | "
                f"{format_metric(row['cagr'], pct=True)} | "
                f"{row['sharpe']:.2f} | "
                f"{format_metric(row['max_drawdown'], pct=True)} | "
                f"{format_metric(row['win_rate'], pct=True)} | "
                f"{row['profit_factor']:.2f} | "
                f"{row['trades']} |"
            )
        compare_md.write_text("\n".join(lines), encoding="utf-8")

        html_rows = []
        for row in compare_rows:
            html_rows.append(
                "<tr>"
                f"<td>{row['profile']}</td>"
                f"<td>{row['description']}</td>"
                f"<td>{format_metric(row['total_return'], pct=True)}</td>"
                f"<td>{format_metric(row['cagr'], pct=True)}</td>"
                f"<td>{row['sharpe']:.2f}</td>"
                f"<td>{format_metric(row['max_drawdown'], pct=True)}</td>"
                f"<td>{format_metric(row['win_rate'], pct=True)}</td>"
                f"<td>{row['profit_factor']:.2f}</td>"
                f"<td>{row['trades']}</td>"
                "</tr>"
            )

        html_content = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Profile Comparison</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #0f1115; color: #e6e6e6; padding: 16px; }}
    h1 {{ font-size: 20px; margin: 0 0 10px 0; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #2a313c; }}
    th {{ text-align: left; color: #b3b3b3; }}
    tr:hover {{ background: #1a1e24; }}
    .meta {{ font-size: 12px; color: #b3b3b3; }}
  </style>
</head>
<body>
  <h1>Profile Comparison</h1>
  <div class="meta">Dataset: {args.csv_path or "synthetic"} | Range: {args.date_from} to {args.date_to}</div>
  <table>
    <thead>
      <tr>
        <th>Profile</th>
        <th>Description</th>
        <th>Total Return</th>
        <th>CAGR</th>
        <th>Sharpe</th>
        <th>Max DD</th>
        <th>Win Rate</th>
        <th>Profit Factor</th>
        <th>Trades</th>
      </tr>
    </thead>
    <tbody>
      {''.join(html_rows)}
    </tbody>
  </table>
</body>
</html>
"""
        compare_html.write_text(html_content, encoding="utf-8")

        print(f"Saved profile comparison to {compare_csv}, {compare_md}, and {compare_html}")


if __name__ == "__main__":
    main()
