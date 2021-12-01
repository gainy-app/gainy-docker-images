"""Tests standard tap features using the built-in SDK tests library."""

import copy

import vcr
from freezegun import freeze_time
from singer_sdk.plugin_base import JSONSchemaValidator
from singer_sdk.testing import get_standard_tap_tests

from tap_eodhistoricaldata.tap import Tapeodhistoricaldata

EXCHANGES_CONFIG = {
    "api_token": "fake_token",
    "exchanges": ["NASDAQ", "NYSE"]
}

EXCHANGES_STATE = {"bookmarks": {
    "eod_historical_prices": {"partitions": [
        {"context": {"exchange": "NYSE"}, "replication_key": "date", "replication_key_value": "2021-11-28"}
    ]},
    "eod_dividends": {"partitions": [
        {"context": {"Code": "AAPL"}, "replication_key": "date", "replication_key_value": "2021-01-01"}
    ]}
}}

SYMBOLS_CONFIG = {
    "api_token": "fake_token",
    "symbols": ["AAPL", "GOOGL", "TSLA", "IBM", "F"]
}


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml")
def test_standard_tap_tests():
    """Run standard tap tests from the SDK."""

    tests = get_standard_tap_tests(
        Tapeodhistoricaldata,
        config=EXCHANGES_CONFIG
    )

    for test in tests:
        test()


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml")
def test_tap_sync_all():
    tap = Tapeodhistoricaldata(config=EXCHANGES_CONFIG)
    tap.sync_all()


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-state-sync.yaml")
def test_tap_with_state_sync_all():
    tap = Tapeodhistoricaldata(config=EXCHANGES_CONFIG, state=copy.deepcopy(EXCHANGES_STATE))
    tap.sync_all()


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-state-sync.yaml")
def test_tap_prices_with_state():
    tap = Tapeodhistoricaldata(config=EXCHANGES_CONFIG, state=copy.deepcopy(EXCHANGES_STATE))

    prices_stream = tap.streams["eod_historical_prices"]
    price_stream_partitions = prices_stream.partitions
    assert len(price_stream_partitions) == 2

    nasdaq_partition = price_stream_partitions[0]
    assert "NASDAQ" == nasdaq_partition["exchange"]
    nyse_partition = price_stream_partitions[1]
    assert "NYSE" == nyse_partition["exchange"]

    prices_stream._write_starting_replication_value(nasdaq_partition)
    prices_stream._write_starting_replication_value(nyse_partition)

    nasdaq_replication_key_value = prices_stream.get_starting_replication_key_value(nasdaq_partition)
    assert nasdaq_replication_key_value is None
    nyse_replication_key_value = prices_stream.get_starting_replication_key_value(nyse_partition)
    assert "2021-11-28" == nyse_replication_key_value

    # Check that historical prices for NASDAQ are loaded for a couple of days since previous replication
    nyse_records = list(prices_stream.get_records(nyse_partition))
    nyse_tickers = set(map(lambda r: r["Code"], nyse_records))
    nyse_avg_days = len(nyse_records) / len(nyse_tickers)
    assert nyse_avg_days <= 4

    # Check that historical prices for NASDAQ are loaded for longer period
    nasdaq_records = list(prices_stream.get_records(nasdaq_partition))
    nasdaq_tickers = set(map(lambda r: r["Code"], nasdaq_records))
    nasdaq_avg_days = len(nasdaq_records) / len(nasdaq_tickers)
    assert nasdaq_avg_days > 5


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-state-sync.yaml")
def test_tap_dividends_with_state():
    tap = Tapeodhistoricaldata(config=EXCHANGES_CONFIG, state=EXCHANGES_STATE)
    tap._reset_state_progress_markers()

    div_stream = tap.streams["eod_dividends"]
    div_stream_partitions = div_stream.partitions
    assert 5 == len(div_stream_partitions)

    apple_partition = div_stream_partitions[0]
    assert "AAPL" == apple_partition["Code"]
    ford_partition = div_stream_partitions[1]
    assert "F" == ford_partition["Code"]

    div_stream._write_starting_replication_value(apple_partition)
    div_stream._write_starting_replication_value(ford_partition)

    apple_replication_key_value = div_stream.get_starting_replication_key_value(apple_partition)
    assert "2021-01-01" == apple_replication_key_value
    ford_replication_key_value = div_stream.get_starting_replication_key_value(ford_partition)
    assert ford_replication_key_value is None


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-state-sync.yaml")
def test_tap_splits():
    config1 = copy.deepcopy(EXCHANGES_CONFIG)
    config1["split-id"] = 0
    config1["split-num"] = 2
    tap1 = Tapeodhistoricaldata(config=config1)

    config2 = copy.deepcopy(EXCHANGES_CONFIG)
    config2["split-id"] = 1
    config2["split-num"] = 2
    tap2 = Tapeodhistoricaldata(config=config2)

    config3 = copy.deepcopy(EXCHANGES_CONFIG)
    tap3 = Tapeodhistoricaldata(config=config3)

    assert len(tap1.streams["eod_fundamentals"].partitions) + len(tap2.streams["eod_fundamentals"].partitions) \
           == len(tap3.streams["eod_fundamentals"].partitions)


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml")
def test_tap_symbols_config():
    tap = Tapeodhistoricaldata(config=SYMBOLS_CONFIG)

    assert 1 == len(tap.streams["eod_historical_prices"].partitions)
    assert "US" == tap.streams["eod_historical_prices"].partitions[0]["exchange"]

    assert 5 == len(tap.streams["eod_fundamentals"].partitions)

    tap.sync_all()


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml")
def test_validate_schema():
    _validate_schema({"exchange": "US"}, "eod.json", "eod_historical_prices")

    _validate_schema({"Code": "AAPL"}, "fundamentals.json", "eod_fundamentals")
    _validate_schema({"Code": "AAPL"}, "options.json", "eod_options")
    _validate_schema({"Code": "AAPL"}, "dividends.json", "eod_dividends")


def _validate_schema(context, schema_file, stream_name):
    from pathlib import Path
    test_data_dir = Path(__file__).parent
    import json

    tap = Tapeodhistoricaldata(config=SYMBOLS_CONFIG)

    stream = tap.streams[stream_name]
    stream._write_starting_replication_value(context)
    records = list(stream.get_records(context))

    with open(test_data_dir / ("../tap_eodhistoricaldata/schemas/%s" % schema_file)) as f:
        schema = json.load(f)

        validator = JSONSchemaValidator(schema)
        validator.validate(records[0])

