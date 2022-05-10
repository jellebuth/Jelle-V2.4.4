#!/usr/bin/env python

from typing import NamedTuple
from hummingbot.connector.exchange_base import ExchangeBase


class ExchangePairTuple(NamedTuple):
    maker: ExchangeBase
    kucoin: ExchangeBase
    gate_io: ExchangeBase
    taker: ExchangeBase
