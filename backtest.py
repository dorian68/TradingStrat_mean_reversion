from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from metrics import (
    compute_drawdown,
    compute_returns,
    infer_periods_per_year,
    summarize_trades,
)


@dataclass
class BacktestConfig:
    initial_cash: float = 10_000.0
    risk_per_trade: float = 0.01
    max_leverage: float = 1.0
    fee_bps: float = 2.0
    slippage_bps: float = 1.0
    allow_long: bool = True
    allow_short: bool = True
    stop_loss: float = 0.02
    take_profit: float = 0.04
    signal_mode: str = "entries"  # "entries" or "target"
    use_atr_sl_tp: bool = False
    atr_window: int = 14
    atr_stop_mult: float = 2.0
    atr_take_mult: float = 3.0
    close_on_end: bool = True
    price_col: str = "Close"
    open_col: str = "Open"
    high_col: str = "High"
    low_col: str = "Low"
    timestamp_col: str = "Timestamp"


@dataclass
class Trade:
    entry_time: Optional[pd.Timestamp]
    exit_time: Optional[pd.Timestamp]
    side: str
    entry_price: float
    exit_price: float
    stop_loss_pct: float
    take_profit_pct: float
    stop_price: float
    take_price: float
    units: float
    notional: float
    pnl: float
    return_pct: float
    duration_bars: int
    exit_reason: str
    entry_fee: float
    exit_fee: float


@dataclass
class BacktestResult:
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    stats: Dict[str, float]
    config: BacktestConfig


