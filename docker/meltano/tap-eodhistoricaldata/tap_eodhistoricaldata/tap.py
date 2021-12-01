"""eodhistoricaldata tap class."""
from typing import List, Tuple

from singer_sdk import Tap, Stream
from singer_sdk import typing as th  # JSON schema typing helpers
from singer_sdk.exceptions import ConfigValidationError

from tap_eodhistoricaldata.streams import (
    EODPrices, Fundamentals, HistoricalDividends, Options
)

STREAM_TYPES = [
    Fundamentals,
    HistoricalDividends,
    Options,
    EODPrices
]


class Tapeodhistoricaldata(Tap):
    """eodhistoricaldata tap class."""
    name = "tap-eodhistoricaldata"

    config_jsonschema = th.PropertiesList(
        th.Property("api_token", th.StringType, required=True),
        th.Property(
            "symbols",
            th.ArrayType(th.StringType),
            required=False,
            description="List of ticker symbols to load"
        ),
        th.Property(
            "exchanges",
            th.ArrayType(th.StringType),
            required=False,
            description="List of exchanges to load ticker symbols from"
        ),
        th.Property(
            "split-id",
            th.IntegerType,
            required=False,
            description="Tap split index"
        ),
        th.Property(
            "split-num",
            th.IntegerType,
            required=False,
            description="Total number of tap splits"
        )
    ).to_dict()

    parse_env_config = True

    def discover_streams(self) -> List[Stream]:
        # """Return a list of discovered streams."""
        return [stream_class(tap=self) for stream_class in STREAM_TYPES]

    def _validate_config(
            self, raise_errors: bool = True, warnings_as_errors: bool = False
    ) -> Tuple[List[str], List[str]]:
        warnings, errors = super()._validate_config(raise_errors, warnings_as_errors)

        errors += self._check_exactly_one("exchanges", "symbols", raise_errors)
        errors += self._check_both_or_nothing("split-id", "split-num", raise_errors)

        return warnings, errors

    def _check_exactly_one(self, property1: str, property2: str, raise_errors: bool):
        if (property1 in self.config) != (property2 in self.config):
            return []

        error_msg = f"Either `{property1}` or `{property2}` should be specified"
        if raise_errors:
            raise ConfigValidationError(error_msg)

        return error_msg

    def _check_both_or_nothing(self, property1: str, property2: str, raise_errors: bool):
        if (property1 in self.config) == (property2 in self.config):
            return []

        error_msg = f"Both `{property1}` and `{property2}` should be specified or missed"
        if raise_errors:
            raise ConfigValidationError(error_msg)

        return error_msg
