"""REST client handling, including coingeckoStream base class."""
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Iterable

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


class CoingeckoStream(RESTStream):
    """coingecko stream class."""

    url_base = "https://api.coingecko.com/api"

    def get_next_page_token(
            self, response: requests.Response, previous_token: Optional[Any]
    ) -> Optional[Any]:
        return None

    def get_records(self, context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        try:
            yield from super().get_records(context)
        except Exception as e:
            self.logger.error('Error while requesting %s for coin %s: %s' % (self.name, context['id'], str(e)))
            pass

    def validate_response(self, response: requests.Response) -> None:
        if response.status_code == 429:
            msg = (
                f"{response.status_code} Client Error: "
                f"{response.reason} for path: {self.path}"
            )
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

