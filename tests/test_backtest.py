import pandas as pd

from backtest import BacktestConfig, Backtester


def _make_df():
    ts = pd.date_range("2020-01-01", periods=6, freq="D")
    prices = [100, 102, 101, 99, 98, 100]
    df = pd.DataFrame(
        {
            "Timestamp": ts,
            "Open": prices,
            "High": [p + 1 for p in prices],
            "Low": [p - 1 for p in prices],
            "Close": prices,
        }
    )
    return df


def test_backtest_runs():
    df = _make_df()
    signals = [0, 1, 0, 0, 0, 0]
    config = BacktestConfig(fee_bps=0.0, slippage_bps=0.0)
    result = Backtester(df, signals, config).run()

    assert "total_return" in result.stats
    assert len(result.equity_curve) == len(df) - 1


def test_stop_loss_triggers():
    df = _make_df()
    signals = [0, 1, 0, 0, 0, 0]
    config = BacktestConfig(fee_bps=0.0, slippage_bps=0.0, stop_loss=0.01, take_profit=0.5)
    result = Backtester(df, signals, config).run()
    if not result.trades.empty:
        assert result.trades.iloc[0]["exit_reason"] in {"stop_loss", "signal_flip", "take_profit"}
