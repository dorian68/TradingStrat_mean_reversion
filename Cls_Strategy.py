import matplotlib.pyplot as plt


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
                    
