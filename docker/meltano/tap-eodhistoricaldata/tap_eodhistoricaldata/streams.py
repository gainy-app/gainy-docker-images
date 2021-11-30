"""Stream type classes for tap-eodhistoricaldata."""
import copy
import os
from abc import ABC
from datetime import datetime
from datetime import timedelta
from functools import cached_property
from pathlib import Path
from typing import Any, Dict, Optional, Iterable, List

import requests
import singer
from singer import RecordMessage
from singer_sdk.helpers._typing import conform_record_data_types
from singer_sdk.helpers._util import utc_now

from tap_eodhistoricaldata.client import eodhistoricaldataStream

SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")


class AbstractEODStream(eodhistoricaldataStream):

    @cached_property
    def partitions(self) -> List[dict]:
        if "symbols" in self.config:
            self.logger.info("Using symbols from the config parameter")
            symbols = self.config["symbols"]
        else:
            self.logger.info(f"Loading symbols for exchanges: {self.config['exchanges']}")
            exchange_url = f"{self.url_base}/exchange-symbol-list"
            symbols = []
            for exchange in self.config["exchanges"]:
                res = requests.get(
                    url=f"{exchange_url}/{exchange}",
                    params={"api_token": self.config["api_token"], "fmt": "json"}
                )
                self._write_request_duration_log("/exchange-symbol-list", res, None, None)

                exchange_symbols = list(map(lambda record: record["Code"], res.json()))
                symbols += exchange_symbols

        return list(map(lambda x: {'Code': x}, symbols))

    def post_process(self, row: dict, context: Optional[dict] = None) -> dict:
        row['Code'] = context['Code']

        def replace_na(row):
            for k, v in row.items():
                if v == 'NA' or v == '"NA"':
                    row[k] = {}
            return row

        return replace_na(row)

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

    def get_records(self, context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        try:
            yield from super().get_records(context)
        except Exception as e:
            self.logger.error('Error while requesting %s for symbol %s: %s' % (self.name, context['Code'], str(e)))
            pass


class Fundamentals(AbstractEODStream):
    name = "eod_fundamentals"
    path = "/fundamentals/{Code}"
    primary_keys = ["Code"]
    selected_by_default = True

    STATE_MSG_FREQUENCY = 100

    schema_filepath = SCHEMAS_DIR / "fundamentals.json"

    def get_url_params(self, context: Optional[dict], next_page_token: Optional[Any]) -> Dict[str, Any]:
        """Return a dictionary of values to be used in URL parameterization."""
        params = super().get_url_params(context, next_page_token)
        params["filter"] = "General,Earnings,Highlights,AnalystRatings,Technicals,Valuation,Financials,SplitsDividends,SharesStats"
        return params

    def post_process(self, row: dict, context: Optional[dict] = None) -> dict:
        if 'UpdatedAt' in row['General']:
            row['UpdatedAt'] = row['General']['UpdatedAt']
        else:
            row['UpdatedAt'] = {}

        return super().post_process(row, context)

class HistoricalDividends(AbstractEODStream):
    name = "eod_dividends"
    path = "/div/{Code}?fmt=json"
    primary_keys = ["Code", "date"]
    selected_by_default = True

    STATE_MSG_FREQUENCY = 1000

    replication_key = 'date'
    schema_filepath = SCHEMAS_DIR / "dividends.json"

    def get_url_params(self, context: Optional[dict], next_page_token: Optional[Any]) -> Dict[str, Any]:
        params = super().get_url_params(context, next_page_token)

        if self.get_starting_replication_key_value(context) is not None:
            params['from'] = self.get_starting_replication_key_value(context)
        return params

class HistoricalPrices(AbstractEODStream):
    name = "eod_historical_prices"
    path = "/eod/{Code}?fmt=json&period=d"
    primary_keys = ["Code", "date"]
    selected_by_default = True

    STATE_MSG_FREQUENCY = 1000

    replication_key = 'date'
    schema_filepath = SCHEMAS_DIR / "eod.json"

    def get_url_params(self, context: Optional[dict], next_page_token: Optional[Any]) -> Dict[str, Any]:
        params = super().get_url_params(context, next_page_token)

        if self.get_starting_replication_key_value(context) is not None:
            params['from'] = self.get_starting_replication_key_value(context)
        return params

class Options(AbstractEODStream):
    name = "eod_options"
    path = "/options/{Code}?fmt=json"
    primary_keys = ["Code", "expirationDate"]
    selected_by_default = True

    STATE_MSG_FREQUENCY = 1000

    schema_filepath = SCHEMAS_DIR / "options.json"

    def get_records(self, context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        for i in super().get_records(context):
            for j in i['data']:
                del j['options']
                yield j


# ############## BULK STREAMS ################

class AbstractBulkStream(eodhistoricaldataStream, ABC):

    @cached_property
    def partitions(self) -> List[Dict[str, Any]]:
        state_partitions = super().partitions

        partitions = []
        exchanges = self.config.get("exchanges", []) or ["US"]
        for exchange in exchanges:
            if state_partitions:
                filtered_partitions_for_exchange = [p for p in state_partitions if p["exchange"] == exchange]
                if filtered_partitions_for_exchange:
                    partitions.append(filtered_partitions_for_exchange[0])
                    continue

            partitions.append({"exchange": exchange})

        return partitions


class IncrementalPrices(AbstractBulkStream):
    name = "eod_prices_daily"
    schema_filepath = SCHEMAS_DIR / "eod.json"

    path = "/eod-bulk-last-day/{exchange}"

    primary_keys = ["Code", "date"]
    replication_key = "date"

    STATE_MSG_FREQUENCY = 1000

    def get_url_params(self, context: Optional[dict], next_page_token: Optional[Any]) -> Dict[str, Any]:
        params = super().get_url_params(context, next_page_token)

        params["date"] = context["date"]
        params["api_token"] = self.config["api_token"]
        params["fmt"] = "json"

        if "symbols" in self.config:
            params["symbols"] = ",".join(self.config["symbols"])

        return params

    def get_records(self, context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        for date in self.loading_dates(context):
            context["date"] = date
            yield from super().get_records(context)
            del context["date"]

    def loading_dates(self, context: Optional[dict]) -> List[str]:
        to_date = datetime.now()

        if self.get_starting_replication_key_value(context) is not None:
            from_date = datetime.strptime(self.get_starting_replication_key_value(context), "%Y-%m-%d")
            delta_days = to_date - from_date
        else:
            self.logger.info("Replication key is not found in state, processing the last 3 days")
            delta_days = timedelta(days=3)

        self.logger.info(f"Loading data from {to_date - delta_days} to {to_date}")
        return [
            datetime.strftime(to_date - timedelta(days=i), "%Y-%m-%d")
            for i in reversed(range(delta_days.days + 1))
        ]


class IncrementalFundamentals(AbstractBulkStream):
    """
    Incremental Fundamentals stream is based on Fundamentals Bulk API, which doesn't currently include
    all needed data comparing to the full Fundamentals API. For example, `AnalystRatings` is not
    provided as a part of the bulk version of API.


    This is a significant limitation, therefore, this stream is disable for now.
    """

    name = "fundamentals_daily"
    schema_filepath = SCHEMAS_DIR / "fundamentals.json"

    path = "/bulk-fundamentals/{exchange}"
    page_size = 1000

    primary_keys = ["Code", "Year"]

    STATE_MSG_FREQUENCY = 1000

    def get_url_params(self, context: Optional[dict], next_page_token: Optional[Any]) -> Dict[str, Any]:
        params = super().get_url_params(context, next_page_token)

        params["api_token"] = self.config["api_token"]
        params["fmt"] = "json"

        offset = 0 if not next_page_token else next_page_token
        limit = self.page_size

        if "symbols" in self.config:
            params["symbols"] = ",".join(self.config["symbols"][offset:(offset + limit)])
        else:
            params["offset"] = offset
            params["limit"] = limit

        return params

    def get_records(self, context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        response = list(self.request_records(context))
        for record in response[0].values():
            yield self.post_process(record, context)

    def get_next_page_token(self, response: requests.Response, previous_token: Optional[Any]) -> Any:
        response_length = len(response.json())
        if response_length < self.page_size:
            return None

        if not previous_token:
            # No previous token means that only the first page was loaded
            return response_length

        return previous_token + response_length

    def post_process(self, row: dict, context: Optional[dict] = None) -> Optional[dict]:
        row["UpdatedAt"] = row["General"]["UpdatedAt"]

        update_at = datetime.strptime(row["General"]["UpdatedAt"], "%Y-%m-%d")
        row["Year"] = update_at.year

        row["Code"] = row["General"]["Code"]

        return super().post_process(row, context)
