"""eodhistoricaldata tap class."""
from typing import List, Tuple

from singer_sdk import Tap, Stream
from singer_sdk.exceptions import ConfigValidationError
from singer_sdk import typing as th  # JSON schema typing helpers

from tap_eodhistoricaldata.streams import (
    Fundamentals,
    HistoricalDividends,
    HistoricalPrices,
    Options,
    IncrementalPrices
)

STREAM_TYPES = [
    Fundamentals,
    HistoricalDividends,
    Options,
    HistoricalPrices,
    IncrementalPrices
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
            "prices_stream",
            th.StringType,
            required=False,
            default="daily",
            description="Flag which specifies whether daily incremental or historical prices will be loaded"
        )
    ).to_dict()

    def discover_streams(self) -> List[Stream]:
        # """Return a list of discovered streams."""
        for stream_class in STREAM_TYPES:
            if self._is_stream_enabled(stream_class):
                self.logger.info("Enabling ")

        return [stream_class(tap=self) for stream_class in STREAM_TYPES if self._is_stream_enabled(stream_class)]

    def _is_stream_enabled(self, stream_class) -> bool:
        if stream_class != HistoricalPrices and stream_class != IncrementalPrices:
            return True

        is_daily_prices = "prices_stream" in self.config and "daily" == self.config["prices_stream"]
        return is_daily_prices == (stream_class == IncrementalPrices)

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
