import math
from datetime import datetime
from decimal import Decimal
from typing import Optional

from hummingbot.client.config.config_validators import (
    validate_bool,
    validate_datetime_iso_string,
    validate_decimal,
    validate_exchange,
    validate_market_trading_pair,
)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import AllConnectorSettings, required_exchanges


def trading_pair_prompt():
    exchange = twap_config_map.get("connector").value
    example = AllConnectorSettings.get_example_pairs().get(exchange)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (exchange, f" (e.g. {example})" if example else "")


def str2bool(value: str):
    return str(value).lower() in ("yes", "y", "true", "t", "1")

# checks if the trading pair is valid


def validate_market_trading_pair_tuple(value: str) -> Optional[str]:
    exchange = twap_config_map.get("connector").value
    return validate_market_trading_pair(exchange, value)


twap_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt=None,
                  default="TwapTradeStrategy"),
    "connector":
        ConfigVar(key="connector",
                  prompt="Enter the name of spot connector >>> ",
                  validator=validate_exchange,
                  on_validated=lambda value: required_exchanges.append(value),
                  prompt_on_new=True),
    "trading_pair":
        ConfigVar(key="trading_pair",
                  prompt=trading_pair_prompt,
                  validator=validate_market_trading_pair_tuple,
                  prompt_on_new=True),

    "location":
        ConfigVar(key="location",
                  prompt="Where would you like to store your csv, type location + file name + .csv e.g. 'local/home/documents/collect_data.csv' >>> ",
                  default="",
                  prompt_on_new=True),

}
