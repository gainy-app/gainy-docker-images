"""Stream type classes for tap-coingecko."""
from functools import cached_property
from pathlib import Path
from typing import Any, Dict, Optional, List

import requests
import hashlib

from tap_coingecko.client import CoingeckoStream

SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")


class CoinData(CoingeckoStream):
    name = "coingecko_coin"
    path = "/v3/coins/{id}"
    primary_keys = ["id"]
    selected_by_default = True

    STATE_MSG_FREQUENCY = 100

    schema_filepath = SCHEMAS_DIR / "coin_data.json"

    @cached_property
    def partitions(self) -> List[dict]:
        return self.load_coins()

    def get_url_params(self, context: Optional[dict], next_page_token: Optional[Any]) -> Dict[str, Any]:
        params = super().get_url_params(context, next_page_token)

        params["localization"] = "false"
        params["tickers"] = "false"

        return params

    def load_coins(self) -> List[Dict[str, str]]:
        coins = self.config.get("coins", None)

        if coins:
            self.logger.info(f"Using coins {coins} from the config parameter")
            coins = [ {"id": symbol} for coin in coins ]
        else:
            coins_limit = self.config.get("coins_limit", None)

            self.logger.info(f"Loading coins")
            params = super().get_url_params(None, None)
            params["include_platform"] = 'false'
            res = requests.get(
                url=f"{self.url_base}/v3/coins/list",
                params=params,
            )
            self._write_request_duration_log("/v3/coins/list", res, None, None)
            coins = [ {"id": coin['id']} for coin in res.json() ]

            if coins_limit is not None:
                coins = list(sorted(coins, key=lambda record: record['id']))[:coins_limit]

        return list(filter(lambda coin: self.is_within_split(coin['id']), sorted(coins, key=lambda coin: coin['id'])))

    def is_within_split(self, symbol) -> int:
        split_num = int(self.config.get("split_num", 1))
        split_id = int(self.config.get("split_id", 0))
        # Use built-in `hashlib` to get consistent hash value
        symbol_hash = int(hashlib.md5(symbol.encode("UTF-8")).hexdigest(), 16)
        return symbol_hash % split_num == split_id