class Backtester:
    def __init__(self, data: pd.DataFrame, signals: List[int], config: BacktestConfig):
        self.data = data.copy()
        self.signals = np.asarray(self._coerce_signals(signals), dtype=float)
        self.config = config

    def _coerce_signals(self, signals):
        if len(signals) == 0:
            return signals
        sample = signals[0]
        if isinstance(sample, str):
            mapping = {"buy": 1, "sell": -1, "hold": 0}
            return [mapping.get(str(s).lower(), 0) for s in signals]
        return signals

    def run(self) -> BacktestResult:
        df = self._prepare_data(self.data)
        if len(self.signals) != len(df):
            raise ValueError("La taille des signaux doit correspondre au nombre de lignes des données.")
        if len(df) < 2:
            raise ValueError("Pas assez de données pour exécuter un backtest.")

        cash = float(self.config.initial_cash)
        position = None
        equity_curve: List[Dict[str, float]] = []
        trades: List[Trade] = []

        for i in range(1, len(df)):
            row = df.iloc[i]
            timestamp = row["Timestamp"] if "Timestamp" in df.columns else None
            open_price = float(row["Open"])
            high_price = float(row["High"])
            low_price = float(row["Low"])
            close_price = float(row["Close"])

            signal = int(self.signals[i - 1])

            if self.config.signal_mode == "target":
                target = signal
                if position is not None:
                    if target == 0:
                        exit_price = self._apply_slippage(open_price, side=position["side"], is_entry=False)
                        cash, trade = self._close_position(position, cash, exit_price, timestamp, "target_flat", i)
                        trades.append(trade)
                        position = None
                    elif target == 1 and position["side"] == "short":
                        exit_price = self._apply_slippage(open_price, side=position["side"], is_entry=False)
                        cash, trade = self._close_position(position, cash, exit_price, timestamp, "target_flip", i)
                        trades.append(trade)
                        position = None
                    elif target == -1 and position["side"] == "long":
                        exit_price = self._apply_slippage(open_price, side=position["side"], is_entry=False)
                        cash, trade = self._close_position(position, cash, exit_price, timestamp, "target_flip", i)
                        trades.append(trade)
                        position = None

                if position is None and target != 0:
                    side = "long" if target > 0 else "short"
                    if (side == "long" and self.config.allow_long) or (side == "short" and self.config.allow_short):
                        entry_price = self._apply_slippage(open_price, side=side, is_entry=True)
                        atr_value = float(row["ATR"]) if "ATR" in row and pd.notna(row["ATR"]) else None
                        position, cash = self._open_position(
                            side=side,
                            entry_price=entry_price,
                            cash=cash,
                            timestamp=timestamp,
                            bar_index=i,
                            atr_value=atr_value,
                        )
            else:
                if position is not None:
                    if self._signal_is_exit(position["side"], signal):
                        exit_price = self._apply_slippage(open_price, side=position["side"], is_entry=False)
                        cash, trade = self._close_position(position, cash, exit_price, timestamp, "signal_flip", i)
                        trades.append(trade)
                        position = None

                if position is None:
                    if self._signal_is_entry(signal):
                        side = "long" if signal > 0 else "short"
                        if (side == "long" and self.config.allow_long) or (side == "short" and self.config.allow_short):
                            entry_price = self._apply_slippage(open_price, side=side, is_entry=True)
                            atr_value = float(row["ATR"]) if "ATR" in row and pd.notna(row["ATR"]) else None
                            position, cash = self._open_position(
                                side=side,
                                entry_price=entry_price,
                                cash=cash,
                                timestamp=timestamp,
                                bar_index=i,
                                atr_value=atr_value,
                            )

            if position is not None:
                stop_hit, take_hit, exit_price, reason = self._check_stop_take(position, high_price, low_price)
                if stop_hit or take_hit:
                    exit_price = self._apply_slippage(exit_price, side=position["side"], is_entry=False)
                    cash, trade = self._close_position(position, cash, exit_price, timestamp, reason, i)
                    trades.append(trade)
                    position = None

            unrealized = 0.0
            if position is not None:
                unrealized = self._unrealized_pnl(position, close_price)

            equity = cash + unrealized
            equity_curve.append(
                {
                    "Timestamp": timestamp,
                    "Equity": equity,
                    "Cash": cash,
                    "Unrealized": unrealized,
                    "Position": 0 if position is None else (1 if position["side"] == "long" else -1),
                }
            )

        if position is not None and self.config.close_on_end:
            last_row = df.iloc[-1]
            timestamp = last_row["Timestamp"] if "Timestamp" in df.columns else None
            exit_price = self._apply_slippage(float(last_row["Close"]), side=position["side"], is_entry=False)
            cash, trade = self._close_position(position, cash, exit_price, timestamp, "eod", len(df) - 1)
            trades.append(trade)
            if equity_curve:
                equity_curve[-1]["Cash"] = cash
                equity_curve[-1]["Unrealized"] = 0.0
                equity_curve[-1]["Equity"] = cash
                equity_curve[-1]["Position"] = 0

        equity_df = pd.DataFrame(equity_curve)
        trades_df = pd.DataFrame([t.__dict__ for t in trades])
        stats = self._compute_stats(equity_df, trades_df)
        return BacktestResult(equity_curve=equity_df, trades=trades_df, stats=stats, config=self.config)

    def _prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if self.config.timestamp_col in df.columns:
            df["Timestamp"] = pd.to_datetime(df[self.config.timestamp_col], errors="coerce")
            df = df.dropna(subset=["Timestamp"])
            df = df.sort_values("Timestamp")
        if self.config.price_col not in df.columns:
            raise ValueError(f"Colonne de prix manquante: {self.config.price_col}")

        close_col = self.config.price_col
        df["Close"] = df[close_col].astype(float)
        df["Open"] = df[self.config.open_col].astype(float) if self.config.open_col in df.columns else df["Close"]
        df["High"] = df[self.config.high_col].astype(float) if self.config.high_col in df.columns else df["Close"]
        df["Low"] = df[self.config.low_col].astype(float) if self.config.low_col in df.columns else df["Close"]
        df = df.dropna(subset=["Open", "High", "Low", "Close"])
        if self.config.use_atr_sl_tp:
            prev_close = df["Close"].shift(1)
            tr = pd.concat(
                [
                    (df["High"] - df["Low"]).abs(),
                    (df["High"] - prev_close).abs(),
                    (df["Low"] - prev_close).abs(),
                ],
                axis=1,
            ).max(axis=1)
            df["ATR"] = tr.rolling(self.config.atr_window).mean()
        return df.reset_index(drop=True)

    def _signal_is_entry(self, signal: int) -> bool:
        return signal != 0

    def _signal_is_exit(self, side: str, signal: int) -> bool:
        if side == "long" and signal < 0:
            return True
        if side == "short" and signal > 0:
            return True
        return False

    def _open_position(
        self,
        side: str,
        entry_price: float,
        cash: float,
        timestamp: Optional[pd.Timestamp],
        bar_index: int,
        atr_value: Optional[float],
    ):
        stop_loss = self.config.stop_loss
        take_profit = self.config.take_profit
        if self.config.use_atr_sl_tp and atr_value is not None and atr_value > 0:
            stop_loss = (atr_value * self.config.atr_stop_mult) / entry_price
            take_profit = (atr_value * self.config.atr_take_mult) / entry_price

        if stop_loss <= 0:
            raise ValueError("stop_loss doit être > 0")

        equity = cash
        risk_budget = equity * self.config.risk_per_trade
        position_notional = risk_budget / stop_loss
        max_notional = equity * self.config.max_leverage
        position_notional = max(0.0, min(position_notional, max_notional))
        if position_notional == 0.0:
            return None, cash

        units = position_notional / entry_price
        fee = position_notional * (self.config.fee_bps / 10_000.0)
        cash -= fee

        if side == "long":
            stop_price = entry_price * (1 - stop_loss)
            take_price = entry_price * (1 + take_profit)
        else:
            stop_price = entry_price * (1 + stop_loss)
            take_price = entry_price * (1 - take_profit)

        position = {
            "side": side,
            "entry_price": entry_price,
            "entry_time": timestamp,
            "units": units,
            "notional": position_notional,
            "entry_bar": bar_index,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "stop_price": stop_price,
            "take_price": take_price,
            "entry_fee": fee,
        }
        return position, cash

    def _close_position(
        self,
        position: Dict[str, float],
        cash: float,
        exit_price: float,
        timestamp: Optional[pd.Timestamp],
        reason: str,
        bar_index: int,
    ):
        pnl = self._realized_pnl(position, exit_price)
        exit_notional = position["units"] * exit_price
        exit_fee = exit_notional * (self.config.fee_bps / 10_000.0)
        cash += pnl - exit_fee

        entry_fee = position.get("entry_fee", 0.0)
        net_pnl = pnl - exit_fee - entry_fee
        return_pct = net_pnl / position["notional"] if position["notional"] else 0.0
        trade = Trade(
            entry_time=position["entry_time"],
            exit_time=timestamp,
            side=position["side"],
            entry_price=position["entry_price"],
            exit_price=exit_price,
            stop_loss_pct=position["stop_loss"],
            take_profit_pct=position["take_profit"],
            stop_price=position["stop_price"],
            take_price=position["take_price"],
            units=position["units"],
            notional=position["notional"],
            pnl=net_pnl,
            return_pct=return_pct,
            duration_bars=bar_index - position.get("entry_bar", bar_index),
            exit_reason=reason,
            entry_fee=entry_fee,
            exit_fee=exit_fee,
        )
        return cash, trade

    def _realized_pnl(self, position: Dict[str, float], exit_price: float) -> float:
        if position["side"] == "long":
            return (exit_price - position["entry_price"]) * position["units"]
        return (position["entry_price"] - exit_price) * position["units"]

    def _unrealized_pnl(self, position: Dict[str, float], price: float) -> float:
        if position["side"] == "long":
            return (price - position["entry_price"]) * position["units"]
        return (position["entry_price"] - price) * position["units"]

    def _apply_slippage(self, price: float, side: str, is_entry: bool) -> float:
        slip = self.config.slippage_bps / 10_000.0
        if side == "long":
            return price * (1 + slip) if is_entry else price * (1 - slip)
        return price * (1 - slip) if is_entry else price * (1 + slip)

    def _check_stop_take(self, position: Dict[str, float], high: float, low: float):
        stop_price = position["stop_price"]
        take_price = position["take_price"]

        if position["side"] == "long":
            stop_hit = low <= stop_price
            take_hit = high >= take_price
            if stop_hit and take_hit:
                return True, True, stop_price, "stop_loss"
            if stop_hit:
                return True, False, stop_price, "stop_loss"
            if take_hit:
                return False, True, take_price, "take_profit"
        else:
            stop_hit = high >= stop_price
            take_hit = low <= take_price
            if stop_hit and take_hit:
                return True, True, stop_price, "stop_loss"
            if stop_hit:
                return True, False, stop_price, "stop_loss"
            if take_hit:
                return False, True, take_price, "take_profit"
        return False, False, 0.0, ""

    def _compute_stats(self, equity_curve: pd.DataFrame, trades: pd.DataFrame) -> Dict[str, float]:
        if equity_curve.empty:
            return {}

        equity = equity_curve["Equity"].astype(float)
        returns = compute_returns(equity)
        dd, max_dd = compute_drawdown(equity)
        periods_per_year = infer_periods_per_year(equity_curve["Timestamp"])
        if returns.std() > 0:
            sharpe = (returns.mean() / returns.std()) * np.sqrt(periods_per_year)
        else:
            sharpe = 0.0

        total_return = (equity.iloc[-1] / equity.iloc[0]) - 1 if equity.iloc[0] else 0.0
        cagr = (1 + total_return) ** (periods_per_year / max(len(equity) - 1, 1)) - 1

        trade_stats = summarize_trades(trades)
        stats = {
            "total_return": float(total_return),
            "cagr": float(cagr),
            "volatility": float(returns.std() * np.sqrt(periods_per_year)),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_dd),
        }
        stats.update(trade_stats)
        return stats
