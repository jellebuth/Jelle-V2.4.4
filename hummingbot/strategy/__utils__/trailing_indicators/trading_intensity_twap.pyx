# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

import warnings
from decimal import Decimal
from typing import Tuple
import logging

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


cdef class TradingIntensityIndicator:

    def __init__(self, order_book: OrderBook, price_delegate: AssetPriceDelegate, db_name):
        self._trades_forwarder = TradesForwarder(self)
        self._order_book = order_book
        self._order_book.c_add_listener(OrderBookEvent.TradeEvent.value, self._trades_forwarder)
        self._price_delegate = price_delegate




    def register_trade(self, trade):
        """A helper method to be used in unit tests"""
        self.c_register_trade(trade)

    cdef c_register_trade(self, object trade):
        self._current_trade_sample.append(trade)
