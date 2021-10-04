"""REST client handling, including eodhistoricaldataStream base class."""

import requests
from pathlib import Path
from typing import Any, Dict, Optional

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
