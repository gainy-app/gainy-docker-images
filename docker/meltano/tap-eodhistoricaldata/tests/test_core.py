"""Tests standard tap features using the built-in SDK tests library."""

import copy
import re
import vcr
from vcr.record_mode import RecordMode
from freezegun import freeze_time
from singer_sdk.plugin_base import JSONSchemaValidator
from singer_sdk.testing import get_standard_tap_tests
from tap_eodhistoricaldata.tap import Tapeodhistoricaldata

# RECORD_MODE = RecordMode.NEW_EPISODES
RECORD_MODE = RecordMode.NONE
EXCHANGES_CONFIG = {
    "api_token": "fake_token",
    "exchanges": ["NASDAQ", "NYSE", "INDX", "CC"],
    "exchange_symbols_limit": 1
}

EXCHANGES_STATE = {
    "bookmarks": {
        "eod_historical_prices": {
            "partitions": [{
                "context": {
                    "symbol": "AAPL"
                },
                "replication_key": "date",
                "replication_key_value": "2021-11-28"
            }]
        },
        "eod_dividends": {
            "partitions": [{
                "context": {
                    "Code": "AAPL",
                    "Type": "Common Stock",
                    "Exchange": "NASDAQ"
                },
                "replication_key": "date",
                "replication_key_value": "2021-01-01"
            }]
        }
    }
}

SYMBOLS_CONFIG = {
    "api_token": "fake_token",
    "symbols":
    ["AAPL", "GOOGL", "TSLA", "IBM", "F", "000906.INDX", "$ANRX.CC"]
}


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_standard_tap_tests():
    """Run standard tap tests from the SDK."""

    tests = get_standard_tap_tests(Tapeodhistoricaldata,
                                   config=EXCHANGES_CONFIG)

    for test in tests:
        test()


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_tap_sync_all():
    tap = Tapeodhistoricaldata(config=EXCHANGES_CONFIG)
    tap.sync_all()


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-state-sync.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_tap_with_state_sync_all():
    tap = Tapeodhistoricaldata(config=EXCHANGES_CONFIG,
                               state=copy.deepcopy(EXCHANGES_STATE))
    tap.sync_all()


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-state-sync.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_tap_prices_with_state():
    tap = Tapeodhistoricaldata(config=EXCHANGES_CONFIG,
                               state=copy.deepcopy(EXCHANGES_STATE))

    prices_stream = tap.streams["eod_historical_prices"]
    price_stream_partitions = prices_stream.partitions

    symbols = set([i['symbol'] for i in price_stream_partitions])
    assert '$ANRX-USD.CC' in symbols
    assert '000906.INDX' in symbols
    assert 'AAPL' in symbols

    for partition in price_stream_partitions:
        prices_stream._write_starting_replication_value(partition)

        replication_key_value = prices_stream.get_starting_replication_key_value(
            partition)
        if partition['symbol'] == 'AAPL':
            assert "2021-11-28" == replication_key_value
        else:
            assert replication_key_value is None

        # Check that historical prices for NYSE are loaded for a couple of days since previous replication
        records = list(prices_stream.get_records(partition))
        nyse_avg_days = len(records)
        if partition['symbol'] == 'AAPL':
            assert len(records) <= 6
        else:
            assert len(records) > 6


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-state-sync.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_tap_dividends_with_state():
    tap = Tapeodhistoricaldata(config=EXCHANGES_CONFIG, state=EXCHANGES_STATE)
    tap._reset_state_progress_markers()

    div_stream = tap.streams["eod_dividends"]
    div_stream_partitions = div_stream.partitions
    assert 2 == len(div_stream_partitions)

    apple_partition = div_stream_partitions[0]
    assert "AAPL" == apple_partition["Code"]

    div_stream._write_starting_replication_value(apple_partition)

    apple_replication_key_value = div_stream.get_starting_replication_key_value(
        apple_partition)
    assert "2021-01-01" == apple_replication_key_value


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-state-sync.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_tap_splits():
    config1 = copy.deepcopy(EXCHANGES_CONFIG)
    config1["split_id"] = "0"
    config1["split_num"] = "2"
    tap1 = Tapeodhistoricaldata(config=config1)

    config2 = copy.deepcopy(EXCHANGES_CONFIG)
    config2["split_id"] = "1"
    config2["split_num"] = "2"
    tap2 = Tapeodhistoricaldata(config=config2)

    config3 = copy.deepcopy(EXCHANGES_CONFIG)
    tap3 = Tapeodhistoricaldata(config=config3)

    assert len(tap1.streams["eod_fundamentals"].partitions) + len(tap2.streams["eod_fundamentals"].partitions) \
           == len(tap3.streams["eod_fundamentals"].partitions)


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_tap_symbols_config():
    tap = Tapeodhistoricaldata(config=SYMBOLS_CONFIG)

    assert 7 == len(tap.streams["eod_historical_prices"].partitions)
    assert 7 == len(tap.streams["eod_fundamentals"].partitions)

    tap.sync_all()


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_tap_prices_with_symbols_config():
    tap = Tapeodhistoricaldata(config=SYMBOLS_CONFIG)

    prices_stream = tap.streams["eod_historical_prices"]
    for context in prices_stream.partitions:
        records = prices_stream.get_records(context)
        for record in records:
            assert record["Code"] in SYMBOLS_CONFIG['symbols']


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
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

    with open(test_data_dir /
              ("../tap_eodhistoricaldata/schemas/%s" % schema_file)) as f:
        schema = json.load(f)

        validator = JSONSchemaValidator(schema)
        validator.validate(records[0])
