"""Stream type classes for tap-polygon."""
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

from tap_polygon.client import PolygonStream

SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")


class AbstractPolygonStream(PolygonStream):
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


class AbstractHistoricalPricesStream(AbstractPolygonStream):
    selected_by_default = True
    STATE_MSG_FREQUENCY = 100

    def get_url_params(self, context: Optional[dict],
                       next_page_token: Optional[Any]) -> Dict[str, Any]:
        params: dict = super().get_url_params(context, next_page_token)

        params['adjusted'] = 'true'
        params['sort'] = 'asc'
        params['limit'] = '50000'

        return params

    def get_records(self, context: Optional[dict]) -> Iterable[Dict[str, Any]]:
        try:
            for i in super().get_records(context):
                yield from i.get('results', [])
        except Exception as e:
            symbol = context.get("contract_name") or context.get("symbol")
            self.logger.error('Error while requesting %s for contract %s: %s' %
                              (self.name, symbol, str(e)))
            pass

    def get_state_symbols(self, field_name) -> Dict[str, str]:
        state_partitions = super().partitions or []
        state_symbols = {}
        for context in state_partitions:
            symbol = context[field_name]
            if symbol in state_symbols:
                state_symbols[symbol] = min(context["date_to"],
                                            state_symbols[symbol])
            else:
                state_symbols[symbol] = context["date_to"]
        return state_symbols

    def get_partition(self,
                      field_name: str,
                      symbol: str,
                      default_context: dict,
                      state_symbols: Dict[str, str],
                      partial_update: bool = True):
        partition = {field_name: symbol, **default_context}

        if partial_update and symbol in state_symbols:
            partition["date_from"] = state_symbols[symbol]

        return partition


class StocksHistoricalPrices(AbstractHistoricalPricesStream):
    name = "polygon_stocks_historical_prices"
    path = "/v2/aggs/ticker/{symbol}/range/1/day/{date_from}/{date_to}"
    primary_keys = ["symbol", "t"]
    schema_filepath = SCHEMAS_DIR / "stocks_historical_prices.json"

    @cached_property
    def partitions(self) -> List[Dict[str, Any]]:
        default_context = {
            'date_from': '1980-01-01',
            'date_to': datetime.now().strftime('%Y-%m-%d')
        }

        # 1. load from state
        state_symbols = self.get_state_symbols("symbol")

        # 2. load from config
        stock_symbols = self.config.get("stock_symbols")
        if stock_symbols:
            for symbol in stock_symbols:
                if not symbol or not self.is_within_split(symbol):
                    continue

                yield self.get_partition("symbol", symbol, default_context,
                                         state_symbols, False)

            return

        exchanges = self.config.get("stock_exchanges")
        symbols = []
        url = "/v3/reference/tickers"
        for exchange in exchanges:
            next_url = None
            page = 0
            while page == 0 or next_url:
                page += 1
                if next_url:
                    res = requests.get(url=next_url,
                                       params={
                                           "apiKey": self.config['api_key'],
                                       })
                    next_url = None
                else:
                    res = requests.get(url=self.url_base + url,
                                       params={
                                           "exchange": exchange,
                                           "active": "true",
                                           "sort": "ticker",
                                           "order": "asc",
                                           "limit": 1000,
                                           "apiKey": self.config['api_key'],
                                       })
                self._write_request_duration_log(url, res, None, None)
                data = res.json()

                if not data or "status" not in data or data['status'] not in [
                        "OK", "DELAYED"
                ]:
                    raise Exception('Error while requesting %s' % (url))

                for record in data.get('results', []):
                    symbol = record['ticker']
                    if not symbol or not self.is_within_split(symbol):
                        continue
                    symbols.append(symbol)

                next_url = data.get('next_url')
                if not next_url:
                    break

        symbols = list(sorted(symbols))
        self.logger.info('Loading symbols %s' % (json.dumps(symbols)))
        for symbol in symbols:
            yield self.get_partition("symbol", symbol, default_context,
                                     state_symbols, False)


class OptionsHistoricalPrices(AbstractHistoricalPricesStream):
    name = "polygon_options_historical_prices"
    path = "/v2/aggs/ticker/O:{contract_name}/range/1/day/{date_from}/{date_to}"
    primary_keys = ["contract_name", "t"]
    schema_filepath = SCHEMAS_DIR / "options_historical_prices.json"

    @cached_property
    def partitions(self) -> List[Dict[str, Any]]:
        default_context = {
            'date_from': '1980-01-01',
            'date_to': datetime.now().strftime('%Y-%m-%d')
        }

        # 1. load from state
        state_symbols = self.get_state_symbols("contract_name")

        # 2. load from config
        option_contract_names = self.config.get("option_contract_names", [])
        for contract_name in option_contract_names:
            if not contract_name or not self.is_within_split(contract_name):
                continue

            yield self.get_partition("contract_name", contract_name,
                                     default_context, state_symbols, False)


class CryptoHistoricalPrices(AbstractHistoricalPricesStream):
    name = "polygon_crypto_historical_prices"
    path = "/v2/aggs/ticker/X:{symbol}/range/1/day/{date_from}/{date_to}"
    primary_keys = ["symbol", "t"]
    schema_filepath = SCHEMAS_DIR / "crypto_historical_prices.json"

    @cached_property
    def partitions(self) -> List[Dict[str, Any]]:
        default_context = {
            'date_from': '2009-01-01',
            'date_to': datetime.now().strftime('%Y-%m-%d')
        }

        # 1. load from state
        state_symbols = self.get_state_symbols("symbol")

        # 2. load from config
        crypto_symbols = self.config.get("crypto_symbols")
        if crypto_symbols:
            for symbol in crypto_symbols:
                if not symbol or not self.is_within_split(symbol):
                    continue

                yield self.get_partition("symbol", symbol, default_context,
                                         state_symbols)
            return

        # 3. load all
        url = "/v2/snapshot/locale/global/markets/crypto/tickers"
        res = requests.get(url=self.url_base + url,
                           params={
                               "apiKey": self.config['api_key'],
                           })
        self._write_request_duration_log(url, res, None, None)
        data = res.json()

        if not data or "status" not in data or data['status'] != "OK":
            self.logger.error('Error while requesting %s: %s' %
                              (url, json.dumps(data)))
        else:
            for record in res.json().get('tickers', []):
                symbol = re.sub(r'^X:', '', record['ticker'])
                if not symbol or not self.is_within_split(symbol):
                    continue

                yield self.get_partition("symbol", symbol, default_context,
                                         state_symbols)
