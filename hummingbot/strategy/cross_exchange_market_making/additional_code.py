#new_variables
#self._counter


def balance_fix_check(self, market_pair):
    maker_market = market_pair.maker.market
    taker_market = market_pair.taker.market

    taker_base_balance = maket_market.get_balance(market_pair.taker.base_asset)
    maker_base_balance = maket_market.get_balance(market_pair.maker.base_asset)

    total_base_balance = taker_base_balance + maker_base_balance

    pref_base_min_actual = Decimal(
        self._target_base_balance - total_base_balance)

    order_size_base = abs(pref_base_min_actual)

    if order_size_base > self._min_order_amount and self._counter == 0:
      self._counter = self._counter + 1
      self.logger().info(
          f"Total Balance: {total_base_balance} pref_min_acutal {pref_base_min_actual} order size base: {order_size_base}")
      self._restore_timer = self._current_timestamp + self._waiting_time
      return True

    elif order_size_base > self._min_order_amount:
      return True

    else:
      self._counter = 0
      self._maker_order_update = False
      return False


def balance_fix_fix(self, market_pair):
      maker_market = market_pair.maker.market
      taker_market = market_pair.taker.market
      taker_trading_pair = market_pair.taker.trading_pair
      maker_trading_pair = market_pair.maker.trading_pair

      bid, ask = self.get_top_bid_ask(market_pair)
      mid_price = (bid + ask) / 2

      mid_price_buy_price = mid_price * \
          (Decimal("1") + self._slippage_buffer_fix)
      mid_price_sell_price = mid_price * \
          (Decimal("1") - self._slippage_buffer_fix)

      total_base_balance = taker_market.get_balance(
          market_pair.taker.base_asset) + maker_market.get_balance(market_pair.maker.base_asset)

      pref_base_min_actual = Decimal(
          self._target_base_balance - total_base_balance)

      maker_available_balance_base = maker_market.get_available_balance(
          market_pair.maker.base_asset)
      taker_available_balance_base = taker_market.c_get_available_balance(
          market_pair.taker.base_asset)

      maker_available_balance_quote = maker_market.get_available_balance(
          market_pair.maker.quote_asset)
      taker_available_balance_quote = taker_market.get_available_balance(
          market_pair.taker.quote_asset)

      order_size_base = abs(pref_base_min_actual)

      maker_order_size_in_quote = (order_size_base / mid_price_maker_buy_price)
      taker_order_size_in_quote = (order_size_base / mid_price_buy_price)

  if self._keep_target_balance:

        if self._current_timestamp > self._restore_timer and self.c_balance_fix_check(market_pair) and not self._maker_order_update:

                self.cancel_all_taker_limit_orders(market_pair)
                self.cancel_all_maker_limit_orders(market_pair)
                self.log_with_clock(
                    logging.INFO,
                    f"(Just canceled all orders to restore balance")

                self._fix_counter = self._fix_counter +1
                self.log_with_clock(
                    logging.INFO,
                    f"(fix_counter is now at: {self._fix_counter} balance fixes")


                if pref_base_min_actual > 0 and order_size_base > self._min_order_amount:
                    # second time checking if there is a difference, if there is, place buy order
                    # here you would want to cancell all orders on the exchanges
                    self.logger().info(f"Timer passed {self._waiting_time} seconds, current value of Timer: {self._counter} Order_size base: {order_size_base} Base Balance: {total_base_balance}, Target Balance: {self._target_base_balance}, Diff: {pref_base_min_actual}")
                    # available balance with a buy order on maker side
                    if self.check_available_balance(is_buy = True, market_pair = market_pair) == "buy_maker":

                        self.logger().info("Going to place a maker buy order to fix balance")

                        order_size_base = maker_market.quantize_order_amount(maker_trading_pair, Decimal(hedged_order_quantity))
                        mid_price_buy_price = maker_market.quantize_order_price(maker_trading_pair, mid_price_buy_price)

                        self.place_order(market_pair, market_pair.maker, False, order_size_base, Decimal(mid_price_buy_price))

                    # available balance with a buy order on taker side
                    elif self.check_available_balance(is_buy = True, market_pair = market_pair) == "buy_taker":
                         self.logger().info("Going to place a taker buy order to fix balance")

                         order_size_base = taker_market.quantize_order_amount(taker_trading_pair, Decimal(hedged_order_quantity))
                         mid_price_buy_price = taker_market.quantize_order_price(taker_trading_pair, mid_price_buy_price)

                         self.place_order(market_pair, market_pair.taker, False, order_size_base, Decimal(mid_price_buy_price))

                    elif self.check_available_balance(is_buy = True, market_pair = market_pair) == "buy_maker_taker":
                                # buy as much as possible on the taker exchange
                                self.place_order(market_pair, True, market_pair.taker, False, min(Decimal((taker_available_balance_quote / mid_price_buy_price)), maker_order_size_in_quote), Decimal(mid_price_buy_price))
                                self.logger().info(f"Place buy order on taker and maker - Taker buy order is placed with most available balance or at max size of the order to restore balance {min(Decimal((taker_available_balance_quote / mid_price_buy_price)), maker_order_size_in_quote)}")

                                # if there is enough remaining on the maker exchange, also place an order on the maker exchange with the remainging volume
                                if maker_order_size_in_quote - (taker_available_balance_quote / mid_price_buy_price > maker_available_balance_quote / mid_price_buy_price * (Decimal("1"))):
                                    self.c_place_order(market_pair, True, market_pair.maker, False, min(Decimal((taker_order_size_in_quote - min(Decimal((taker_available_balance_quote / mid_price_buy_price))))),maker_order_size_in_quote), Decimal(mid_price_buy_price))
                                    self.logger().info(f"Place buy order on taker and maker - The remaining amount of buy order is placed on the maker exchange {Decimal((taker_order_size_in_quote - (taker_available_balance_quote / mid_price_buy_price)))}")

                    self._counter = 0

                if pref_base_min_actual < 0 and order_size_base > self._min_order_amount:  # after checking again if there is a difference in balance
                          self.logger().info(f"Timer passed {self._waiting_time} seconds, current value of Timer: {self._counter} Order_size base: {order_size_base} Total Base Balance: {total_base_balance}, Target Balance: {self._target_base_balance}, Diff: {pref_base_min_actual}")
                          # available balance with a sell order on taker side

                          if self.c_check_available_balance(is_buy = False, market_pair = market_pair) == "sell_taker":
                              self.logger().info("Going to place a taker sell order to fix balance ")

                              order_size_base = taker_market.quantize_order_amount(taker_trading_pair, Decimal(hedged_order_quantity))
                              mid_price_buy_price = taker_market.quantize_order_price(taker_trading_pair, mid_price_buy_price)

                              self.place_order(market_pair, market_pair.taker, False, order_size_base, Decimal(mid_price_sell_price))

                          # available balance with a sell order on maker side
                          elif self.check_available_balance(is_buy = False, market_pair = market_pair) == "sell_maker":
                              self.logger().info("Going to place a maker sell order to fix balance")

                              order_size_base = maker_market.quantize_order_amount(maker_trading_pair, Decimal(hedged_order_quantity))
                              mid_price_buy_price = maker_market.quantize_order_price(maker_trading_pair, mid_price_buy_price)

                              self.place_order(market_pair, False, market_pair.maker, False, order_size_base, Decimal(mid_price_sell_price))

                          elif self.check_available_balance(is_buy = False, market_pair = market_pair) == "sell_maker_taker":
                                      # place order on the taker exchange with volume available balance
                                      self.place_order(market_pair, market_pair.taker, False,  min(taker_available_balance_base, order_size_base), mid_price_sell_price)
                                      self.logger().info(f"Place sell order on taker and maker - Taker sell order is placed with most available balance or at max size of the order to restore balance {min(taker_available_balance_base, order_size_base)} ")

                                      # if there is enough remaining on the maker exchange, also place an order on the maker exchange with the remainging value
                                      if order_size_base - min(taker_available_balance_base, order_size_base) > maker_available_balance_base:
                                          self.c_place_order(market_pair, False, market_pair.maker, False, (order_size_base - min(taker_available_balance_base, order_size_base)), mid_price_sell_price)
                                          self.logger().info(f"Place sell order on taker and maker - The remaining amount of {min(taker_available_balance_base, order_size_base)} sell order is placed on the maker exchange")

                          self._counter = 0

                return True
                 #return true, so if there was a mistake, ship the normal proces untill it does not return true

        else:
            return False


