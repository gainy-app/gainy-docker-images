"""REST client handling, including eodhistoricaldataStream base class."""
import os
import re
import hashlib
from pathlib import Path
from typing import Any, Callable, Dict, Optional, List

import datadog.api
import requests
import backoff
from singer_sdk.streams import RESTStream
from singer_sdk.exceptions import RetriableAPIError

SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")

EXCHANGE_POSTFIXES = {'CC': '.CC', 'INDX': '.INDX'}


class eodhistoricaldataStream(RESTStream):
    """eodhistoricaldata stream class."""

    url_base = "https://eodhistoricaldata.com/api"

    def get_next_page_token(self, response: requests.Response,
                            previous_token: Optional[Any]) -> Optional[Any]:
        return None

    def get_url_params(self, context: Optional[dict],
                       next_page_token: Optional[Any]) -> Dict[str, Any]:
        """Return a dictionary of values to be used in URL parameterization."""
        params: dict = {"api_token": self.config['api_token']}
        return params

    def request_decorator(self, func: Callable) -> Callable:
        decorator: Callable = backoff.on_exception(
            backoff.expo,
            (
                RetriableAPIError,
                requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout,
            ),
            max_tries=5,
            factor=2,
        )(func)
        return decorator

    def post_process(self, row: dict, context: Optional[dict] = None) -> dict:

        def replace_na(row):
            for k, v in row.items():
                if v == 'NA' or v == '"NA"':
                    row[k] = None
            return row

        return replace_na(row)

    def load_symbols(self, exchange=None) -> List[Dict[str, str]]:
        self.logger.info(f"Loading symbols with config: {self.config}")
        symbols = self.config.get("symbols", None)

        if symbols:
            symbols_type = self.config.get("symbols_type", None)
            symbols_exchange = self.config.get("symbols_exchange", None)
            self.logger.info("Using symbols from the config parameter")
            symbols = map(lambda symbol: re.sub(r'\.CC$', '-USD.CC', symbol),
                          symbols)
            records = [{
                "Code": symbol,
                "Type": symbols_type,
                "Exchange": symbols_exchange,
            } for symbol in symbols]
        else:
            exchange_symbols_limit = self.config.get("exchange_symbols_limit",
                                                     None)
            if exchange is None:
                exchanges = self.config.get("exchanges", [])
            else:
                exchanges = [exchange]

            self.logger.info(f"Loading symbols for exchanges: {exchanges}")
            exchange_url = f"{self.url_base}/exchange-symbol-list"
            records = []
            for exchange in exchanges:
                res = requests.get(url=f"{exchange_url}/{exchange}",
                                   params={
                                       "api_token": self.config["api_token"],
                                       "fmt": "json"
                                   })
                self._write_request_duration_log("/exchange-symbol-list", res,
                                                 None, None)

                exchange_symbols = [{
                    "Code":
                    record["Code"] + self.get_ticker_postfix(exchange),
                    "Type":
                    record["Type"],
                    "Exchange":
                    record["Exchange"],
                } for record in res.json()]

                if exchange_symbols_limit is not None:
                    exchange_symbols = list(
                        sorted(exchange_symbols,
                               key=lambda record: record['Code'])
                    )[:exchange_symbols_limit]

                records += exchange_symbols

        return list(
            filter(lambda record: self.is_within_split(record['Code']),
                   sorted(records, key=lambda record: record['Code'])))

    def load_split_symbols(self, exchange: str, dates: List[str]) -> List[str]:
        self.logger.info(f"Loading symbols' splits for exchange: {exchange}")

        url = f"{self.url_base}/eod-bulk-last-day/{exchange}"
        symbols = set()
        params = {
            "api_token": self.config["api_token"],
            "type": "splits",
            "fmt": "json"
        }
        for date in dates:
            params["date"] = date
            res = requests.get(url=url, params=params)
            self._write_request_duration_log("/eod-bulk-last-day?type=splits",
                                             res, None, None)

            for record in res.json():
                symbols.add(record["code"] + self.get_ticker_postfix(exchange))

        exchange_symbols_limit = self.config.get("exchange_symbols_limit",
                                                 None)
        if exchange_symbols_limit is not None:
            symbols = list(sorted(symbols))[:exchange_symbols_limit]

        return list(symbols)

    def split_num(self) -> int:
        return int(self.config.get("split_num", "1"))

    def split_id(self) -> int:
        return int(self.config.get("split_id", "0"))

    def is_within_split(self, symbol) -> int:
        # Use built-in `hashlib` to get consistent hash value
        symbol_hash = int(hashlib.md5(symbol.encode("UTF-8")).hexdigest(), 16)
        return symbol_hash % self.split_num() == self.split_id()

    def get_ticker_postfix(self, exchange) -> str:
        return EXCHANGE_POSTFIXES.get(exchange, '')

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
