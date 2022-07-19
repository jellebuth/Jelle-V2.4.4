cdef c_apply_vol_adjustment_multiplier(self, object proposal):
"""
Adjust the price of the bid and asks based on the volatility
If the first bid and ask spreads exceeds the max_volatility_spread limit. All order are adjusted to the max spread adjustment market_info_to_active_orders
If not, each order is adjusted for the max(slow_volatility, quick_volatility)
IMPORTANT: the spread IS A MULTIPLIER of the current spread
"""

cdef:
  ExchangeBase market = self._market_info.market
  volatility = self.get_volatility()
  mid_price = self.get_mid_price()

volatility_percentage = volatility/mid_price

volatility_adjusted = (
  Decimal(1) + (volatility_percentage * self._volatility_adjustment_multiplier))

first_bid_order_spread_adjusted = (
  self.get_first_order_proposal_spread(proposal)[0] * volatility_adjusted)
first_ask_order_spread_adjusted = (
  self.get_first_order_proposal_spread(proposal)[1] * volatility_adjusted)

if first_bid_order_spread_adjusted < self._max_volatility_spread:
volatility_adjusted_bid = volatility_adjusted
else:  # calculate the max percentage increase in spread
volatility_adjusted_bid = Decimal(1) + ((self._max_volatility_spread - self.get_first_order_proposal_spread(
  proposal)[0]) / self.get_first_order_proposal_spread(proposal)[0])

if first_ask_order_spread_adjusted < self._max_volatility_spread:
volatility_adjusted_ask = volatility_adjusted
else:
volatility_adjusted_ask = Decimal(1) + ((self._max_volatility_spread - self.get_first_order_proposal_spread(
  proposal)[1]) / self.get_first_order_proposal_spread(proposal)[1])

self.log_with_clock(
  logging.INFO,
  f"Vol_adjustment: vol_percentage {volatility_percentage} - volatility_adjusted_bid {volatility_adjusted_bid} - volatility_adjusted_ask {volatility_adjusted_ask}  "
)

for buy in proposal.buys:
price = buy.price
current_spread = (mid_price - price) / mid_price
new_spread = current_spread * volatility_adjusted_bid
volatility_adjusted_price = mid_price / (Decimal(1) + new_spread)

buy.price = market.c_quantize_order_price(
  self.trading_pair, volatility_adjusted_price)

for sell in proposal.sells:
price = sell.price
current_spread = (price - mid_price) / mid_price
new_spread = current_spread / volatility_adjusted_ask
volatility_adjusted_price = mid_price * (Decimal(1) + new_spread)
sell.price = market.c_quantize_order_price(
  self.trading_pair, volatility_adjusted_price)
