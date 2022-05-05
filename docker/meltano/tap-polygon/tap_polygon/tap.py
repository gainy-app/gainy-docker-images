"""polygon tap class."""
from typing import List, Tuple

from singer_sdk import Tap, Stream
from singer_sdk import typing as th  # JSON schema typing helpers
from singer_sdk.exceptions import ConfigValidationError

from tap_polygon.streams import MarketStatusUpcoming, OptionsHistoricalPrices

STREAM_TYPES = [
    MarketStatusUpcoming,
    OptionsHistoricalPrices,
]


class Tappolygon(Tap):
    """polygon tap class."""
    name = "tap-polygon"

    config_jsonschema = th.PropertiesList(
        th.Property("api_key", th.StringType, required=True),
        th.Property("option_contract_names",
                    th.StringType,
                    required=False,
                    description="Option contracts to load (comma separated)"),
        th.Property("split_id",
                    th.StringType,
                    required=False,
                    description="Tap split index"),
        th.Property("split_num",
                    th.StringType,
                    required=False,
                    description="Total number of tap splits")).to_dict()

    parse_env_config = True

    def discover_streams(self) -> List[Stream]:
        # """Return a list of discovered streams."""
        return [stream_class(tap=self) for stream_class in STREAM_TYPES]
