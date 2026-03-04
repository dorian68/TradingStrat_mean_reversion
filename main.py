import argparse

from Cls_Strategy import Strategy
from Cls_TradingBot import convert, SIGNAL_MAP
from Mod_BTC import DEFAULT_DATE_FROM, DEFAULT_DATE_TO, df_sub_from_dates, load_btc_data
from backtest import BacktestConfig, Backtester


def main():
    parser = argparse.ArgumentParser(description="Mean reversion demo")
    parser.add_argument("--csv", dest="csv_path", default=None, help="Chemin vers un CSV avec Timestamp/Close")
    parser.add_argument("--date-from", default=DEFAULT_DATE_FROM, help="Format: JJ-MM-AAAA HH:MM:SS")
    parser.add_argument("--date-to", default=DEFAULT_DATE_TO, help="Format: JJ-MM-AAAA HH:MM:SS")
    parser.add_argument("--no-plot", action="store_true", help="Désactive le plot")
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

    mean_rev = Strategy(sub_data)
    if not args.no_plot:
        mean_rev.plot_signal(smooth=True)
    signals = mean_rev.generate_signals()

    # Chargement des signaux
    signals = convert(SIGNAL_MAP, list(signals["smooth_signal"]))

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
    )
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


if __name__ == "__main__":
    main()
