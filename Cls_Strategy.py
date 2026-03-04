import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def lisse_signal(signals):
    """
    Lisse une séquence de signaux en supprimant les répétitions successives.
    - Conserve 0 (hold)
    - Ne renvoie un signal non nul que lors d'un changement
    """
    smoothed = []
    prev = 0
    for s in signals:
        if s == 0:
            smoothed.append(0)
            prev = 0
        elif s == prev:
            smoothed.append(0)
        else:
            smoothed.append(s)
            prev = s
    return smoothed


class Strategy:
    def __init__(self,data,ma_window=14,threshold=0.002,arrow_head_width=0.009,arrow_head_length=0.04,arrow_width=0.004):
        self.data = data
        self.ma_window = ma_window
        self.threshold = threshold
        self.arrow_head_width = arrow_head_width
        self.arrow_head_length = arrow_head_length
        self.arrow_width = arrow_width

    def generate_signals(self):
        """
        Génère des signaux d'achat et de vente basés sur une stratégie de mean reversion.
        
        :param prices: DataFrame contenant les colonnes 'Date' et 'Close'
        :param window: Période de la moyenne mobile
        :param threshold: Seuil de déviation en pourcentage
        :return: DataFrame avec les signaux
        """
        prices = self.data.copy()
        prices["SMA"] = prices.Close.rolling(window=self.ma_window).mean()
        prices["Deviation"] = (prices.Close - prices.SMA) / prices.SMA
        
        # Signaux d'achat et de vente
        prices["Signal"] = 0
        mask = prices["Deviation"] < -self.threshold
        not_mask = prices["Deviation"] > self.threshold
        prices.loc[mask, "Signal"] = 1  # Acheter
        prices.loc[not_mask, "Signal"] = -1  # Vendre (short)
        prices["smooth_signal"] = lisse_signal(list(prices["Signal"]))
        return prices

    def plot_signal(self,smooth=True,no_curb=False):
        plt.figure(figsize=(17,6))
        x = self.data["Timestamp"] if "Timestamp" in self.data.columns else self.data.index
        plt.plot(x, self.data["Close"])
        plt.plot(x, self.data["Close"].rolling(window=self.ma_window).mean(), "g")

        df_meanR_signal = self.generate_signals()
        """
        if no_curb:
            plt.figure(figsize=(17,6))
            plt.plot(df_meanR_signal["Timestamp"],df_meanR_signal["smooth_signal"])
        elif no_curb:
        """    
        signal_col = "smooth_signal" if smooth else "Signal"
        for idx, row in df_meanR_signal.iterrows():
            x_value = row["Timestamp"] if "Timestamp" in row else idx
            if row[signal_col] > 0:
                plt.arrow(
                    x_value,
                    row["Close"],
                    0,
                    10,
                    head_length=self.arrow_head_length,
                    head_width=self.arrow_head_width,
                    width=self.arrow_width,
                    ec="green",
                )
            if row[signal_col] < 0:
                plt.arrow(
                    x_value,
                    row["Close"],
                    0,
                    10,
                    head_length=self.arrow_head_length,
                    head_width=self.arrow_head_width,
                    width=self.arrow_width,
                    ec="red",
                )

    def params(self):
        return {
            "ma_window": self.ma_window,
            "threshold": self.threshold,
        }


