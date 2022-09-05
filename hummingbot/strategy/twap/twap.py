from datetime import datetime
from decimal import Decimal
import logging
import statistics
from typing import (
    List,
    Tuple,
    Optional,
    Dict
)
import os
import pandas as pd
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.events import (MarketOrderFailureEvent,
                                          OrderCancelledEvent,
                                          OrderExpiredEvent,
                                          )
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.conditional_execution_state import ConditionalExecutionState, RunAlwaysExecutionState
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.event.events import OrderBookEvent

from sqlalchemy import create_engine
import sqlalchemy as db

twap_logger = None


class TradesForwarder(EventListener):
    def __init__(self, strategy: 'TwapTradeStrategy'):
        self._indicator = strategy

    def call(self, arg: object):
        self._indicator.register_trade(arg)


class TwapTradeStrategy(StrategyPyBase):
    """
    Time-Weighted Average Price strategy
    This strategy is intended for  executing trades evenly over a specified time period.
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global twap_logger
        if twap_logger is None:
            twap_logger = logging.getLogger(__name__)
        return twap_logger

    def __init__(self,
                 market_infos: List[MarketTradingPairTuple],
                 location: str = '',
                 exchange: str = 'Binance',
                 status_report_interval: float = 900,
                 order_book: OrderBook = OrderBook
                 ):
        """
        :param market_infos: list of market trading pairs
        :param is_buy: if the order is to buy
        :param target_asset_amount: qty of the order to place
        :param order_step_size: amount of base asset to be configured in each order
        :param order_price: price to place the order at
        :param order_delay_time: how long to wait between placing trades
        :param execution_state: execution state object with the conditions that should be satisfied to run each tick
        :param cancel_order_wait_time: how long to wait before cancelling an order
        :param status_report_interval: how often to report network connection related warnings, if any
        """

        if len(market_infos) < 1:
            raise ValueError("market_infos must not be empty.")

        super().__init__()
        self._market_infos = {
            (market_info.market, market_info.trading_pair): market_info
            for market_info in market_infos
        }
        self._all_markets_ready = False
        self._place_orders = True
        self._status_report_interval = status_report_interval
        self._time_to_cancel = {}
        self._first_order = True
        self._previous_timestamp = 0
        self._last_timestamp = 0
        self._location = location
        self._exchange = exchange

        self._engine = " "
        self._connection = " "

        self._trades_forwarder = TradesForwarder(self)
        self._order_book = order_book
        self._order_book.c_add_listener(
            OrderBookEvent.TradeEvent.value, self._trades_forwarder)

        all_markets = set([market_info.market for market_info in market_infos])
        self.add_markets(list(all_markets))

    def configuration_status_lines(self,):
        lines = ["", "  Configuration:"]

        for market_info in self._market_infos.values():
            lines.append("    "
                         f"{market_info.base_asset}    "
                         f"Order price: {PerformanceMetrics.smart_round(self._order_price)} "
                         f"{market_info.quote_asset}    "
                         f"Order size: {PerformanceMetrics.smart_round(self._order_step_size)} "
                         f"{market_info.base_asset}")

        return lines

    def register_trade(self, trade: object):
        self.log_with_clock(
            logging.INFO,
            f"just registered a trade"
        )

    def format_status(self) -> str:
        lines: list = []
        warning_lines: list = []

        lines.extend(self.configuration_status_lines())

        for market_info in self._market_infos.values():

            warning_lines.extend(self.network_warning([market_info]))

            markets_df = self.market_status_data_frame([market_info])
            lines.extend(["", "  Markets:"] + ["    "
                                               + line for line in markets_df.to_string().split("\n")])

            assets_df = self.wallet_balance_data_frame([market_info])
            lines.extend(["", "  Assets:"] + ["    "
                                              + line for line in assets_df.to_string().split("\n")])

        if warning_lines:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    def process_market(self, market_info):
        """
        Checks if enough time has elapsed from previous order to place order and if so, calls place_orders_for_market() and
        cancels orders if they are older than self._cancel_order_wait_time.

        :param market_info: a market trading pair
        """
        market: ExchangeBase = market_info.market
        trading_pair: str = market_info.trading_pair
        order_book: OrderBook = market_info.order_book

        self.c_dump_debug_variables(market_info)

    def start(self, clock: Clock, timestamp: float):
        self._previous_timestamp = timestamp
        self._last_timestamp = timestamp

        self._engine = create_engine(
            'mysql+pymysql://hb:Jelle123@hb.ceh1qcgkh4yh.ap-northeast-1.rds.amazonaws.com/Hummingbot')
        self._connection = self._engine.connect()

        self._engine.execute('''DROP TABLE IF EXISTS DATA_COLLECTION''')

        self.log_with_clock(
            logging.INFO,
            f"Connected to database, engine = {self._engine}, connection = {self._connection}"
        )

    def tick(self, timestamp: float):
        """
        Clock tick entry point.
        For the TWAP strategy, this function simply checks for the readiness and connection status of markets, and
        then delegates the processing of each market info to process_market().

        :param timestamp: current tick timestamp
        """

        try:
            self.process_tick(timestamp)
        finally:

            self._last_timestamp = timestamp

    def process_tick(self, timestamp: float):
        """
        Clock tick entry point.
        For the TWAP strategy, this function simply checks for the readiness and connection status of markets, and
        then delegates the processing of each market info to process_market().
        """
        current_tick = timestamp // self._status_report_interval
        last_tick = (self._last_timestamp // self._status_report_interval)
        should_report_warnings = current_tick > last_tick

        if not self._all_markets_ready:
            self._all_markets_ready = all(
                [market.ready for market in self.active_markets])
            if not self._all_markets_ready:
                # Markets not ready yet. Don't do anything.
                if should_report_warnings:
                    self.logger().warning("Markets are not ready. No market making trades are permitted.")
                return

        if (should_report_warnings
                and not all([market.network_status is NetworkStatus.CONNECTED for market in self.active_markets])):
            self.logger().warning("WARNING: Some markets are not connected or are down at the moment. Market "
                                  "making may be dangerous when markets or networks are unstable.")

        for market_info in self._market_infos.values():
            self.process_market(market_info)

    def c_weighted_mid_price_0_1(self, market_info):

        market: ExchangeBase = market_info.market
        trading_pair: str = market_info.trading_pair
        order_book: OrderBook = market_info.order_book

        top_ask = market.get_price(trading_pair, True)
        top_bid = market.get_price(trading_pair, False)
        mid_price = market_info.get_mid_price()
        percentage_depth = Decimal(0.001)
        ask_price_range = (mid_price * (Decimal(1) + percentage_depth))
        bid_price_range = (mid_price / (Decimal(1) + percentage_depth))
        volume_bid_side = order_book.get_volume_for_price(
            False, bid_price_range).result_volume
        volume_ask_side = order_book.get_volume_for_price(
            True, ask_price_range).result_volume

        return volume_bid_side, volume_ask_side

    def c_weighted_mid_price_0_25(self, market_info):

        market: ExchangeBase = market_info.market
        trading_pair: str = market_info.trading_pair
        order_book: OrderBook = market_info.order_book

        top_ask = market.get_price(trading_pair, True)
        top_bid = market.get_price(trading_pair, False)
        mid_price = market_info.get_mid_price()
        percentage_depth = Decimal(0.0025)
        ask_price_range = (mid_price * (Decimal(1) + percentage_depth))
        bid_price_range = (mid_price / (Decimal(1) + percentage_depth))
        volume_bid_side = order_book.get_volume_for_price(
            False, bid_price_range).result_volume
        volume_ask_side = order_book.get_volume_for_price(
            True, ask_price_range).result_volume

        return volume_bid_side, volume_ask_side

    def c_weighted_mid_price_0_5(self, market_info):

        market: ExchangeBase = market_info.market
        trading_pair: str = market_info.trading_pair
        order_book: OrderBook = market_info.order_book

        top_ask = market.get_price(trading_pair, True)
        top_bid = market.get_price(trading_pair, False)
        mid_price = market_info.get_mid_price()
        percentage_depth = Decimal(0.005)
        ask_price_range = (mid_price * (Decimal(1) + percentage_depth))
        bid_price_range = (mid_price / (Decimal(1) + percentage_depth))
        volume_bid_side = order_book.get_volume_for_price(
            False, bid_price_range).result_volume
        volume_ask_side = order_book.get_volume_for_price(
            True, ask_price_range).result_volume

        return volume_bid_side, volume_ask_side

    def c_weighted_mid_price_1_0(self, market_info):

        market: ExchangeBase = market_info.market
        trading_pair: str = market_info.trading_pair
        order_book: OrderBook = market_info.order_book

        top_ask = market.get_price(trading_pair, True)
        top_bid = market.get_price(trading_pair, False)
        mid_price = market_info.get_mid_price()
        percentage_depth = Decimal(0.01)
        ask_price_range = (mid_price * (Decimal(1) + percentage_depth))
        bid_price_range = (mid_price / (Decimal(1) + percentage_depth))
        volume_bid_side = order_book.get_volume_for_price(
            False, bid_price_range).result_volume
        volume_ask_side = order_book.get_volume_for_price(
            True, ask_price_range).result_volume

        return volume_bid_side, volume_ask_side

    def c_weighted_mid_price_1_5(self, market_info):

        market: ExchangeBase = market_info.market
        trading_pair: str = market_info.trading_pair
        order_book: OrderBook = market_info.order_book

        top_ask = market.get_price(trading_pair, True)
        top_bid = market.get_price(trading_pair, False)
        mid_price = market_info.get_mid_price()
        percentage_depth = Decimal(0.015)
        ask_price_range = (mid_price * (Decimal(1) + percentage_depth))
        bid_price_range = (mid_price / (Decimal(1) + percentage_depth))
        volume_bid_side = order_book.get_volume_for_price(
            False, bid_price_range).result_volume
        volume_ask_side = order_book.get_volume_for_price(
            True, ask_price_range).result_volume

        return volume_bid_side, volume_ask_side

    def c_weighted_mid_price_2(self, market_info):

        market: ExchangeBase = market_info.market
        trading_pair: str = market_info.trading_pair
        order_book: OrderBook = market_info.order_book

        top_ask = market.get_price(trading_pair, True)
        top_bid = market.get_price(trading_pair, False)
        mid_price = market_info.get_mid_price()
        percentage_depth = Decimal(0.02)
        ask_price_range = (mid_price * (Decimal(1) + percentage_depth))
        bid_price_range = (mid_price / (Decimal(1) + percentage_depth))
        volume_bid_side = order_book.get_volume_for_price(
            False, bid_price_range).result_volume
        volume_ask_side = order_book.get_volume_for_price(
            True, ask_price_range).result_volume

        return volume_bid_side, volume_ask_side

    def c_weighted_mid_price_3_5(self, market_info):

        market: ExchangeBase = market_info.market
        trading_pair: str = market_info.trading_pair
        order_book: OrderBook = market_info.order_book

        top_ask = market.get_price(trading_pair, True)
        top_bid = market.get_price(trading_pair, False)
        mid_price = market_info.get_mid_price()
        percentage_depth = Decimal(0.035)
        ask_price_range = (mid_price * (Decimal(1) + percentage_depth))
        bid_price_range = (mid_price / (Decimal(1) + percentage_depth))
        volume_bid_side = order_book.get_volume_for_price(
            False, bid_price_range).result_volume
        volume_ask_side = order_book.get_volume_for_price(
            True, ask_price_range).result_volume

        return volume_bid_side, volume_ask_side

    def c_weighted_mid_price_5(self, market_info):

        market: ExchangeBase = market_info.market
        trading_pair: str = market_info.trading_pair
        order_book: OrderBook = market_info.order_book

        top_ask = market.get_price(trading_pair, True)
        top_bid = market.get_price(trading_pair, False)
        mid_price = market_info.get_mid_price()
        percentage_depth = Decimal(0.05)
        ask_price_range = (mid_price * (Decimal(1) + percentage_depth))
        bid_price_range = (mid_price / (Decimal(1) + percentage_depth))
        volume_bid_side = order_book.get_volume_for_price(
            False, bid_price_range).result_volume
        volume_ask_side = order_book.get_volume_for_price(
            True, ask_price_range).result_volume

        return volume_bid_side, volume_ask_side

    def c_get_spread(self, market_info):

        market: ExchangeBase = market_info.market
        trading_pair: str = market_info.trading_pair
        order_book: OrderBook = market_info.order_book

        top_ask = market.get_price(trading_pair, True)
        top_bid = market.get_price(trading_pair, False)
        mid_price = market_info.get_mid_price()

        spread = ((top_ask - top_bid) / mid_price) * 100
        spread_absolute = top_ask - top_bid
        return spread, spread_absolute

    def c_dump_debug_variables(self, market_info):

        market: ExchangeBase = market_info.market
        trading_pair: str = market_info.trading_pair
        order_book: OrderBook = market_info.order_book

        timestamp = self.current_timestamp
        bid_5 = self.c_weighted_mid_price_5(market_info)[0]
        bid_3_5 = self.c_weighted_mid_price_3_5(market_info)[0]
        bid_2 = self.c_weighted_mid_price_2(market_info)[0]
        bid_1_5 = self.c_weighted_mid_price_1_5(market_info)[0]
        bid_1 = self.c_weighted_mid_price_1_0(market_info)[0]
        bid_0_5 = self.c_weighted_mid_price_0_5(market_info)[0]
        bid_0_25 = self.c_weighted_mid_price_0_25(market_info)[0]
        bid_0_1 = self.c_weighted_mid_price_0_1(market_info)[0]
        ask_0_1 = self.c_weighted_mid_price_0_1(market_info)[1]
        ask_0_25 = self.c_weighted_mid_price_0_25(market_info)[1]
        ask_0_5 = self.c_weighted_mid_price_0_5(market_info)[1]
        ask_1 = self.c_weighted_mid_price_1_0(market_info)[1]
        ask_1_5 = self.c_weighted_mid_price_1_5(market_info)[1]
        ask_2 = self.c_weighted_mid_price_2(market_info)[1]
        ask_3_5 = self.c_weighted_mid_price_3_5(market_info)[1]
        ask_5 = self.c_weighted_mid_price_5(market_info)[1]
        spread_percentage = self.c_get_spread(market_info)[0]
        spread_absolute = self.c_get_spread(market_info)[1]
        pair = market_info.trading_pair
        exchange = self._exchange

        #increments
        bid_5_increment = bid_5 - bid_3_5
        bid_3_5_increment = bid_3_5 - bid_2
        bid_2_increment = bid_2 - bid_1_5
        bid_1_5_increment = bid_1_5 - bid_1
        bid_1_increment = bid_1 - bid_0_5
        bid_0_5_increment = bid_0_5 - bid_0_25
        bid_0_25_incement = bid_0_25 - bid_0_1
        bid_0_1_increment = bid_0_1
        ask_0_1_increment = ask_0_1
        ask_0_25_increment = ask_0_25 - ask_0_1
        ask_0_5_increment = ask_0_5 - ask_0_25
        ask_1_increment = ask_1 - ask_0_5
        ask_1_5_increment = ask_1_5 - ask_1
        ask_2_increment = ask_2 - ask_1_5
        ask_3_5_increment = ask_3_5 - ask_2
        ask_5_increment = ask_5 - ask_3_5

        #other metrics
        order_book_imbalance_0_5 = bid_0_5 / (ask_0_5 + bid_0_5)
        top_ask = market.get_price(trading_pair, True)
        top_bid = market.get_price(trading_pair, False)
        mid_price = ((top_ask + top_bid) / 2)

        if not os.path.exists(self._location):
            df_header = pd.DataFrame([(
                'timestamp',
                'bid_5.0%_depth',
                'bid_3.5%_depth',
                'bid_2.0%_depth',
                'bid_1.5%_depth',
                'bid_1.0%_depth',
                'bid_0.5%_depth',
                'bid_0.25%_depth',
                'bid_0.1%_depth',
                'ask_0.1%_depth',
                'ask_0.25%_depth',
                'ask_0.5%_depth',
                'ask_1.0%_depth',
                'ask_1.5%_depth',
                'ask_2.0%_depth',
                'ask_3.5%_depth',
                'ask_5.0%_depth',
                'bid_5.0%_increment_depth',
                'bid_3.5%_increment_depth',
                'bid_2.0%_increment_depth',
                'bid_1.5%_increment_depth',
                'bid_1.0%_increment_depth',
                'bid_0.5%_increment_depth',
                'bid_0.25%_increment_depth',
                'bid_0.1%_increment_depth',
                'ask_0.1%_increment_depth',
                'ask_0.25%_increment_depth',
                'ask_0.5%_increment_depth',
                'ask_1.0%_increment_depth',
                'ask_1.5%_increment_depth',
                'ask_2.0%_increment_depth',
                'ask_3.5%_increment_depth',
                'ask_5.0%_increment_depth',
                'mid_price',
                'spread_absolute',
                'spread percentage',
                '0.5_order_book_imbalance',
                'pair',
                'exchange',
                'snapshot'
            )])
            df_header.to_csv(self._location, mode='a',
                             header=False, index=False)

        df = pd.DataFrame([(timestamp,
                            bid_5,
                            bid_3_5,
                            bid_2,
                            bid_1_5,
                            bid_1,
                            bid_0_5,
                            bid_0_25,
                            bid_0_1,
                            ask_0_1,
                            ask_0_25,
                            ask_0_5,
                            ask_1,
                            ask_1_5,
                            ask_2,
                            ask_3_5,
                            ask_5,
                            bid_5_increment,
                            bid_3_5_increment,
                            bid_2_increment,
                            bid_1_5_increment,
                            bid_1_increment,
                            bid_0_5_increment,
                            bid_0_25_incement,
                            bid_0_1_increment,
                            ask_0_1_increment,
                            ask_0_25_increment,
                            ask_0_5_increment,
                            ask_1_increment,
                            ask_1_5_increment,
                            ask_2_increment,
                            ask_3_5_increment,
                            ask_5_increment,
                            mid_price,
                            spread_absolute,
                            spread_percentage,
                            order_book_imbalance_0_5,
                            pair,
                            exchange,
                            self._market_info.order_book.snapshot
                            )])
        df.to_csv(self._location, mode='a', header=False, index=False)

        df.to_sql('DATA_COLLECTION', con=self._connection,
                  if_exists='append', index=False)

        #'/Users/jellebuth/Documents/test4.csv'
