import dask
import numpy as np
import pandas as pd
from dask import delayed

from Cls_Strategy import Strategy
from Mod_BTC import DEFAULT_DATE_FROM, data, df_sub_from_dates, sub_bitcoin_historic, timer
from backtest import BacktestConfig, Backtester

@timer
def run_simu_threads(seuil_max=0.02,seuil_taille=20,ma_min=10,ma_max=50):

    # Liste de paramètres à tester
    seuils = np.linspace(0,seuil_max,seuil_taille)
    params = [(j,i) for j in range(ma_min,ma_max + 1,1) for i in seuils]
    
    # Utilisation de dask.delayed pour préparer les tâches avec différents paramètres
    tasks = [delayed(sub_bitcoin_historic)(x, y) for x, y in params]
    
    # Exécution des tâches en parallèle et récupération des résultats
    results = dask.compute(*tasks)

    # Affiche les resultats de l'execution dans un dataframe
    donnees = {"Moyennes mobiles": [x for x,y in params],"Seuils": [y for x,y in params], 'Signals achats': [x for x,y in results], 'Signals ventes': [y for x,y in results]}
    return pd.DataFrame(data=donnees)

@timer
def run_simu_no_threads(seuil_max=0.02,seuil_taille=20,ma_min=10,ma_max=50):

    # Liste de paramètres à tester
    seuils = np.linspace(0,seuil_max,seuil_taille)
    params = [(j,i) for j in range(ma_min,ma_max + 1,1) for i in seuils]
    results = []

    for i in params:
        x,y = i
        results.append(sub_bitcoin_historic(x, y))

    # Affiche les resultats de l'execution dans un dataframe
    donnees = {"Moyennes mobiles": [x for x,y in params], "Seuils": [y for x,y in params], "Signals achats": [x for x,y in results], "Signals ventes": [y for x,y in results]}
    return pd.DataFrame(data=donnees)

@timer
def run_simu_backtest_mean_reversion(seuil_min=0.0,seuil_max=0.02,seuil_taille=7,ma_min=10,ma_max=50):

    # Liste de paramètres à tester
    seuils = np.linspace(seuil_min,seuil_max,seuil_taille)
    params = [(j,i) for j in range(ma_min,ma_max + 1,1) for i in seuils]
    
    # Utilisation de dask.delayed pour préparer les tâches avec différents paramètres
    tasks = [delayed(sub_bitcoin_historic)(x, y) for x, y in params]
    
    tasks2 = [delayed(backtest_mean_reversion)(x,y) for x,y in params]
    
    # Exécution des tâches en parallèle et récupération des résultats
    results = dask.compute(*tasks)
    
     # Exécution des tâches en parallèle et récupération des résultats
    results2 = dask.compute(*tasks2)

    # Affiche les resultats de l'execution dans un dataframe
    donnees = {"Moyennes mobiles": [x for x,y in params],"Seuils": [y for x,y in params], 'Signals achats': [x for x,y in results], 'Signals ventes': [y for x,y in results],'Pnl strategie': [i for i in results2]}
    return pd.DataFrame(data=donnees)

@timer
def run_simu_backtest_mean_reversion_SLTP(seuil_min=0.01,seuil_max=0.02,seuil_taille=5,ma_min=10,ma_max=50):

    # Liste de paramètres à tester
    seuils = np.linspace(seuil_min,seuil_max,seuil_taille)
    SL = np.linspace(seuil_min,0.1,seuil_taille)
    TP = np.linspace(seuil_min,0.1,seuil_taille)
    params = [(j, i, k, l) for j in range(ma_min, ma_max + 1, 1) for i in seuils for k in SL for l in TP]
    
    # Utilisation de dask.delayed pour préparer les tâches avec différents paramètres
    tasks = [delayed(sub_bitcoin_historic)(ma, threshold) for ma, threshold, _, _ in params]

    tasks2 = [delayed(backtest_mean_reversion)(ma, threshold, sl, tp) for ma, threshold, sl, tp in params]
    
    # Exécution des tâches en parallèle et récupération des résultats
    results = dask.compute(*tasks)

     # Exécution des tâches en parallèle et récupération des résultats
    results2 = dask.compute(*tasks2)

    # Affiche les resultats de l'execution dans un dataframe
    donnees = {
        "Moyennes mobiles": [ma for ma, _, _, _ in params],
        "Seuils": [threshold for _, threshold, _, _ in params],
        "Signals achats": [x for x, y in results],
        "Signals ventes": [y for x, y in results],
        "Pnl strategie": [i for i in results2],
        "Stop loss": [sl for _, _, sl, _ in params],
        "Take profit": [tp for _, _, _, tp in params],
    }
    return pd.DataFrame(data=donnees)

def backtest_mean_reversion(MA, threshold,stop_loss=0.02, take_profit=0.04):
    # Génération des signaux de prise de position
    sub_data = df_sub_from_dates(data, DEFAULT_DATE_FROM, DEFAULT_DATE_TO)
    mean_rev = Strategy(sub_data, ma_window=MA, threshold=threshold)
    signals = mean_rev.generate_signals()
    
    # Chargement des signaux
    signals = list(signals["smooth_signal"])

    config = BacktestConfig(
        initial_cash=10_000.0,
        risk_per_trade=0.01,
        max_leverage=1.0,
        fee_bps=2.0,
        slippage_bps=1.0,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )
    result = Backtester(sub_data, signals, config).run()
    return result.stats.get("total_return", 0.0)
