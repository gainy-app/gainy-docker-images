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
        state_partitions = super().partitions or []
        state_symbols = {}
        for context in state_partitions:
            symbol = context["symbol"]
            if symbol in state_symbols:
                state_symbols[symbol] = min(context["date_to"],
                                            state_symbols[symbol])
            else:
                state_symbols[symbol] = context["date_to"]

        # 2. load from config
        stock_symbols = self.config.get("stock_symbols")
        if stock_symbols:
            stock_symbols = stock_symbols.split(",")
            for symbol in stock_symbols:
                symbol = symbol.strip()
                if not symbol or not self.is_within_split(symbol):
                    continue

                partition = {"symbol": symbol, **default_context}

                if symbol in state_symbols:
                    partition["date_from"] = state_symbols[symbol]

                yield partition

            return

        # 3. load all
        url = "/v2/snapshot/locale/us/markets/stocks/tickers"
        res = requests.get(url=self.url_base + url,
                           params={
                               "apiKey": self.config['api_key'],
                           })
        self._write_request_duration_log(url, res, None, None)
        data = res.json()

        if not data or "status" not in data or data['status'] not in [
                "OK", "DELAYED"
        ]:
            self.logger.error('Error while requesting %s' % (url))
        else:
            symbols = []
            for record in res.json().get('tickers', []):
                symbol = re.sub(r'^X:', '', record['ticker'])
                if not symbol or not self.is_within_split(symbol):
                    continue
                symbols.append(symbol)

            symbols = list(sorted(symbols))
            self.logger.info('Loading symbols %s' % (json.dumps(symbols)))
            for symbol in symbols:
                partition = {"symbol": symbol, **default_context}

                if symbol in state_symbols:
                    partition["date_from"] = state_symbols[symbol]

                yield partition


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
        state_partitions = super().partitions or []
        state_contract_names = set()
        for context in state_partitions:
            state_contract_names.add(context["contract_name"])
            yield {
                "contract_name": context["contract_name"],
                "date_from": context["date_to"],
                "date_to": default_context["date_to"],
            }

        # 2. load from config
        option_contract_names = self.config.get("option_contract_names",
                                                "").split(",")
        for contract_name in option_contract_names:
            contract_name = contract_name.strip()
            if not contract_name or contract_name in state_contract_names:
                continue
            if not self.is_within_split(contract_name):
                continue

            yield {"contract_name": contract_name, **default_context}


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
        state_partitions = super().partitions or []
        state_symbols = set()
        for context in state_partitions:
            state_symbols.add(context["symbol"])
            yield {
                "symbol": context["symbol"],
                "date_from": context["date_to"],
                "date_to": default_context["date_to"],
            }

        # 2. load from config
        crypto_symbols = self.config.get("crypto_symbols")
        if crypto_symbols:
            crypto_symbols = crypto_symbols.split(",")
            for symbol in crypto_symbols:
                symbol = symbol.strip()
                if not symbol or symbol in state_symbols:
                    continue
                if not self.is_within_split(symbol):
                    continue

                yield {"symbol": symbol, **default_context}
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
                if not symbol or symbol in state_symbols:
                    continue
                if not self.is_within_split(symbol):
                    continue

                yield {"symbol": symbol, **default_context}
