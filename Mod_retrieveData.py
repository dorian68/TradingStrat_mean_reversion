import yfinance as yf
import pandas as pd

#https://fr.finance.yahoo.com/quote/GC%3DF/futures/
"""
def history(self, period="1mo", interval="1d",
            start=None, end=None, prepost=False, actions=True,
            auto_adjust=True, back_adjust=False,
            proxy=None, rounding=False, tz=None, timeout=None, **kwargs):
    
    :Parameters:
        period : str
            Valid periods: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max
            Either Use period parameter or use start and end
        interval : str
            Valid intervals: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo
            Intraday data cannot extend last 60 days
        start: str
            Download start date string (YYYY-MM-DD) or _datetime.
            Default is 1900-01-01
        end: str
            Download end date string (YYYY-MM-DD) or _datetime.
            Default is now
        prepost : bool
            Include Pre and Post market data in results?
            Default is False
        auto_adjust: bool
            Adjust all OHLC automatically? Default is True
        back_adjust: bool
            Back-adjusted data to mimic true historical prices
        proxy: str
            Optional. Proxy server URL scheme. Default is None
        rounding: bool
            Round values to 2 decimal places?
            Optional. Default is False = precision suggested by Yahoo!
        tz: str
            Optional timezone locale for dates.
            (default data is returned as non-localized dates)
        timeout: None or float
            If not None stops waiting for a response after given number of
            seconds. (Can also be a fraction of a second e.g. 0.01)
            Default is None.
        **kwargs: dict
            debug: bool
                Optional. If passed as False, will suppress
                error message printing to console.
    """
try:
    # get historical market data
    hist_msft = pd.read_csv(r"C:\Users\Do\Documents\HISTORIC_DATA\hist_msft.csv")
    hist_tsla = pd.read_csv(r"C:\Users\Do\Documents\HISTORIC_DATA\hist_tsla.csv")
    hist_dji = pd.read_csv(r"C:\Users\Do\Documents\HISTORIC_DATA\hist_dji.csv")
    hist_gold = pd.read_csv(r"C:\Users\Do\Documents\HISTORIC_DATA\hist_gold.csv")
    hist_btc = pd.read_csv(r"C:\Users\Do\Documents\HISTORIC_DATA\hist_btc.csv")
    print("Historical data loaded")

except(FileNotFoundError):
    print("WARNING - files not saved")

    # get historical market data
    msft = yf.Ticker("MSFT")
    tsla = yf.Ticker("TSLA")
    dji = yf.Ticker("^DJI")
    gold = yf.Ticker("GC=F")
    btcusd = yf.Ticker("BTC-USD")
    
    
    # get all stock info
    msft.info
    
    # get historical market data
    hist_msft = msft.history(period="10y")
    hist_tsla = tsla.history(period="10y")
    hist_dji = dji.history(period="10y")
    hist_gold = gold.history(period="10y")
    hist_btc = gold.history(period="10y")

    # save historical market data
    hist_msft = hist_msft.to_csv(r"C:\Users\Do\Documents\HISTORIC_DATA\hist_msft.csv")
    hist_tsla = hist_tsla.to_csv(r"C:\Users\Do\Documents\HISTORIC_DATA\hist_tsla.csv")
    hist_dji = hist_dji.to_csv(r"C:\Users\Do\Documents\HISTORIC_DATA\hist_dji.csv")
    hist_gold = hist_gold.to_csv(r"C:\Users\Do\Documents\HISTORIC_DATA\hist_gold.csv")
    hist_btc = hist_btc.to_csv(r"C:\Users\Do\Documents\HISTORIC_DATA\hist_btc.csv")
    print("Historical data saved")