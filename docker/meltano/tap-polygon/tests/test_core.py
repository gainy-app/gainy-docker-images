"""Tests standard tap features using the built-in SDK tests library."""

import copy

import vcr
from vcr.record_mode import RecordMode
from freezegun import freeze_time
from singer_sdk.plugin_base import JSONSchemaValidator
from singer_sdk.testing import get_standard_tap_tests

from tap_polygon.tap import Tappolygon

RECORD_MODE = RecordMode.NONE
# RECORD_MODE = RecordMode.NEW_EPISODES
CONFIG = {
    "api_key": "fake_key",
    "option_contract_names": ["TSLA240621C01090000", "TSLA240621C00250000"],
    "crypto_symbols": ["BTCUSD"],
    "stock_symbols": ["AAPL"],
}
EXCHANGES_CONFIG = {
    "api_key": "fake_key",
    "stock_exchanges": ["XNAS"],
}

STATE = {
    "bookmarks": {
        "polygon_marketstatus_upcoming": {},
        "polygon_stock_splits": {},
        "polygon_options_historical_prices": {
            "partitions": [{
                "context": {
                    "contract_name": "TSLA240621C00250000",
                    "date_from": "1980-01-01",
                    "date_to": "2022-05-05"
                }
            }]
        },
        "polygon_crypto_historical_prices": {
            "partitions": [{
                "context": {
                    "symbol": "BTCUSD",
                    "date_from": "1980-01-01",
                    "date_to": "2022-05-05"
                }
            }]
        },
        "polygon_stocks_historical_prices": {
            "partitions": [{
                "context": {
                    "symbol": "AAPL",
                    "date_from": "1980-01-01",
                    "date_to": "2022-05-05"
                }
            }]
        },
    }
}


@freeze_time("2022-05-05")
@vcr.use_cassette("cassettes/tap/tap-core.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_standard_tap_tests():
    """Run standard tap tests from the SDK."""

    tests = get_standard_tap_tests(Tappolygon, config=CONFIG)

    for test in tests:
        test()


@freeze_time("2022-05-05")
@vcr.use_cassette("cassettes/tap/tap-core.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_tap_sync_all():
    tap = Tappolygon(config=CONFIG)
    tap.sync_all()


@freeze_time("2022-05-05")
@vcr.use_cassette("cassettes/tap/tap-core.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_tap_sync_exchanges():
    tap = Tappolygon(config=EXCHANGES_CONFIG)
    tap.sync_all()


@freeze_time("2022-05-05")
@vcr.use_cassette("cassettes/tap/tap-core.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_tap_with_state_sync_all():
    tap = Tappolygon(config=CONFIG, state=copy.deepcopy(STATE))
    tap.sync_all()


@freeze_time("2022-05-05")
@vcr.use_cassette("cassettes/tap/tap-core.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_validate_schema():
    _validate_schema({}, "marketstatus_upcoming.json",
                     "polygon_marketstatus_upcoming")
    _validate_schema({}, "stock_splits.json", "polygon_stock_splits")
    _validate_schema(
        STATE["bookmarks"]["polygon_options_historical_prices"]["partitions"]
        [0]["context"], "options_historical_prices.json",
        "polygon_options_historical_prices")
    _validate_schema(
        STATE["bookmarks"]["polygon_stocks_historical_prices"]["partitions"][0]
        ["context"], "stocks_historical_prices.json",
        "polygon_stocks_historical_prices")
    _validate_schema(
        STATE["bookmarks"]["polygon_crypto_historical_prices"]["partitions"][0]
        ["context"], "crypto_historical_prices.json",
        "polygon_crypto_historical_prices")


def _validate_schema(context, schema_file, stream_name):
    from pathlib import Path
    test_data_dir = Path(__file__).parent
    import json

    tap = Tappolygon(config=CONFIG)

    stream = tap.streams[stream_name]
    stream._write_starting_replication_value(context)
    records = list(stream.get_records(context))

    with open(test_data_dir /
              ("../tap_polygon/schemas/%s" % schema_file)) as f:
        schema = json.load(f)

        validator = JSONSchemaValidator(schema)
        validator.validate(records[0])
