"""Stream type classes for tap-coingecko."""
from functools import cached_property
from pathlib import Path
from typing import Any, Dict, Optional, Iterable, List

from tap_coingecko.client import CoingeckoStream

SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")


class CoinData(CoingeckoStream):
    name = "coingecko_coin"
    path = "/v3/coins/{id}"
    primary_keys = ["id"]
    selected_by_default = True

    STATE_MSG_FREQUENCY = 100

    schema_filepath = SCHEMAS_DIR / "coin_data.json"

    @property
    def is_realtime(self) -> bool:
        return False

    @cached_property
    def partitions(self) -> List[dict]:
        return self.load_coins()

    def get_url_params(self, context: Optional[dict], next_page_token: Optional[Any]) -> Dict[str, Any]:
        params = super().get_url_params(context, next_page_token)

        params["localization"] = "false"
        params["tickers"] = "false"

        return params

    def get_records(self, context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        try:
            yield from super().get_records(context)
        except Exception as e:
            self.logger.error('Error while requesting %s for coin %s: %s' % (self.name, context['id'], str(e)))
            pass


class CoinMarketRealtimeData(CoingeckoStream):
    name = "coingecko_market_realtime"
    path = "/v3/coins/markets"
    primary_keys = ["id"]
    selected_by_default = True
    STATE_MSG_FREQUENCY = 100
    schema_filepath = SCHEMAS_DIR / "coin_market_realtime.json"

    per_page = 500

    @property
    def is_realtime(self) -> bool:
        return True

    @property
    def url_base(self) -> str:
        return "https://api.coingecko.com/api"

    @cached_property
    def partitions(self) -> List[dict]:
        records = self.load_coins()
        partitions = []
        for page_start in range(0, len(records), self.per_page):
            batch = records[page_start:min(len(records), page_start + self.per_page)]
            batch_coin_ids = [record["id"] for record in batch]
            partitions.append({"ids": ",".join(batch_coin_ids)})
        return partitions

    def get_url_params(self, context: Optional[dict], next_page_token: Optional[Any]) -> Dict[str, Any]:
        params = super().get_url_params(context, next_page_token)

        params["vs_currency"] = "usd"
        params["ids"] = context["ids"]
        params["sparkline"] = "false"

        return params

    def get_records(self, context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        try:
            yield from super().get_records(context)
        except Exception as e:
            self.logger.error('Error while requesting %s for coins %s: %s' % (self.name, context['ids'], str(e)))
            pass
