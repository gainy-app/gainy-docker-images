"""Tests standard tap features using the built-in SDK tests library."""

import copy

import vcr
from freezegun import freeze_time
from singer_sdk.plugin_base import JSONSchemaValidator
from singer_sdk.testing import get_standard_tap_tests

from tap_polygon.tap import Tappolygon

CONFIG = {
    "api_key": "fake_key",
}

STATE = {"bookmarks": {"polygon_marketstatus_upcoming": {}}}


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml")
def test_standard_tap_tests():
    """Run standard tap tests from the SDK."""

    tests = get_standard_tap_tests(Tappolygon, config=CONFIG)

    for test in tests:
        test()


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml")
def test_tap_sync_all():
    tap = Tappolygon(config=CONFIG)
    tap.sync_all()


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml")
def test_tap_with_state_sync_all():
    tap = Tappolygon(config=CONFIG, state=copy.deepcopy(STATE))
    tap.sync_all()


@freeze_time("2021-12-01")
@vcr.use_cassette("cassettes/tap/tap-core.yaml")
def test_validate_schema():
    _validate_schema({}, "marketstatus_upcoming.json",
                     "polygon_marketstatus_upcoming")


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
