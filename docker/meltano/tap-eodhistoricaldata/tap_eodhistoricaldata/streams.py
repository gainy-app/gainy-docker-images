"""Stream type classes for tap-eodhistoricaldata."""
from abc import ABC
from datetime import datetime, timedelta
from functools import cached_property, reduce
from pathlib import Path
from typing import Any, Dict, Optional, Iterable, List

import json
import re
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
        return self.load_symbols()

    def post_process(self, row: dict, context: Optional[dict] = None) -> dict:
        symbol = context['Code']
        symbol = symbol.replace('-USD.CC', '.CC')
        row['Code'] = symbol

        return super().post_process(row, context)

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
        if context is None:
            return

        try:
            yield from super().get_records(context)
        except Exception as e:
            self.logger.error('Error while requesting %s for symbol %s: %s' %
                              (self.name, context['Code'], str(e)))
            pass


class Fundamentals(AbstractEODStream):
    name = "eod_fundamentals"
    path = "/fundamentals/{Code}"
    primary_keys = ["Code"]
    selected_by_default = True

    STATE_MSG_FREQUENCY = 100

    schema_filepath = SCHEMAS_DIR / "fundamentals.json"

    def get_url_params(self, context: Optional[dict],
                       next_page_token: Optional[Any]) -> Dict[str, Any]:
        """Return a dictionary of values to be used in URL parameterization."""
        params = super().get_url_params(context, next_page_token)
        params[
            "filter"] = "General,Earnings,Highlights,AnalystRatings,Technicals,Valuation,Financials,SplitsDividends,SharesStats,ETF_Data,MutualFund_Data,Components"
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

    @cached_property
    def partitions(self) -> List[dict]:
        allowed_types = [
            'fund', 'etf', 'mutual fund', 'preferred stock', 'common stock'
        ]
        records = list(
            filter(
                lambda record: (record['Type'] or "").lower() in allowed_types,
                super().partitions))

        return records

    def get_url_params(self, context: Optional[dict],
                       next_page_token: Optional[Any]) -> Dict[str, Any]:
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

    @cached_property
    def partitions(self) -> List[dict]:
        allowed_types = [
            'fund', 'etf', 'mutual fund', 'preferred stock', 'common stock'
        ]
        records = list(
            filter(
                lambda record: (record['Type'] or "").lower() in allowed_types,
                super().partitions))

        return records

    def get_records(self, context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        for i in super().get_records(context):
            for j in i['data']:
                yield j


# ############## EXCHANGE STREAMS ################


class AbstractExchangeStream(eodhistoricaldataStream, ABC):

    @cached_property
    def partitions(self) -> List[Dict[str, Any]]:
        state_partitions = super().partitions

        partitions = []
        exchanges = self.config.get("exchanges", []) or ["US"]
        for exchange in exchanges:
            exchange_partitions = [
                p for p in state_partitions or []
                if p.get("exchange", None) == exchange
            ]
            if exchange_partitions:
                partitions.append(exchange_partitions[0])
            else:
                partitions.append({"exchange": exchange})

        return partitions


class EODPrices(AbstractExchangeStream):
    name = "eod_historical_prices"
    schema_filepath = SCHEMAS_DIR / "eod.json"

    path = "/{api}/{object}"
    # bulk api = "/eod-bulk-last-day/{exchange}"
    # historical api = "/eod/{Code}"

    primary_keys = ["Code", "date"]
    replication_key = "date"

    STATE_MSG_FREQUENCY = 1000

    def get_url_params(self, context: Optional[dict],
                       next_page_token: Optional[Any]) -> Dict[str, Any]:
        params = super().get_url_params(context, next_page_token)

        params["fmt"] = "json"
        params["api_token"] = self.config["api_token"]

        if context["api"] == "eod":
            params["period"] = "d"
        else:
            params["date"] = context["date"]

            if "symbols" in self.config:
                params["symbols"] = ",".join(self.config["symbols"])

        return params

    def is_initial_load(self, context: dict) -> bool:
        return self.get_starting_replication_key_value(context) is None

    def get_records_all(self, symbols: Iterable[str],
                        context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        context["api"] = "eod"

        for symbol in symbols:
            if not symbol:
                continue
            try:
                context["object"] = symbol
                yield from super().get_records(context)
            except requests.exceptions.RequestException as e:
                self.logger.exception(e)

    def get_records_partial(
            self, context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        context["api"] = "eod-bulk-last-day"
        context["object"] = context['exchange']

        from_date = datetime.strptime(
            self.get_starting_replication_key_value(context), "%Y-%m-%d")
        for date in self.loading_dates(from_date):
            context["date"] = date
            yield from super().get_records(context)
        del context["date"]

    def get_records(self, context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        if not self.is_initial_load(context) and self.split_id() > 0:
            self.logger.info(
                f"Skipping bulk load for split: `{self.split_id()}`")
            return []

        if self.is_initial_load(context):
            self.logger.info(
                f"Loading prices using historical EOD API for exchange: {context['exchange']}"
            )
            symbols = [
                record['Code']
                for record in self.load_symbols(exchange=context["exchange"])
            ]
            yield from self.get_records_all(symbols, context)
        else:
            self.logger.info(
                f"Loading prices using bulk daily EOD API for exchange: {context['exchange']}"
            )
            yield from self.get_records_partial(context)

            # load all prices for recently split symbols
            from_date = datetime.strptime(
                self.get_starting_replication_key_value(context), "%Y-%m-%d")
            dates = self.loading_dates(from_date - timedelta(days=7))
            full_refresh_symbols = self.load_split_symbols(
                exchange=context["exchange"], dates=dates)
            self.logger.info(
                f"Loading all prices for recently split symbols: {json.dumps(full_refresh_symbols)}"
            )
            yield from self.get_records_all(full_refresh_symbols, context)

            # load all prices for full_refresh_symbols
            full_refresh_symbols = self.config.get("full_refresh_symbols")
            if full_refresh_symbols:
                full_refresh_symbols = full_refresh_symbols.split(",")
                self.logger.info(
                    f"Loading all prices (config): {json.dumps(full_refresh_symbols)}"
                )
                yield from self.get_records_all(full_refresh_symbols, context)

        del context["api"], context["object"]

    def loading_dates(self, from_date) -> List[str]:
        to_date = datetime.now()
        delta_days = to_date - from_date

        self.logger.info(
            f"Loading daily data from {to_date - delta_days} to {to_date}")
        return [
            datetime.strftime(to_date - timedelta(days=i), "%Y-%m-%d")
            for i in reversed(range(delta_days.days + 1))
        ]

    def post_process(self, row: dict, context: Optional[dict] = None) -> dict:
        if context["api"] == "eod":
            symbol = context["object"]
        else:
            symbol = row["code"]

        symbol = symbol.replace('-USD.CC', '.CC')
        exchange_name = context.get("exchange") or row.get(
            'exchange_short_name')
        if exchange_name == 'CC':
            symbol = re.sub(r'-USD$', '.CC', symbol)

        if exchange_name == 'INDX' and re.search(r'\.INDX$', symbol) is None:
            symbol += '.INDX'

        row['Code'] = symbol

        row = super().post_process(row, context)

        if row['date'] is None:
            return None

        self.logger.debug(f"Loading row {json.dumps(row)}")
        return row


class DailyFundamentals(AbstractExchangeStream):
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

    def get_url_params(self, context: Optional[dict],
                       next_page_token: Optional[Any]) -> Dict[str, Any]:
        params = super().get_url_params(context, next_page_token)

        params["api_token"] = self.config["api_token"]
        params["fmt"] = "json"

        offset = 0 if not next_page_token else next_page_token
        limit = self.page_size

        if "symbols" in self.config:
            params["symbols"] = ",".join(
                self.config["symbols"][offset:(offset + limit)])
        else:
            params["offset"] = offset
            params["limit"] = limit

        return params

    def get_records(self, context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        response = list(self.request_records(context))
        for record in response[0].values():
            yield self.post_process(record, context)

    def get_next_page_token(self, response: requests.Response,
                            previous_token: Optional[Any]) -> Any:
        response_length = len(response.json())
        if response_length < self.page_size:
            return None

        if not previous_token:
            # No previous token means that only the first page was loaded
            return response_length

        return previous_token + response_length

    def post_process(self,
                     row: dict,
                     context: Optional[dict] = None) -> Optional[dict]:
        row["UpdatedAt"] = row["General"]["UpdatedAt"]

        update_at = datetime.strptime(row["General"]["UpdatedAt"], "%Y-%m-%d")
        row["Year"] = update_at.year

        row["Code"] = row["General"]["Code"]

        return super().post_process(row, context)
