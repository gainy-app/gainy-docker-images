"""REST client handling, including polygonStream base class."""
import os
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, List, Callable

import backoff
import datadog.api
import requests
from singer_sdk.streams import RESTStream
from singer_sdk.exceptions import RetriableAPIError

SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")


class PolygonStream(RESTStream):
    """polygon stream class."""

    url_base = "https://api.polygon.io"

    def request_decorator(self, func: Callable) -> Callable:
        decorator: Callable = backoff.on_exception(
            backoff.expo,
            (RetriableAPIError, ),
            max_tries=6,
            factor=5,
            jitter=lambda w: w / 2 + backoff.full_jitter(w / 2),
        )(func)
        return decorator

    def get_next_page_token(self, response: requests.Response,
                            previous_token: Optional[Any]) -> Optional[Any]:
        return None

    def get_url_params(self, context: Optional[dict],
                       next_page_token: Optional[Any]) -> Dict[str, Any]:
        """Return a dictionary of values to be used in URL parameterization."""
        params: dict = {"apiKey": self.config['api_key']}
        return params

    @property
    def split_id(self):
        return int(self.config.get("split_id", 0))

    def is_within_split(self, symbol) -> int:
        split_num = int(self.config.get("split_num", 1))
        # Use built-in `hashlib` to get consistent hash value
        symbol_hash = int(hashlib.md5(symbol.encode("UTF-8")).hexdigest(), 16)
        return symbol_hash % split_num == self.split_id

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
