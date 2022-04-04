"""Stream type classes for tap-coingecko."""
from abc import ABC
from datetime import datetime
from datetime import timedelta
from functools import cached_property, reduce
from pathlib import Path
from typing import Any, Dict, Optional, Iterable, List

import requests
import singer
from singer import RecordMessage
from singer_sdk.helpers._typing import conform_record_data_types
from singer_sdk.helpers._util import utc_now

from tap_coingecko.client import CoingeckoStream

SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")


class AbstractCoingeckoStream(CoingeckoStream):
    def _write_record_message(self, record: dict) -> None:
        """Write out a RECORD message."""
        record = conform_record_data_types(
            stream_name=self.name,
            row=record,
            schema=self.schema,
            logger=self.logger,
        )
        for stream_map in self.stream_maps:
            mapped_record = stream_map.transform(record)
            # Emit record if not filtered
            if mapped_record is not None:
                record_message = RecordMessage(
                    stream=stream_map.stream_alias,
                    record=mapped_record,
                    version=None,
                    time_extracted=utc_now(),
                )
                singer.write_message(record_message)

    def get_records(self, context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        try:
            yield from super().get_records(context)
        except Exception as e:
            self.logger.error('Error while requesting %s for coin %s: %s' % (self.name, context['id'], str(e)))
            pass


class CoinData(AbstractCoingeckoStream):
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