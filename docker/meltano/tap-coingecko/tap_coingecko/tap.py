"""coingecko tap class."""
from typing import List, Tuple

from singer_sdk import Tap, Stream
from singer_sdk import typing as th  # JSON schema typing helpers
from singer_sdk.exceptions import ConfigValidationError

from tap_coingecko.streams import CoinData

STREAM_TYPES = [
    CoinData,
]


class Tapcoingecko(Tap):
    """coingecko tap class."""
    name = "tap-coingecko"

    config_jsonschema = th.PropertiesList(
        th.Property("coins", th.ArrayType(th.StringType), required=False),
        th.Property("coins_limit", th.IntegerType, required=False),
    ).to_dict()

    parse_env_config = True

    def discover_streams(self) -> List[Stream]:
        # """Return a list of discovered streams."""
        return [stream_class(tap=self) for stream_class in STREAM_TYPES]
