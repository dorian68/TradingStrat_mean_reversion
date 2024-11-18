import numpy as np

class TradingBot:
    nb_call = 0
    def __init__(self, capital=20 ,stop_loss=0.02, take_profit=0.04):
        """
        Initialise le bot de trading avec des niveaux de stop-loss et de take-profit.

        :param stop_loss: Pourcentage de perte maximum avant de clôturer la position.
        :param take_profit: Pourcentage de profit cible avant de clôturer la position.
        """
        self.orders = {}
        self.position = None  # Pas de position ouverte au début
        self.entry_price = None
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.capital = capital  # Exemple de capital initial
        self.position_size = 0.1  # Fraction du capital allouée par position (10% ici)
        self.log = "" # log de l'ensemble des position prises par l'algo
        TradingBot.nb_call += 1
    
    def enter_position(self, price, signal):
        """
        Entre dans une position d'achat ou de vente.

        :param price: Prix actuel de l'actif.
        :param signal: Signal de la stratégie ('buy' ou 'sell').
        """
        if signal == 'buy':
            self.position = 'long'
            self.entry_price = price
            order_id = self.generate_orderId()
            self.log += f"Position d'achat ouverte à {price}. ID :{order_id}\n"
        elif signal == 'sell':
            self.position = 'short'
            self.entry_price = price
            order_id = self.generate_orderId()
            self.log += f"Position de vente ouverte à {price}. ID :{order_id}\n"
        self.orders[order_id] = {"position":self.position,"entry_price":self.entry_price,"P/L":0,"Status":"Open"}

    def exit_position(self, order_id,price):
        """
        Sort de la position en cours et calcule le profit ou la perte.

        :param price: Prix actuel de l'actif.
        """
        cursor = self.orders[order_id]
        if cursor["position"] == 'long':
            perf = (price - cursor["entry_price"]) / cursor["entry_price"]
            profit_loss = perf * self.position_size * self.capital
            self.log += f"Position longue clôturée à {price}. Profit/perte : {profit_loss:.3f}. performance : {perf:.5f}. ID :{order_id}\n"

        elif cursor["position"] == 'short':
            perf = (cursor["entry_price"] - price) / cursor["entry_price"]
            profit_loss = perf * self.position_size * self.capital
            self.log += f"Position courte clôturée à {price}. Profit/perte : {profit_loss:.3f}. performance : {perf:.5f}. ID :{order_id}\n"
            
        self.orders[order_id]["Status"] = "Terminated"
        self.orders[order_id]["P/L"] = profit_loss
        
        # Remettre à zéro la position
        self.position = None
        self.entry_price = None

    def manage_position(self, price):
        """
        Vérifie les conditions de stop-loss et take-profit et sort de la position si nécessaire.

        :param price: Prix actuel de l'actif.
        """
        
        for elem in self.orders.keys():
            cursor = self.orders[elem]
            if cursor["Status"] != "Terminated":        
                if cursor["position"] == 'long':
                    if (price - cursor["entry_price"]) / cursor["entry_price"] >= self.take_profit:
                        self.log += f"Take-profit atteint pour la position longue, ID: {elem}\n"
                        self.exit_position(elem,price)
                    elif (cursor["entry_price"] - price) / cursor["entry_price"] >= self.stop_loss:
                        self.log += f"Stop-loss atteint pour la position longue, ID: {elem}\n"
                        self.exit_position(elem,price)
                    else:
                        self.log += f"Position {cursor["position"]}. perf : {(price - cursor["entry_price"]) / cursor["entry_price"]}. ID : {elem}\n"
                
                elif cursor["position"] == 'short':
                    if (cursor["entry_price"] - price) / cursor["entry_price"] >= self.take_profit:
                        self.log += f"Take-profit atteint pour la position courte, ID: {elem}\n"
                        self.exit_position(elem,price)
                    elif (price - cursor["entry_price"]) / cursor["entry_price"] >= self.stop_loss:
                        self.log += f"Stop-loss atteint pour la position courte, ID: {elem}\n"
                        self.exit_position(elem,price)
                    else:
                        self.log += f"Position {cursor["position"]}. perf : {(price - cursor["entry_price"]) / cursor["entry_price"]}. ID : {elem}\n"
    
    def run_strategy(self, prices, signals):
        """
        Exécute la stratégie sur une série de prix et signaux.

        :param prices: Liste des prix de l'actif.
        :param signals: Liste des signaux associés à chaque prix ('buy', 'sell', ou 'hold').
        """
        for price, signal in zip(prices, signals):
            if signal == 'buy':# and not self.position:
                self.enter_position(price, signal)
            elif signal == 'sell':# and not self.position:
                self.enter_position(price, signal)
            elif signal == 'hold':
                # Gérer les positions ouvertes
                self.manage_position(price)
    def Log(self):
        print(self.log)

    def Pnl(self):   
        return dict_sum(self.orders)

    def generate_orderId(self):
        rand_id = np.random.randint(100000,999999)
        if not rand_id in self.orders.keys(): 
            return rand_id
        else:
            while rand_id in self.orders.keys():
                rand_id = np.random.randint(100000,999999)
            return rand_id
            

def dict_sum(dict):
    sum = 0
    for id in dict.keys():
        sum += dict[id]["P/L"]
    return sum
        
def convert(dict,lst):
    return [dict[i] for i in lst]

dict = {
    0:'hold', 
    1:'buy',
    -1:'sell'
}

def generate_orderId(dict_orders):
    rand_id = np.random.randint(100000,999999)
    if not rand_id in dict_orders.keys(): 
        return rand_id
    else:
        while rand_id in dict_orders.keys():
            rand_id = np.random.randint(100000,999999)
        return rand_id
        
def detect_trend(prices):
    delta = [prices[i+1] - prices[i] for i in range(len(prices) - 1)]
    mn = np.mean(delta)

    if mn > 0:
        res = "hausse"
    elif mn < 0:
        res = "baisse"
    elif res > 0.001:
        res = "stable"
    return res

# Exemple
prices = [100, 102, 105, 103, 107]
print(detect_trend(prices))  # Devrait renvoyer "hausse"