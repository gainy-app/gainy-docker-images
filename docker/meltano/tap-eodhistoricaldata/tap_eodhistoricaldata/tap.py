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
        )
    ).to_dict()

    def discover_streams(self) -> List[Stream]:
        # """Return a list of discovered streams."""
        return [stream_class(tap=self) for stream_class in STREAM_TYPES]

    def _validate_config(
            self, raise_errors: bool = True, warnings_as_errors: bool = False
    ) -> Tuple[List[str], List[str]]:
        warnings, errors = super()._validate_config(raise_errors, warnings_as_errors)

        if ("symbols" in self.config) == ("exchanges" in self.config):
            error_msg = "Either `exchanges` or `symbols` property should be specified"
            if raise_errors:
                raise ConfigValidationError(error_msg)
            else:
                errors.append(error_msg)

        return warnings, errors
