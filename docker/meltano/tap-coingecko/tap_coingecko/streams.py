"""Stream type classes for tap-coingecko."""
from functools import cached_property
from pathlib import Path
from typing import Any, Dict, Optional, List

import requests

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
            records = [
                {
                    "id": symbol,
                } for coin in coins
            ]
        else:
            coins_limit = self.config.get("coins_limit", None)

            self.logger.info(f"Loading coins")
            res = requests.get(
                url=f"{self.url_base}/v3/coins/list",
                params={"include_platform": 'false'}
            )
            self._write_request_duration_log("/v3/coins/list", res, None, None)

            records = [
                {
                    "id": coin['id'],
                } for coin in res.json()
            ]

            if coins_limit is not None:
                exchange_symbols = list(sorted(exchange_symbols, key=lambda record: record['id']))[:coins_limit]

        return records