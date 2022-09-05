# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

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
        self._alpha = 0
        self._kappa = 0
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
        return self._alpha, self._kappa

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
                    trade_price = trade.price
                    side = trade.type
                    amount = trade.amount
                    price_level = abs(trade.price - float(quote["price"]))


                    trade = {"price_level": abs(trade.price - float(quote["price"])), "amount": trade.amount} #absolute difference between the mid_price and the trade amount

                    if quote["timestamp"] + 1 not in self._trade_samples.keys(): #if timestamp +1 not in the trades yet, add the current trade data
                        self._trade_samples[quote["timestamp"] + 1] = []

                    self._trade_samples[quote["timestamp"] + 1] += [trade]

                    timestamp = quote["timestamp"]
                    timestamp_plus = quote["timestamp"] + 1
                    mid_price = quote["price"]


                    if os.path.exists('/Users/jellebuth/Documents/tradeinfo_hotcross.csv'):
                      pass
                    else:
                        df_header = pd.DataFrame([('timestamp',
                                                    'trade_price',
                                                    'side',
                                                    'mid_price',
                                                    'price_level',
                                                    'amount')])
                        df_header.to_csv('/Users/jellebuth/Documents/tradeinfo_hotcross.csv', mode='a', header=False, index=False)

                    df = pd.DataFrame([(timestamp,
                                        trade_price,
                                        side,
                                        mid_price,
                                        price_level,
                                        amount)])

                    df.to_csv('/Users/jellebuth/Documents/tradeinfo_hotcross.csv', mode='a', header=False, index=False)



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
        lambdas = []

        trades_consolidated = {} #list of price level and amount per price level
        price_levels = [] #list of price levels


        for timestamp in self._trade_samples.keys():
            tick = self._trade_samples[timestamp] #list of timestamps + correstonding trade levels + amount at that timestamp
            for trade in tick: #tick = timetamp + the price level and amount value at that timestamp, could be multiple
                if trade['price_level'] not in trades_consolidated.keys():  #only process if price level is not in price level already
                    trades_consolidated[trade['price_level']] = 0
                    price_levels += [trade['price_level']] #add the price levels

                trades_consolidated[trade['price_level']] += trade['amount'] #add amout to the respective price level

        price_levels = sorted(price_levels, reverse=True) #just a list of all price levels but then sorted


        self.logger().info(f"trades_consolidated {trades_consolidated}")
        for price_level in price_levels: #price levels are all unique price levels

            lambdas += [trades_consolidated[price_level]] #list or amounts from the trades_consolidated dict sorted from lowest price level to highest


        # Adjust to be able to calculate log
        lambdas_adj = [10**-10 if x==0 else x for x in lambdas] #same values as lambdas
        self.logger().info(f"lambdas_adj  {lambdas_adj} price_levels {price_levels} len lamd {len(lambdas_adj)} len price_level {len(price_levels)}")

        #experimental


        # Fit the probability density function; reuse previously calculated parameters as initial values
        try:
            params = curve_fit(lambda t, a, b: a*np.exp(-b*t),
                               price_levels,
                               lambdas_adj,
                               p0=(self._alpha, self._kappa),
                               method='dogbox',
                               bounds=([0, 0], [np.inf, np.inf]))

            self._kappa = Decimal(str(params[0][1]))
            self._alpha = Decimal(str(params[0][0]))

        except (RuntimeError, ValueError) as e:
            pass


        if os.path.exists('/Users/jellebuth/Documents/curvefit_hotcross.csv'):
          pass
        else:
            df_header = pd.DataFrame([('round','timestamp',
                                        'lambdas_adjusted',
                                        'price_levels',
                                        'kappa',
                                        'alpha')])
            df_header.to_csv('/Users/jellebuth/Documents/curvefit_hotcross.csv', mode='a', header=False, index=False)

        for i in range(len(lambdas_adj)):
          df = pd.DataFrame([(self._round,
                              self._current_timestamp,
                              lambdas_adj[i],
                              price_levels[i],
                              self._kappa,
                              self._alpha)])

          df.to_csv('/Users/jellebuth/Documents/curvefit_hotcross.csv', mode='a', header=False, index=False)
        self._round = self._round + 1
