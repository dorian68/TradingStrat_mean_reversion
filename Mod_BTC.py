import datetime
import numpy as np
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import time

date_from = "28-11-2019 00:00:00"
date_to = "28-11-2019 10:00:00"

def timer(function):

    def fct_in_between(*arg):
        start = time.time()
        res = function(*arg)
        end = time.time()
        print("--- %s seconds ---" % (end - start))
        return res
        
    return fct_in_between

def df_sub_from_dates(data,date_from,date_to):
    obj_date_from = datetime.strptime(date_from,'%d-%m-%Y %H:%M:%S')
    obj_date_to = datetime.strptime(date_to,'%d-%m-%Y %H:%M:%S')
    
    sub_data = data[(data['Timestamp'] > obj_date_from) & (data['Timestamp'] < obj_date_to)]
    return sub_data.ffill()

def sub_bitcoin_historic(window=14, threshold=0.02):  
    rsi_sensi = 12

    sub_data = df_sub_from_dates(data,date_from,date_to)
    #local_min_idx = argrelmin(sub_data["Close"])

    # lookthrough to find signals     
    mean_rev = Strategy(sub_data,ma_window=window, threshold=threshold)
    df_meanR = mean_rev.generate_signals()
    df_meanR_signal = df_meanR[df_meanR["Signal"] != 0]
    
    buy, _ = df_meanR_signal[df_meanR_signal["Signal"] == 1].shape
    sell, _ = df_meanR_signal[df_meanR_signal["Signal"] == -1].shape
    return buy, sell

# retrieve Bitcoin historical datas
data = pd.read_csv(r"C:\Windows.old\Users\ld\Documents\Entreprenariat\Projets Guadeloupe\DATASETS\bitstampUSD_1-min_data_2012-01-01_to_2021-03-31.csv")
data['Timestamp'] = data['Timestamp'].apply(lambda x: datetime.fromtimestamp(x))
#data["RSI"] = rsi(data)

# compute exponential moving averages
period_14 = 14
period_50 = 50
data["MA_14"] = data["Close"].ewm(com = period_14 - 1, adjust=True).mean()
data["MA_50"] = data["Close"].ewm(com = period_50 - 1, adjust=True).mean()
#data["Timestamp_date"] = data['Timestamp'].apply(lambda x:datetime.strptime(date_from,'%d-%m-%Y %H:%M:%S'))