# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp
from hummingbot.core.data_type.common import (
    OrderType,
    PriceType,
    TradeType
)



import warnings
from decimal import Decimal
from typing import Tuple
import logging
import pandas as pd
import os

import numpy as np
from scipy.optimize import curve_fit
from scipy.optimize import OptimizeWarning

from hummingbot.core.data_type.common import (
    PriceType,
)
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.event_listener cimport EventListener
from hummingbot.core.event.events import OrderBookEvent
from hummingbot.strategy.asset_price_delegate import AssetPriceDelegate

cdef class TradesForwarder(EventListener):
    def __init__(self, indicator: 'TradingIntensityIndicator'):
        self._indicator = indicator

    cdef c_call(self, object arg):
        self._indicator.c_register_trade(arg)

pmm_logger = None

cdef class TradingIntensityIndicator:

    def __init__(self, order_book: OrderBook, price_delegate: AssetPriceDelegate, sampling_length: int = 30):
        self._alpha_buy = 0
        self._kappa_buy = 0
        self._alpha_sell = 0
        self._kappa_sell = 0
        self._trade_samples = {}
        self._current_trade_sample = []
        self._trades_forwarder = TradesForwarder(self)
        self._order_book = order_book
        self._order_book.c_add_listener(OrderBookEvent.TradeEvent.value, self._trades_forwarder)
        self._price_delegate = price_delegate
        self._sampling_length = sampling_length
        self._samples_length = 0
        self._last_quotes = []
        self._round = 0
        self._current_timestamp = 0

        warnings.simplefilter("ignore", OptimizeWarning)

    @classmethod
    def logger(cls):
        global pmm_logger
        if pmm_logger is None:
            pmm_logger = logging.getLogger(__name__)
        return pmm_logger

    @property
    def current_value(self) -> Tuple[float, float]:
        return self._alpha_buy, self._kappa_buy, self._alpha_sell, self._kappa_sell

    @property
    def is_sampling_buffer_full(self) -> bool:
        return len(self._trade_samples.keys()) == self._sampling_length

    @property
    def is_sampling_buffer_changed(self) -> bool:
        is_changed = self._samples_length != len(self._trade_samples.keys())
        self._samples_length = len(self._trade_samples.keys())
        return is_changed

    @property
    def sampling_length(self) -> int:
        return self._sampling_length

    @sampling_length.setter
    def sampling_length(self, new_len: int):
        self._sampling_length = new_len

    @property
    def last_quotes(self) -> list:
        """A helper method to be used in unit tests"""
        return self._last_quotes

    @last_quotes.setter
    def last_quotes(self, value):
        """A helper method to be used in unit tests"""
        self._last_quotes = value

    def calculate(self, timestamp):
        """A helper method to be used in unit tests"""
        self.c_calculate(timestamp)

    cdef c_calculate(self, timestamp):
        self._current_timestamp = timestamp
        #current mid_price
        price = self._price_delegate.get_price_by_type(PriceType.MidPrice)
        # Descending order of price-timestamp quotes of the incomming trades
        self._last_quotes = [{'timestamp': timestamp, 'price': price}] + self._last_quotes

        latest_processed_quote_idx = None
        for trade in self._current_trade_sample: #for each trade in the unprocessed trade sample list
            for i, quote in enumerate(self._last_quotes):
                if quote["timestamp"] < trade.timestamp: # only do this for trades that happened after the last mid_price recording
                    if latest_processed_quote_idx is None or i < latest_processed_quote_idx: #to keep track if all trades hae been processed
                        latest_processed_quote_idx = i
                    #here is where we can store the data
                    trade = {"price_level": abs(trade.price - float(quote["price"])), "amount": trade.amount, "buy": trade.type == TradeType.BUY} #absolute difference between the mid_price and the trade amount

                    if quote["timestamp"] + 1 not in self._trade_samples.keys(): #if timestamp +1 not in the trades yet, add the current trade data
                        self._trade_samples[quote["timestamp"] + 1] = []

                    self._trade_samples[quote["timestamp"] + 1] += [trade]
                    break

        # THere are no trades left to process
        self._current_trade_sample = []
        # Store quotes that happened after the latest trade + one before
        if latest_processed_quote_idx is not None:
            self._last_quotes = self._last_quotes[0:latest_processed_quote_idx + 1]

        if len(self._trade_samples.keys()) > self._sampling_length: #if buffer is full -> remove the last one
            timestamps = list(self._trade_samples.keys())
            timestamps.sort()
            timestamps = timestamps[-self._sampling_length:]

            trade_samples = {} #empty the whole dict
            for timestamp in timestamps:
                trade_samples[timestamp] = self._trade_samples[timestamp] #add current timestamps to the trades samples dict
            self._trade_samples = trade_samples


        if self.is_sampling_buffer_full:
            self.c_estimate_intensity()

    def register_trade(self, trade):
        """A helper method to be used in unit tests"""
        self.c_register_trade(trade)


    cdef c_register_trade(self, object trade):
        self._current_trade_sample.append(trade)

    cdef c_estimate_intensity(self):
        cdef:
            dict trades_consolidated
            list lambdas
            list price_levels

        # Calculate lambdas / trading intensities
        lambdas_buy = []
        lambdas_sell = []


        trades_consolidated_buy = {} #list of price level and amount per price level
        price_levels_buy = [] #list of price levels

        trades_consolidated_sell = {} #list of price level and amount per price level
        price_levels_sell = [] #list of price levels


        for timestamp in self._trade_samples.keys():
            tick = self._trade_samples[timestamp] #list of timestamps + correstonding trade levels + amount at that timestamp
            for trade in tick: #tick = timetamp + the price level and amount value at that timestamp, could be multiple
              if trade['buy']:
                  if trade['price_level'] not in trades_consolidated_buy.keys():  #only process if price level is not in price level already
                      trades_consolidated_buy[trade['price_level']] = 0
                      price_levels_buy += [trade['price_level']] #add the price levels

                  trades_consolidated_buy[trade['price_level']] += trade['amount'] #add amout to the respective price level

              if not trade['buy']:
                  if trade['price_level'] not in trades_consolidated_sell.keys():  #only process if price level is not in price level already
                      trades_consolidated_sell[trade['price_level']] = 0
                      price_levels_sell += [trade['price_level']] #add the price levels

                  trades_consolidated_sell[trade['price_level']] += trade['amount'] #add amout to the respective price level

        price_levels_buy = sorted(price_levels_buy, reverse=True) #just a list of all price levels but then sorted
        price_levels_sell = sorted(price_levels_sell, reverse=True) #just a list of all price levels but then sorted

        for price_level in price_levels_buy: #price levels are all unique price levels

            lambdas_buy += [trades_consolidated_buy[price_level]] #list or amounts from the trades_consolidated dict sorted from lowest price level to highest

        for price_level in price_levels_sell: #price levels are all unique price levels

            lambdas_sell += [trades_consolidated_sell[price_level]] #list or amounts from the trades_consolidated dict sorted from lowest price level to highest


        # Adjust to be able to calculate log
        lambdas_adj_buy = [10**-10 if x==0 else x for x in lambdas_buy] #same values as lambdas
        lambdas_adj_sell = [10**-10 if x==0 else x for x in lambdas_sell] #same values as lambdas

        # Fit the probability density function; reuse previously calculated parameters as initial values
        try:
            params_buy = curve_fit(lambda t, a, b: a*np.exp(-b*t),
                               price_levels_buy,
                               lambdas_adj_buy,
                               p0=(self._alpha_buy, self._kappa_buy),
                               method='dogbox',
                               bounds=([0, 0], [np.inf, np.inf]))

            self._kappa_buy = Decimal(str(params_buy[0][1]))
            self._alpha_buy = Decimal(str(params_buy[0][0]))

        except (RuntimeError, ValueError) as e:
            pass

        try:
            params_sell = curve_fit(lambda t, a, b: a*np.exp(-b*t),
                               price_levels_sell,
                               lambdas_adj_sell,
                               p0=(self._alpha_sell, self._kappa_sell),
                               method='dogbox',
                               bounds=([0, 0], [np.inf, np.inf]))

            self._kappa_buy = Decimal(str(params_sell[0][1]))
            self._alpha_buy = Decimal(str(params_sell[0][0]))

        except (RuntimeError, ValueError) as e:
            pass
