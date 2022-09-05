from datetime import datetime
from typing import List, Tuple

from hummingbot.strategy.conditional_execution_state import RunAlwaysExecutionState, RunInTimeConditionalExecutionState
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.twap import TwapTradeStrategy
from hummingbot.strategy.twap.twap_config_map import twap_config_map


def start(self):
    try:
        exchange = twap_config_map.get("connector").value.lower()
        raw_market_trading_pair = twap_config_map.get("trading_pair").value
        location = twap_config_map.get("location").value

        try:
            assets: Tuple[str, str] = self._initialize_market_assets(
                exchange, [raw_market_trading_pair])[0]
        except ValueError as e:
            self._notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [
            (exchange, [raw_market_trading_pair])]

        self._initialize_markets(market_names)
        maker_data = [self.markets[exchange],
                      raw_market_trading_pair] + list(assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]
        self.strategy = TwapTradeStrategy(market_infos=[MarketTradingPairTuple(*maker_data)],
                                          location=location,
                                          exchange=exchange)
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
