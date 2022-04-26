from typing import (
    List,
    Tuple
)
from decimal import Decimal
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_pair import CrossExchangeMarketPair
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making import CrossExchangeMarketMakingStrategy
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making_config_map import \
    cross_exchange_market_making_config_map as xemm_map


def start(self):
    maker_market = xemm_map.get("maker_market").value.lower()
    taker_market = xemm_map.get("taker_market").value.lower()
    raw_maker_trading_pair = xemm_map.get("maker_market_trading_pair").value
    raw_taker_trading_pair = xemm_map.get("taker_market_trading_pair").value
    triangular_arbitrage_pair = xemm_map.get("triangular_arbitrage_pair").value
    min_profitability = xemm_map.get("min_profitability").value / Decimal("100")
    order_amount = xemm_map.get("order_amount").value
    strategy_report_interval = global_config_map.get("strategy_report_interval").value
    limit_order_min_expiration = xemm_map.get("limit_order_min_expiration").value
    cancel_order_threshold = xemm_map.get("cancel_order_threshold").value / Decimal("100")
    active_order_canceling = xemm_map.get("active_order_canceling").value
    adjust_order_enabled = xemm_map.get("adjust_order_enabled").value
    top_depth_tolerance = xemm_map.get("top_depth_tolerance").value
    top_depth_tolerance_taker = xemm_map.get("top_depth_tolerance_taker").value
    order_size_taker_volume_factor = xemm_map.get("order_size_taker_volume_factor").value / Decimal("100")
    order_size_taker_balance_factor = xemm_map.get("order_size_taker_balance_factor").value / Decimal("100")
    order_size_portfolio_ratio_limit = xemm_map.get("order_size_portfolio_ratio_limit").value / Decimal("100")
    order_size_maker_balance_factor = xemm_map.get("order_size_maker_balance_factor").value / Decimal("100")
    anti_hysteresis_duration = xemm_map.get("anti_hysteresis_duration").value
    filled_order_delay = xemm_map.get("filled_order_delay").value
    filled_order_delay_seconds = xemm_map.get("filled_order_delay_seconds").value
    use_oracle_conversion_rate = xemm_map.get("use_oracle_conversion_rate").value
    taker_to_maker_base_conversion_rate = xemm_map.get("taker_to_maker_base_conversion_rate").value
    taker_to_maker_quote_conversion_rate = xemm_map.get("taker_to_maker_quote_conversion_rate").value
    slippage_buffer = xemm_map.get("slippage_buffer").value / Decimal("100")
    min_order_amount = xemm_map.get("min_order_amount").value
    target_base_balance = xemm_map.get("target_base_balance").value
    slippage_buffer_fix = xemm_map.get("slippage_buffer_fix").value / Decimal("100")
    waiting_time = xemm_map.get("waiting_time").value
    keep_target_balance = xemm_map.get("keep_target_balance").value
    top_maker_cancel_seconds = xemm_map.get("top_maker_cancel_seconds").value
    triangular_arbitrage = xemm_map.get("triangular_arbitrage").value
    triangular_switch = xemm_map.get("triangular_switch").value
    cancel_order_timer = xemm_map.get("cancel_order_timer").value
    cancel_order_timer_seconds = xemm_map.get("cancel_order_timer_seconds").value
    balance_fix_maker = xemm_map.get("balance_fix_maker").value
    counter = 0
    restore_timer = 0
    top_maker_cancel_timer = 0
    fix_counter = 0
    maker_order_update = False
    taker_to_maker_base_conversion_rate = xemm_map.get("taker_to_maker_base_conversion_rate").value
    # check if top depth tolerance is a list or if trade size override exists
    if isinstance(top_depth_tolerance, list) or "trade_size_override" in xemm_map:
        self._notify("Current config is not compatible with cross exchange market making strategy. Please reconfigure")
        return

    try:
        maker_trading_pair: str = raw_maker_trading_pair
        taker_trading_pair: str = raw_taker_trading_pair
        third_trading_pair: str = triangular_arbitrage_pair
        maker_assets: Tuple[str, str] = self._initialize_market_assets(maker_market, [maker_trading_pair])[0]
        taker_assets: Tuple[str, str] = self._initialize_market_assets(taker_market, [taker_trading_pair])[0]
        if triangular_switch:
            third_assets: Tuple[str, str] = self._initialize_market_assets(maker_market, [third_trading_pair])[0]
        else:
            third_assets: Tuple[str, str] = self._initialize_market_assets(taker_market, [third_trading_pair])[0]
    except ValueError as e:
        self._notify(str(e))
        return

    market_names: List[Tuple[str, List[str]]] = [
        (maker_market, [maker_trading_pair]),
        (taker_market, [taker_trading_pair]),
        (maker_market, [third_trading_pair]),
    ]

    market_name: List[Tuple[str, List[str]]] = [
        (maker_market, [maker_trading_pair]),
        (taker_market, [taker_trading_pair]),
    ]

    if triangular_arbitrage:
        self._initialize_markets(market_names)
    else:
        self._initialize_markets(market_name)

    maker_data = [self.markets[maker_market], maker_trading_pair] + list(maker_assets)
    taker_data = [self.markets[taker_market], taker_trading_pair] + list(taker_assets)
    third_data = [self.markets[maker_market], third_trading_pair] + list(third_assets)
    maker_market_trading_pair_tuple = MarketTradingPairTuple(*maker_data)
    taker_market_trading_pair_tuple = MarketTradingPairTuple(*taker_data)
    third_market_trading_pair_tuple = MarketTradingPairTuple(*third_data)

    self.market_trading_pair_tuples = [maker_market_trading_pair_tuple, taker_market_trading_pair_tuple, third_market_trading_pair_tuple]
    self.market_pair = CrossExchangeMarketPair(maker=maker_market_trading_pair_tuple, taker=taker_market_trading_pair_tuple)

    strategy_logging_options = (
        CrossExchangeMarketMakingStrategy.OPTION_LOG_CREATE_ORDER
        | CrossExchangeMarketMakingStrategy.OPTION_LOG_ADJUST_ORDER
        | CrossExchangeMarketMakingStrategy.OPTION_LOG_MAKER_ORDER_FILLED
        | CrossExchangeMarketMakingStrategy.OPTION_LOG_REMOVING_ORDER
        | CrossExchangeMarketMakingStrategy.OPTION_LOG_STATUS_REPORT
        | CrossExchangeMarketMakingStrategy.OPTION_LOG_MAKER_ORDER_HEDGED
    )
    self.strategy = CrossExchangeMarketMakingStrategy()
    self.strategy.init_params(
        market_pairs=[self.market_pair],
        third_market=third_market_trading_pair_tuple,
        min_profitability=min_profitability,
        status_report_interval=strategy_report_interval,
        logging_options=strategy_logging_options,
        order_amount=order_amount,
        limit_order_min_expiration=limit_order_min_expiration,
        cancel_order_threshold=cancel_order_threshold,
        active_order_canceling=active_order_canceling,
        adjust_order_enabled=adjust_order_enabled,
        top_depth_tolerance=top_depth_tolerance,
        top_depth_tolerance_taker=top_depth_tolerance_taker,
        order_size_taker_volume_factor=order_size_taker_volume_factor,
        order_size_taker_balance_factor=order_size_taker_balance_factor,
        order_size_portfolio_ratio_limit=order_size_portfolio_ratio_limit,
        order_size_maker_balance_factor=order_size_maker_balance_factor,
        anti_hysteresis_duration=anti_hysteresis_duration,
        filled_order_delay=filled_order_delay,
        filled_order_delay_seconds=filled_order_delay_seconds,
        use_oracle_conversion_rate=use_oracle_conversion_rate,
        taker_to_maker_base_conversion_rate=taker_to_maker_base_conversion_rate,
        taker_to_maker_quote_conversion_rate=taker_to_maker_quote_conversion_rate,
        slippage_buffer=slippage_buffer,
        target_base_balance=target_base_balance,
        slippage_buffer_fix = slippage_buffer_fix,
        waiting_time = waiting_time,
        keep_target_balance = keep_target_balance,
        min_order_amount=min_order_amount,
        top_maker_cancel_seconds = top_maker_cancel_seconds,
        hb_app_notification=True,
        counter = counter,
        top_maker_cancel_timer = top_maker_cancel_timer,
        cancel_order_timer = cancel_order_timer,
        cancel_order_timer_seconds = cancel_order_timer_seconds,
        triangular_arbitrage = triangular_arbitrage,
        triangular_switch = triangular_switch,
        fix_counter = fix_counter,
        balance_fix_maker = balance_fix_maker,
        maker_order_update = maker_order_update
    )
