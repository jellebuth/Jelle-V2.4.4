import ccxt
import pandas as pd
import ta
from ta import add_all_ta_features

def get_candlestick(exchange, pair, timeframe, limit, length):
      if exchange == "kucoin":
        exchange_name = ccxt.kucoin()
        ohlcv = exchange_name.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
        ohlcv = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close','volume'])
        ema = ta.trend.EMAIndicator(ohlcv['close'], length, True).ema_indicator().tail(1).item()
        max_timestamp = ohlcv["timestamp"].max()
        return ohlcv, ema, max_timestamp

      if exchange == "gate_io":
        exchange_name = ccxt.gateio()
        ohlcv = exchange_name.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
        ohlcv = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close','volume'])
        ema = ta.trend.EMAIndicator(ohlcv['close'], length, True).ema_indicator().tail(1).item()
        max_timestamp = ohlcv["timestamp"].max()
        return ohlcv, ema, max_timestamp

      if exchange == "binance":
        exchange_name = ccxt.binance()
        ohlcv = exchange_name.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
        ohlcv = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close','volume'])
        ema = ta.trend.EMAIndicator(ohlcv['close'], length, True).ema_indicator().tail(1).item()
        max_timestamp = ohlcv["timestamp"].max()
        return ohlcv, ema, max_timestamp

      if exchange == "ascend_ex":
        exchange_name = ccxt.ascendex()
        ohlcv = exchange_name.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
        ohlcv = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close','volume'])
        ema = ta.trend.EMAIndicator(ohlcv['close'], length, True).ema_indicator().tail(1).item()
        max_timestamp = ohlcv["timestamp"].max()
        return ohlcv, ema, max_timestamp
