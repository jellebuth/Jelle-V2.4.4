from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.hedge.hedge_config_map import hedge_config_map as c_map
from hummingbot.strategy.hedge.hedge import HedgeStrategy
from hummingbot.strategy.hedge.exchange_pair import ExchangePairTuple


def start(self):
    maker_exchange = c_map.get("maker_exchange").value.lower()
    kucoin_exchange = c_map.get("kucoin_exchange").value.lower()
    gate_exchange = c_map.get("gate_exchange").value.lower()
    taker_exchange = c_map.get("taker_exchange").value.lower()
    maker_assets = list(c_map.get("maker_assets").value.split(","))
    taker_markets = list(c_map.get("taker_markets").value.split(","))
    maker_assets = [m.strip().upper() for m in maker_assets]
    taker_markets = [m.strip().upper() for m in taker_markets]
    hedge_ratio = c_map.get("hedge_ratio").value
    leverage = c_map.get("leverage").value
    slippage = c_map.get("slippage").value
    max_order_age = c_map.get("max_order_age").value
    minimum_trade = c_map.get("minimum_trade").value
    hedge_interval = c_map.get("hedge_interval").value

    self._initialize_markets([(maker_exchange, taker_markets), (gate_exchange, taker_markets),(kucoin_exchange, taker_markets), (taker_exchange, taker_markets)])

    exchanges = ExchangePairTuple(maker=self.markets[maker_exchange], taker=self.markets[taker_exchange],
                                  kucoin=self.markets[kucoin_exchange], gate_io=self.markets[gate_exchange])

    #second option for the above functions, change the exchange_pair.pyx file so it refelcts every exchange
    #if kucoin in exchange_list:
    #    initialize_list.append((kucoin, []))
    #    exchanges.append(ExchangePairTuple(kucoin=self.markets[kucoin])) #do not know if the would work, this is replicating lines 23
    #if gate_io in exchange_list:
    #    initialize_list.append((gate_io, []))
    #    exchanges.append(ExchangePairTuple(gate_io=self.markets[gate_io]))
    #if binance in exchange_list:
    #    initialize_list.append((binance, []))
    #    exchanges.append(ExchangePairTuple(kucoin=self.markets[binance])) #do not know if the would work
    #self._initialize_markets(initialize_list) #initialize the final list, just like in line 22

    #other way of initializing the correct exchanges
    #initialize_list=[(taker_exchange, taker_markets)]
    #for exchange in exchange_list: #this list is generated in the configurations of the bot, just like how you specify the assets, you can now specify the exchanges
    #    exchange_initialize = (exchange, []) #this should be an object that is then stored in the initialize_list just like in line 22
    #    initialize_list.append(exchange_initialize)
    #self._initialize_markets(initialize_list) #initialize the final list, just like in line 22

    #the exchange_pair_tuple_names list hase the same objects as in the Exchange_pair.py file, the names in this file should thus be changes
    #exchange_pair_tuple_names = ["exchange1","exchange2","exchange3","exchange4","exchange5","exchange6","exchange7","exchange8","exchange9","exchange10"]
    #this part replicates the code in line 23, but then for every exchange
    #for i in len(range(exchange_list)):
    #    exchange_pair_tuple_name=exchange_pair_tuple_names[i]
    #    exchange_name=exchange_list[i]
    #    ExchangePairTuple(exchange_pair_tuple_name=self.markets[exchange_name]) #I am doubtfull it this works

    #this part replaces the get balance function in the hedge.pyx file
    #def get_balance(self, maker_asset: str): #replace this for the one in the pyx file
    #    balance = 0
    #    for in in len(range(exchange_list)):
    #        exchange_balance = exchange_list[i] #exchanges_balance variable is equal to exchange1, exchange2 etc.
    #        balance = balance + self._exchanges.exchange_balance.get_balance(maker_asset)
    #        return balance

    #def get_balance(self, maker_asset: str): #replace this for the one in the pyx file
    #    balance = 0
    #    for i in exchange_list):
    #        balance = balance + self._exchanges.i.get_balance(maker_asset)
    #        return balance

    #def wallet_df(self) -> pd.DataFrame:
    #    data=[]
    #    columns = ["Asset", "Price", "total_balance"]
    #    columns.append(exchange_list)
    #    columns.append(["Taker", "Diff", "Hedge Ratio"])
    #    for maker_asset in self._market_infos:
    #        taker_balance = self.get_shadow_position(trading_pair)
    #        mid_price = market_pair.get_mid_price()
    #        difference = - (total_balance + taker_balance)
    #        hedge_ratio = Decimal(-round(taker_balance/maker_balance, 2)) if maker_balance != 0 else 1
    #        market_pair = self._market_infos[maker_asset]
    #        trading_pair=market_pair.trading_pair
    #        total_balance = self.get_balance(maker_asset)
    #        data.append([
    #            maker_asset,
    #            mid_price,
    #            total_balance])
    #        for exchange in exchange_list:
    #             "exchange"= self._exchanges.exchange.get_balance(maker_asset) #need to review this
    #             data.append([exchange])
    #       data.append([taker_balance,
    #            difference,
    #            hedge_ratio,
    #        ]))
    #    return pd.DataFrame(data=data, columns=columns)'

    market_infos = {}
    for i, maker_asset in enumerate(maker_assets):
        taker_market = taker_markets[i]
        t_base, t_quote = taker_market.split("-")
        taker = MarketTradingPairTuple(
            self.markets[taker_exchange], taker_market, t_base, t_quote)
        market_infos[maker_asset] = taker

    self.strategy = HedgeStrategy()
    self.strategy.init_params(
        exchanges=exchanges,
        market_infos=market_infos,
        hedge_ratio=hedge_ratio,
        leverage=leverage,
        minimum_trade=minimum_trade,
        slippage=slippage,
        max_order_age=max_order_age,
        hedge_interval=hedge_interval,
    )