class MeanReversionStrategyV2:
    def __init__(
        self,
        data,
        ma_window=30,
        z_entry=2.0,
        z_exit=0.7,
        ema_fast=10,
        ema_slow=50,
        trend_threshold=0.01,
        trend_follow=True,
        rsi_window=14,
        rsi_overbought=65,
        rsi_oversold=25,
        trend_rsi_long=60,
        trend_rsi_short=45,
        require_reversal=False,
        atr_window=14,
        min_atr_pct=0.001,
        max_atr_pct=0.04,
        cooldown=4,
        max_hold_bars=144,
    ):
        self.data = data
        self.ma_window = ma_window
        self.z_entry = z_entry
        self.z_exit = z_exit
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.trend_threshold = trend_threshold
        self.trend_follow = trend_follow
        self.rsi_window = rsi_window
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.trend_rsi_long = trend_rsi_long
        self.trend_rsi_short = trend_rsi_short
        self.require_reversal = require_reversal
        self.atr_window = atr_window
        self.min_atr_pct = min_atr_pct
        self.max_atr_pct = max_atr_pct
        self.cooldown = cooldown
        self.max_hold_bars = max_hold_bars

    def generate_signals(self):
        df = self.data.copy()
        close = df["Close"].astype(float)

        if "High" not in df.columns:
            df["High"] = close
        if "Low" not in df.columns:
            df["Low"] = close
        if "Open" not in df.columns:
            df["Open"] = close

        ma = close.rolling(self.ma_window).mean()
        std = close.rolling(self.ma_window).std()
        zscore = (close - ma) / std

        ema_fast = close.ewm(span=self.ema_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.ema_slow, adjust=False).mean()
        trend_strength = (ema_fast - ema_slow).abs() / close

        prev_close = close.shift(1)
        tr = pd.concat(
            [
                (df["High"] - df["Low"]).abs(),
                (df["High"] - prev_close).abs(),
                (df["Low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(self.atr_window).mean()
        atr_pct = atr / close

        delta = close.diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)
        avg_gain = gain.rolling(self.rsi_window).mean()
        avg_loss = loss.rolling(self.rsi_window).mean()
        rs = avg_gain / avg_loss.replace(0.0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        allow_mean = trend_strength <= self.trend_threshold
        if self.min_atr_pct is not None:
            allow_mean &= atr_pct >= self.min_atr_pct
        if self.max_atr_pct is not None:
            allow_mean &= atr_pct <= self.max_atr_pct

        allow_trend = atr_pct.notna()
        if self.min_atr_pct is not None:
            allow_trend &= atr_pct >= self.min_atr_pct
        if self.max_atr_pct is not None:
            allow_trend &= atr_pct <= self.max_atr_pct * 1.5

        open_price = df["Open"].astype(float)
        bullish = close > open_price
        bearish = close < open_price
        prev_bullish = bullish.shift(1)
        prev_bearish = bearish.shift(1)

        positions = []
        pos = 0
        cooldown_left = 0
        hold_bars = 0

        for i in range(len(df)):
            if i == 0:
                positions.append(0)
                continue

            if cooldown_left > 0:
                cooldown_left -= 1

            z = zscore.iloc[i]
            allow_mean_i = bool(allow_mean.iloc[i]) if pd.notna(allow_mean.iloc[i]) else False
            allow_trend_i = bool(allow_trend.iloc[i]) if pd.notna(allow_trend.iloc[i]) else False
            trend_i = trend_strength.iloc[i]
            ema_fast_i = ema_fast.iloc[i]
            ema_slow_i = ema_slow.iloc[i]

            if self.trend_follow and pd.notna(trend_i) and trend_i > self.trend_threshold and allow_trend_i:
                if ema_fast_i > ema_slow_i and (pd.isna(rsi.iloc[i]) or rsi.iloc[i] >= self.trend_rsi_long):
                    pos = 1
                elif ema_fast_i < ema_slow_i and (pd.isna(rsi.iloc[i]) or rsi.iloc[i] <= self.trend_rsi_short):
                    pos = -1
                else:
                    pos = 0
                cooldown_left = 0
                hold_bars = 0
                positions.append(pos)
                continue

            if pos == 0:
                if cooldown_left == 0 and allow_mean_i and pd.notna(z):
                    long_reversal_ok = True
                    short_reversal_ok = True
                    if self.require_reversal:
                        long_reversal_ok = bool(bullish.iloc[i] and prev_bearish.iloc[i])
                        short_reversal_ok = bool(bearish.iloc[i] and prev_bullish.iloc[i])

                    if z <= -self.z_entry and (pd.isna(rsi.iloc[i]) or rsi.iloc[i] <= self.rsi_oversold) and long_reversal_ok:
                        pos = 1
                    elif z >= self.z_entry and (pd.isna(rsi.iloc[i]) or rsi.iloc[i] >= self.rsi_overbought) and short_reversal_ok:
                        pos = -1
                positions.append(pos)
            elif pos == 1:
                hold_bars += 1
                if (not allow_mean_i) or (pd.notna(z) and z >= -self.z_exit) or (hold_bars >= self.max_hold_bars):
                    pos = 0
                    cooldown_left = self.cooldown
                    hold_bars = 0
                positions.append(pos)
            else:
                hold_bars += 1
                if (not allow_mean_i) or (pd.notna(z) and z <= self.z_exit) or (hold_bars >= self.max_hold_bars):
                    pos = 0
                    cooldown_left = self.cooldown
                    hold_bars = 0
                positions.append(pos)

        df["zscore"] = zscore
        df["atr"] = atr
        df["atr_pct"] = atr_pct
        df["trend_strength"] = trend_strength
        df["rsi"] = rsi
        df["target_position"] = positions
        return df

    def plot_signal(self):
        df = self.generate_signals()
        x = df["Timestamp"] if "Timestamp" in df.columns else df.index
        plt.figure(figsize=(17, 6))
        plt.plot(x, df["Close"])
        for idx, row in df.iterrows():
            x_value = row["Timestamp"] if "Timestamp" in row else idx
            if row["target_position"] > 0:
                plt.arrow(x_value, row["Close"], 0, 10, head_length=0.04, head_width=0.009, width=0.004, ec="green")
            elif row["target_position"] < 0:
                plt.arrow(x_value, row["Close"], 0, 10, head_length=0.04, head_width=0.009, width=0.004, ec="red")

    def params(self):
        return {
            "ma_window": self.ma_window,
            "z_entry": self.z_entry,
            "z_exit": self.z_exit,
            "ema_fast": self.ema_fast,
            "ema_slow": self.ema_slow,
            "trend_threshold": self.trend_threshold,
            "trend_follow": self.trend_follow,
            "rsi_window": self.rsi_window,
            "rsi_overbought": self.rsi_overbought,
            "rsi_oversold": self.rsi_oversold,
            "trend_rsi_long": self.trend_rsi_long,
            "trend_rsi_short": self.trend_rsi_short,
            "require_reversal": self.require_reversal,
            "atr_window": self.atr_window,
            "min_atr_pct": self.min_atr_pct,
            "max_atr_pct": self.max_atr_pct,
            "cooldown": self.cooldown,
            "max_hold_bars": self.max_hold_bars,
        }
