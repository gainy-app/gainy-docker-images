"""Stream type classes for tap-polygon."""
from abc import ABC, abstractmethod
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

from tap_polygon.client import PolygonStream

SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")


class AbstractPolygonStream(PolygonStream, ABC):
    selected_by_default = True
    STATE_MSG_FREQUENCY = 100

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


class MarketStatusUpcoming(AbstractPolygonStream):
    name = "polygon_marketstatus_upcoming"
    path = "/v1/marketstatus/upcoming"
    primary_keys = ["date", "exchange"]
    schema_filepath = SCHEMAS_DIR / "marketstatus_upcoming.json"

    def get_records(self, context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        if self.split_id:
            return []

        try:
            yield from super().get_records(context)
        except Exception as e:
            self.logger.error('Error while requesting %s: %s' %
                              (self.name, str(e)))
            pass


class StockSplitsUpcoming(AbstractPolygonStream):
    name = "polygon_stock_splits"
    path = "/v3/reference/splits"
    primary_keys = ["ticker", "execution_date"]
    schema_filepath = SCHEMAS_DIR / "stock_splits.json"

    def get_records(self, context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        if self.split_id:
            return []

        try:
            for i in super().get_records(context):
                yield from i.get('results', [])
        except Exception as e:
            self.logger.error('Error while requesting %s: %s' %
                              (self.name, str(e)))
            pass


class AbstractHistoricalPricesStream(AbstractPolygonStream, ABC):
    selected_by_default = True
    STATE_MSG_FREQUENCY = 100

    def get_url_params(self, context: Optional[dict],
                       next_page_token: Optional[Any]) -> Dict[str, Any]:
        params: dict = super().get_url_params(context, next_page_token)

        params['adjusted'] = 'true'
        params['sort'] = 'asc'
        params['limit'] = '50000'

        return params

    def request_records(self, context: Optional[dict]) -> Iterable[dict]:
        for record in super().request_records(context):
            yield from record.get('results', [])

    @abstractmethod
    def get_symbols(self) -> Iterable[str]:
        pass

    @cached_property
    def partitions(self) -> Iterable[Dict[str, Any]]:
        symbols_state = self.get_symbols_state()
        symbols = self.get_symbols()
        symbols = list(sorted(symbols))
        self.logger.info('Loading symbols %s' % (json.dumps(symbols)))
        for symbol in symbols:
            if symbol in symbols_state:
                yield symbols_state[symbol]['context']
            else:
                yield {"symbol": symbol}

    def get_symbols_state(self) -> Dict[str, str]:
        state_partitions = super().partitions or []
        symbols_state = {}
        for context in state_partitions:
            state = self.get_context_state(context)
            symbol = context['symbol']
            symbols_state[symbol] = state
        return symbols_state

    def fetch(self, url, params):
        res = requests.get(url=url, params=params)
        self._write_request_duration_log(url, res, None, None)
        return res.json()

    def load_first_record(self, context) -> Dict[str, Any]:
        url = self.get_url(context)
        params = self.get_url_params(context, None)
        data = self.fetch(url, params)
        if data and 'results' in data and data['results']:
            return data['results'][0]

    def get_records(self, context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        try:
            state = self.get_context_state(context)

            is_incremental = False
            symbol = context.get("contract_name") or context.get("symbol")
            if 'first_record' in state:
                first_record_context = {
                    **context,
                    **{
                        "date_from": state['first_record']['t'],
                        "date_to": state['first_record']['t'],
                    }
                }
                first_record = self.request_decorator(
                    self.load_first_record)(first_record_context)
                if first_record and first_record['t'] == state['first_record'][
                        't'] and abs(first_record['c'] -
                                     state['first_record']['c']) < 1e-6:
                    context['date_from'] = state['first_record']['date_to']
                    is_incremental = True

            if 'date_from' not in context:
                context['date_from'] = '1980-01-01'
            if 'date_to' not in context:
                context['date_to'] = datetime.now().strftime('%Y-%m-%d')

            self.logger.info('Symbol context %s %s' %
                             (symbol, json.dumps(context)))
            records = super().get_records(context)

            if is_incremental and 'first_record' in state:
                # if incremental update - update the date_to in the first_record
                state['first_record']['date_to'] = context['date_to']
            else:
                # if full update - extract first record, otherwise it's preserved
                for record in records:
                    yield record
                    state['first_record'] = record.copy()
                    break

            yield from records

            del context['date_from'], context['date_to']

        except Exception as e:
            symbol = context.get("contract_name") or context.get("symbol")
            self.logger.error('Error while requesting %s for contract %s: %s' %
                              (self.name, symbol, str(e)))


class StocksHistoricalPrices(AbstractHistoricalPricesStream):
    name = "polygon_stocks_historical_prices"
    path = "/v2/aggs/ticker/{symbol}/range/1/day/{date_from}/{date_to}"
    primary_keys = ["symbol", "t"]
    schema_filepath = SCHEMAS_DIR / "stocks_historical_prices.json"

    def get_symbols(self) -> Iterable[str]:
        stock_symbols = self.config.get("stock_symbols")
        if stock_symbols:
            for symbol in stock_symbols:
                if not symbol or not self.is_within_split(symbol):
                    continue
                yield symbol

            return

        exchanges = self.config.get("stock_exchanges")
        if not exchanges:
            return

        symbols = []
        for exchange in exchanges:
            next_url = None
            page = 0
            while page == 0 or next_url:
                page += 1
                if next_url:
                    url = next_url
                    params = {
                        "apiKey": self.config['api_key'],
                    }
                    next_url = None
                else:
                    url = self.url_base + "/v3/reference/tickers"
                    params = {
                        "exchange": exchange,
                        "active": "true",
                        "sort": "ticker",
                        "order": "asc",
                        "limit": 1000,
                        "apiKey": self.config['api_key'],
                    }

                data = self.request_decorator(self.fetch)(url, params)

                if not data or "status" not in data or data['status'] not in [
                        "OK", "DELAYED"
                ]:
                    raise Exception('Error while requesting %s' % (url))

                for record in data.get('results', []):
                    symbol = record['ticker']
                    if not symbol or not self.is_within_split(symbol):
                        continue
                    yield symbol

                next_url = data.get('next_url')
                if not next_url:
                    break


class OptionsHistoricalPrices(AbstractHistoricalPricesStream):
    name = "polygon_options_historical_prices"
    path = "/v2/aggs/ticker/O:{symbol}/range/1/day/{date_from}/{date_to}"
    primary_keys = ["contract_name", "t"]
    schema_filepath = SCHEMAS_DIR / "options_historical_prices.json"

    def get_symbols(self) -> Iterable[str]:
        option_contract_names = self.config.get("option_contract_names", [])
        for contract_name in option_contract_names:
            if not contract_name or not self.is_within_split(contract_name):
                continue

            yield contract_name

    def post_process(self, row: dict, context: Optional[dict] = None) -> dict:
        row['contract_name'] = context["symbol"]
        return super().post_process(row, context)


class CryptoHistoricalPrices(AbstractHistoricalPricesStream):
    name = "polygon_crypto_historical_prices"
    path = "/v2/aggs/ticker/X:{symbol}/range/1/day/{date_from}/{date_to}"
    primary_keys = ["symbol", "t"]
    schema_filepath = SCHEMAS_DIR / "crypto_historical_prices.json"

    def get_symbols(self) -> Iterable[str]:
        crypto_symbols = self.config.get("crypto_symbols")
        if crypto_symbols:
            for symbol in crypto_symbols:
                if not symbol or not self.is_within_split(symbol):
                    continue

                yield symbol
            return

        # 3. load all
        url = self.url_base + "/v2/snapshot/locale/global/markets/crypto/tickers"
        params = {
            "apiKey": self.config['api_key'],
        }
        data = self.request_decorator(self.fetch)(url, params)

        if not data or "status" not in data or data['status'] != "OK":
            self.logger.error('Error while requesting %s: %s' %
                              (url, json.dumps(data)))
        else:
            for record in data.get('tickers', []):
                symbol = re.sub(r'^X:', '', record['ticker'])
                if not symbol or not self.is_within_split(symbol):
                    continue

                yield symbol
