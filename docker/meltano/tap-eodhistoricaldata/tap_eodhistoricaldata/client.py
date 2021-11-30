"""REST client handling, including eodhistoricaldataStream base class."""
import os
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, List

import datadog.api
import requests
from singer_sdk.streams import RESTStream

SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")


class eodhistoricaldataStream(RESTStream):
    """eodhistoricaldata stream class."""

    url_base = "https://eodhistoricaldata.com/api"

    def get_next_page_token(
            self, response: requests.Response, previous_token: Optional[Any]
    ) -> Optional[Any]:
        return None

    def get_url_params(
            self, context: Optional[dict], next_page_token: Optional[Any]
    ) -> Dict[str, Any]:
        """Return a dictionary of values to be used in URL parameterization."""
        params: dict = {"api_token": self.config['api_token']}
        return params

    def load_symbols(self, symbols: List[str] = None, exchanges: List[str] = None):
        if symbols:
            self.logger.info("Using symbols from the config parameter")
            symbols = symbols
        else:
            self.logger.info(f"Loading symbols for exchanges: {exchanges}")
            exchange_url = f"{self.url_base}/exchange-symbol-list"
            symbols = []
            for exchange in self.config["exchanges"]:
                res = requests.get(
                    url=f"{exchange_url}/{exchange}",
                    params={"api_token": self.config["api_token"], "fmt": "json"}
                )
                self._write_request_duration_log("/exchange-symbol-list", res, None, None)

                exchange_symbols = list(map(lambda record: record["Code"], res.json()))
                symbols += exchange_symbols

        return list(filter(lambda s: self.is_within_split(s), sorted(symbols)))

    def split_num(self) -> int:
        return self.config.get("split-num", 1)

    def split_id(self) -> int:
        return self.config.get("split-id", 0)

    def is_within_split(self, symbol) -> int:
        # Use built-in `hashlib` to get consistent hash value
        symbol_hash = int(hashlib.md5(symbol.encode("UTF-8")).hexdigest(), 16)
        return symbol_hash % self.split_num() == self.split_id()

    def _write_metric_log(self, metric: dict, extra_tags: Optional[dict]) -> None:
        super()._write_metric_log(metric, extra_tags)
        self._send_to_datadog(metric, ["counter"])

    def _send_to_datadog(self, metric, types, add_env=True):
        try:
            if metric["type"] in types:
                datadog.initialize()

                tag_list = []
                if "tags" in metric:
                    tag_list += [f"{tag[0]}:{tag[1]}" for tag in metric["tags"].items()]

                if add_env and "ENV" in os.environ:
                    tag_list.append(f"env:{os.environ['ENV']}")

                datadog.api.Metric.send(
                    metric=f"data.tap.{self.name}.{metric['metric']}",
                    type="count",
                    points=metric["value"],
                    tags=tag_list
                )
            else:
                self.logger.debug(f"Skipping metric: {metric['metric']}")

        except Exception as e:
            self.logger.warning(f"Metric was not sent due to an error: '{str(e)}'")
