"""REST client handling, including coingeckoStream base class."""
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, List
from abc import ABC, abstractmethod

import hashlib
import datadog.api
import requests
import backoff
import singer
from singer import RecordMessage
from singer_sdk.streams import RESTStream
from singer_sdk.helpers._typing import conform_record_data_types
from singer_sdk.helpers._util import utc_now
from singer_sdk.exceptions import RetriableAPIError

SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")


class CoingeckoStream(RESTStream, ABC):
    """coingecko stream class."""

    @property
    @abstractmethod
    def is_realtime(self) -> bool:
        pass

    @property
    def url_base(self) -> str:
        if self.config.get("api_key"):
            return "https://pro-api.coingecko.com/api"
        else:
            return "https://api.coingecko.com/api"

    def get_url_params(self, context: Optional[dict],
                       next_page_token: Optional[Any]) -> Dict[str, Any]:
        params = super().get_url_params(context, next_page_token)

        api_key = self.config.get("api_key")
        if api_key:
            params["x_cg_pro_api_key"] = api_key

        return params

    def get_next_page_token(self, response: requests.Response,
                            previous_token: Optional[Any]) -> Optional[Any]:
        return None

    def validate_response(self, response: requests.Response) -> None:
        if response.status_code == 429:
            msg = (f"{response.status_code} Client Error: "
                   f"{response.reason} for path: {self.path}")
            raise RetriableAPIError(msg)

        super().validate_response(response)

    def request_decorator(self, func: Callable) -> Callable:
        decorator: Callable = backoff.on_exception(
            backoff.expo,
            (
                RetriableAPIError,
                requests.exceptions.ReadTimeout,
            ),
            max_tries=5,
            factor=5,
        )(func)
        return decorator

    def load_coins(self) -> List[Dict[str, str]]:
        coins = self.config.get("coins", None)

        if coins:
            self.logger.info(f"Using coins {coins} from the config parameter")
            coins = [{"id": symbol} for coin in coins]
        else:
            coins_limit = self.config.get("coins_limit", None)

            params = self.get_url_params(None, None)
            self.logger.info(
                "Loading coins from %s %s api key, %s api key in config",
                self.url_base,
                'with' if 'x_cg_pro_api_key' in params else 'without',
                'with' if 'api_key' in self.config else 'without')

            params["include_platform"] = 'false'
            res = requests.get(
                url=f"{self.url_base}/v3/coins/list",
                params=params,
            )
            self._write_request_duration_log("/v3/coins/list", res, None, None)

            res_data = res.json()
            if not isinstance(res_data, list):
                self.logger.error(f"Error while loading coins: {res_data}")
                return []

            coins = [{"id": coin['id']} for coin in res_data]

            if coins_limit is not None:
                coins = list(sorted(
                    coins, key=lambda record: record['id']))[:coins_limit]

        return list(
            filter(lambda coin: self.is_within_split(coin['id']),
                   sorted(coins, key=lambda coin: coin['id'])))

    def is_within_split(self, symbol) -> int:
        split_num = int(self.config.get("split_num", 1))
        split_id = int(self.config.get("split_id", 0))
        # Use built-in `hashlib` to get consistent hash value
        symbol_hash = int(hashlib.md5(symbol.encode("UTF-8")).hexdigest(), 16)
        return symbol_hash % split_num == split_id

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

    def _write_metric_log(self, metric: dict,
                          extra_tags: Optional[dict]) -> None:
        super()._write_metric_log(metric, extra_tags)
        self._send_to_datadog(metric, ["counter"])

    def _send_to_datadog(self, metric, types, add_env=True):
        try:
            if metric["type"] in types:
                datadog.initialize()

                tag_list = []
                if "tags" in metric:
                    tag_list += [
                        f"{tag[0]}:{tag[1]}" for tag in metric["tags"].items()
                    ]

                if add_env and "ENV" in os.environ:
                    tag_list.append(f"env:{os.environ['ENV']}")

                datadog.api.Metric.send(
                    metric=f"data.tap.{self.name}.{metric['metric']}",
                    type="count",
                    points=metric["value"],
                    tags=tag_list)
            else:
                self.logger.debug(f"Skipping metric: {metric['metric']}")

        except Exception as e:
            self.logger.warning(
                f"Metric was not sent due to an error: '{str(e)}'")
