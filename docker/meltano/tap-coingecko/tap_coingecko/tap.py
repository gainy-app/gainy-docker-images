"""coingecko tap class."""
from typing import List, Tuple

from singer_sdk import Tap, Stream
from singer_sdk import typing as th  # JSON schema typing helpers
from singer_sdk.exceptions import ConfigValidationError

from tap_coingecko.streams import CoinData, CoinMarketRealtimeData

STREAM_TYPES = [
    CoinData,
    CoinMarketRealtimeData,
]


class Tapcoingecko(Tap):
    """coingecko tap class."""
    name = "tap-coingecko"

    config_jsonschema = th.PropertiesList(
        th.Property("api_key", th.StringType, required=False),
        th.Property("coins", th.ArrayType(th.StringType), required=False),
        th.Property("coins_limit", th.IntegerType, required=False),
        th.Property("split_id",
                    th.StringType,
                    required=False,
                    description="Tap split index"),
        th.Property("split_num",
                    th.StringType,
                    required=False,
                    description="Total number of tap splits"),
        th.Property("realtime",
                    th.BooleanType,
                    required=False,
                    description="Filter by `realtime` stream flag"),
    ).to_dict()

    parse_env_config = True

    def discover_streams(self) -> List[Stream]:
        streams = [stream_class(tap=self) for stream_class in STREAM_TYPES]

        realtime = self.config.get("realtime", False)
        streams = list(
            filter(lambda stream: stream.is_realtime == realtime, streams))

        return streams

    def _validate_config(
            self,
            raise_errors: bool = True,
            warnings_as_errors: bool = False) -> Tuple[List[str], List[str]]:
        warnings, errors = super()._validate_config(raise_errors,
                                                    warnings_as_errors)

        errors += self._check_both_or_nothing("split_id", "split_num",
                                              raise_errors)

        return warnings, errors

    def _check_both_or_nothing(self, property1: str, property2: str,
                               raise_errors: bool):
        if (property1 in self.config) == (property2 in self.config):
            return []

        error_msg = f"Both `{property1}` and `{property2}` should be specified or missed"
        if raise_errors:
            raise ConfigValidationError(error_msg)

        return error_msg