def check_available_balance(self, is_buy: bool, market_pair):
    maker_market = market_pair.maker.market
    taker_market = market_pair.taker.market
    taker_trading_pair = market_pair.taker.trading_pair
    maker_trading_pair = market_pair.maker.trading_pair

    bid, ask = self.get_top_bid_ask(market_pair)
    mid_price = (bid + ask) / 2

    mid_price_buy_price = mid_price * (Decimal("1") + self._slippage_buffer_fix)
    mid_price_sell_price = mid_price * (Decimal("1") - self._slippage_buffer_fix)

    total_base_balance = taker_market.get_balance(market_pair.taker.base_asset) + maker_market.get_balance(market_pair.maker.base_asset)

    pref_base_min_actual = Decimal(self._target_base_balance - total_base_balance)

    maker_available_balance_base = maker_market.get_available_balance(market_pair.maker.base_asset)
    taker_available_balance_base = taker_market.c_get_available_balance(market_pair.taker.base_asset)

    maker_available_balance_quote = maker_market.get_available_balance(market_pair.maker.quote_asset)
    taker_available_balance_quote = taker_market.get_available_balance(market_pair.taker.quote_asset)

    order_size_base = abs(pref_base_min_actual)

    maker_order_size_in_quote = (order_size_base / mid_price_buy_price)
    taker_order_size_in_quote = (order_size_base / mid_price_buy_price)
      # actual balance lower than wanted, thus need to buy
    if is_buy:
          if (taker_available_balance_quote/mid_price_buy_price) > order_size_base:  # check if availabale balance is enough
              self.logger().info(f"Taker enough quote balance {taker_available_balance_quote / mid_price_buy_price} to buy {order_size_base}, will place a taker buy order")
              return "buy_taker"

          elif (maker_available_balance_quote / mid_price_buy_price) > order_size_base :  # check if availabale balance is enough
              self.logger().info(f"Maker enough quote balance {maker_available_balance_quote / mid_price_buy_price} to buy {order_size_base}, will place a maker buy order")
              return "buy_maker"  # not enough balance to buy

          else:
                if (taker_available_balance_quote/mid_price_buy_price) + (maker_available_balance_quote / mid_price_buy_price)  > order_size_base:
                    return "buy_maker_taker"
                    self.logger().info(f"Enough quote balane on both exchanges only Taker: {(taker_available_balance_quote/mid_price_buy_price)}, Maker: {maker_available_balance_quote / mid_price_buy_price}, Total: {taker_available_balance_quote/mid_price_buy_price + (maker_available_balance_quote / mid_price__buy_price)}, to buy {order_size_base}, will place maker and taker buy")
                else:
                    self.logger().info(f"Not enough quote balance to buy Order size: {order_size_base}. Maker Quote balance: {maker_available_balance_quote}, Taker Quote balance:{taker_available_balance_quote} Order size in quote: {maker_order_size_in_quote}")
                return False

    else: # if is sell
          if (maker_available_balance_base + taker_available_balance_base) > order_size_base:
              return "sell_maker_taker"
              self.logger().info(f"Enough base balane on both exchanges only, Maker: {maker_available_balance_base}, Taker:{taker_available_balance_base}, Total: {(maker_available_balance_base + taker_available_balance_base)}, to sell {order_size_base}, will place taker and maker sell")
          else:
              self.logger().info(f"Not enough base balance to sell. order size: {order_size_base}")
              return False

          if taker_available_balance_base > order_size_base:
              self.logger().info(f"Taker enough base balance {taker_available_balance_base} to sell {order_size_base}, will place a taker sell order")
              return "sell_taker"
          elif maker_available_balance_base > order_size_base:
              self.logger().info(f"Maker enough base balance {maker_available_balance_base}, to sell {order_size_base}, will place a Maker sell order")
              return "sell_maker"

          else:  # not enough balance to place it on one available exchange
              if (maker_available_balance_base + taker_available_balance_base) > order_size_base:
                  return "sell_maker_taker"
                  self.logger().info(f"Enough base balane on both exchanges only, Maker: {maker_available_balance_base}, Taker:{taker_available_balance_base}, Total: {(maker_available_balance_base + taker_available_balance_base)}, to sell {order_size_base}, will place taker and maker sell")
              else:
                  self.logger().info(f"Not enough base balance to sell. order size: {order_size_base}")
                  return False





    def cancel_all_maker_limit_orders(self, market_pair):
        market_tuple = market_pair.maker
        limit_orders = self._sb_order_tracker.get_limit_orders()
        limit_orders = limit_orders.get(market_tuple, {})
        for order_id in limit_orders:
          self.cancel_order(market_tuple, order_id)
          self.stop_tracking_limit_order(market_tuple, order_id)


    def cancel_all_taker_limit_orders(self, market_pair):
        market_tuple = market_pair.taker
        limit_orders = self._sb_order_tracker.get_limit_orders()
        limit_orders = limit_orders.get(market_tuple, {})
        for order_id in limit_orders:
          self.cancel_order(market_tuple, order_id)
          self.stop_tracking_limit_order(market_tuple, order_id)
