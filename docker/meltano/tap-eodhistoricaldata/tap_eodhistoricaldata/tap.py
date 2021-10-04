"""eodhistoricaldata tap class."""

from typing import List

from singer_sdk import Tap, Stream
from singer_sdk import typing as th  # JSON schema typing helpers

from tap_eodhistoricaldata.streams import (
    Fundamentals,
    HistoricalDividends,
    HistoricalPrices,
    Options
)

STREAM_TYPES = [
    Fundamentals,
    HistoricalDividends,
    HistoricalPrices,
    Options
]

class Tapeodhistoricaldata(Tap):
    """eodhistoricaldata tap class."""
    name = "tap-eodhistoricaldata"

    config_jsonschema = th.PropertiesList(
        th.Property("api_token", th.StringType, required=True),
        th.Property("symbols", th.ArrayType(th.StringType), required=True),
        th.Property("start_symbol", th.StringType),
        th.Property("api_url", th.StringType, default="https://eodhistoricaldata.com/api/"),
    ).to_dict()

    def discover_streams(self) -> List[Stream]:
        """Return a list of discovered streams."""
        return [stream_class(tap=self) for stream_class in STREAM_TYPES]
