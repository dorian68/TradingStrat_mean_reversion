import Cls_Strategy
import Cls_TradingBot
import Mod_BTC
import Mod_retrieveData
import Mod_HPC_environment

# Génération des signaux de prise de position
sub_data = df_sub_from_dates(data,date_from,date_to)

mean_rev = Strategy(sub_data)
mean_rev.plot_signal(smooth=True)
signals = mean_rev.generate_signals()

# Chargement des signaux
prices = list(signals["Close"])
signals = convert(dict,list(signals["smooth_signal"]))

# Chargement des paramètres et lancement de la stratégie
bot = TradingBot(1000)
bot.run_strategy(prices, signals)

# Affichage du P\L de la stratégie
print(f"La stratégie mean reversion avec les pamamètres ----- a un PnL de {bot.Pnl()}")