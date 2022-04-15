"""Tests standard tap features using the built-in SDK tests library."""

import copy

import vcr
from vcr.record_mode import RecordMode
from freezegun import freeze_time
from singer_sdk.plugin_base import JSONSchemaValidator
from singer_sdk.testing import get_standard_tap_tests

from tap_coingecko.tap import Tapcoingecko

RECORD_MODE = RecordMode.NEW_EPISODES
CONFIG = {}
CONFIG_REALTIME = {"realtime": True}
CONFIG_WITH_KEY = {"api_key": "foo"}
CONTEXT = {"id": "bitcoin"}
CONTEXT_REALTIME = {"ids": "bitcoin"}
STATE = {"coingecko_coin": {"partitions": [{"context": CONTEXT}]}}


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_standard_tap_tests():
    """Run standard tap tests from the SDK."""

    tests = get_standard_tap_tests(Tapcoingecko, config=CONFIG)

    for test in tests:
        test()


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_tap_sync_all():
    tap = Tapcoingecko(config=CONFIG)
    tap.sync_all()


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_tap_api_key():
    tap = Tapcoingecko(config=CONFIG_WITH_KEY)
    for stream in tap.discover_streams():
        assert 'x_cg_pro_api_key' in stream.get_url_params(None, None)
        assert 'https://pro-api.coingecko.com/api' == stream.url_base


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_tap_with_state_sync_all():
    tap = Tapcoingecko(config=CONFIG, state=copy.deepcopy(STATE))
    tap.sync_all()


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml",
                  record_mode=RECORD_MODE,
                  allow_playback_repeats=True)
def test_validate_schema():
    _validate_schema(CONFIG, CONTEXT, "coin_data.json", "coingecko_coin")
    _validate_schema(CONFIG_REALTIME, CONTEXT_REALTIME,
                     "coin_market_realtime.json", "coingecko_market_realtime")


def _validate_schema(config, context, schema_file, stream_name):
    from pathlib import Path
    test_data_dir = Path(__file__).parent
    import json

    tap = Tapcoingecko(config=config)

    stream = tap.streams[stream_name]
    stream._write_starting_replication_value(context)
    records = list(stream.get_records(context))

    with open(test_data_dir /
              ("../tap_coingecko/schemas/%s" % schema_file)) as f:
        schema = json.load(f)

        validator = JSONSchemaValidator(schema)
        validator.validate(records[0])
