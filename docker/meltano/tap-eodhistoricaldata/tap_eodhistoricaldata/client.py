"""REST client handling, including eodhistoricaldataStream base class."""
import os
from pathlib import Path
from typing import Any, Dict, Optional

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
