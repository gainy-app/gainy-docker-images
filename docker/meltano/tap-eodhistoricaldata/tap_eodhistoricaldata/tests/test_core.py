"""Tests standard tap features using the built-in SDK tests library."""

import pytest

from singer_sdk.testing import get_standard_tap_tests

from singer_sdk.plugin_base import JSONSchemaValidator

from tap_eodhistoricaldata.tap import Tapeodhistoricaldata

SAMPLE_CONFIG = {
    "api_token": "fake_token",
    "symbols": ["AAPL"]
}


# Run standard built-in tap tests from the SDK

@pytest.mark.vcr
def test_standard_tap_tests():
    """Run standard tap tests from the SDK."""

    tests = get_standard_tap_tests(
        Tapeodhistoricaldata,
        config=SAMPLE_CONFIG
    )

    for test in tests:
        test()


def test_validate_schema():
    from pathlib import Path
    test_data_dir = Path(__file__).parent
    import json
    with open(test_data_dir / 'fixtures/sample.json') as s:
        with open(test_data_dir / '../schemas/fundamentals.json') as f:
            sch = json.load(f)
            sample = json.load(s)

            validator = JSONSchemaValidator(sch)
            validator.validate(sample)


@pytest.mark.vcr
def test_selected():
    tap1 = Tapeodhistoricaldata(config=SAMPLE_CONFIG, parse_env_config=True)

    tap1.sync_all()


def test_partitions_and_state():
    state = {"bookmarks": {"fundamentals": {"partitions": [
        {"context": {"Code": "F"}, "replication_key": "UpdatedAt", "replication_key_value": "2021-07-11"}
    ]}}}

    config = {"api_token": "fake_token",
              "symbols": ["AAPL", "F", "IBM"]
              }

    tap1 = Tapeodhistoricaldata(config=config, parse_env_config=True)

    assert tap1.streams['fundamentals'].partitions == [{'Code': 'AAPL'}, {'Code': 'F'}, {'Code': 'IBM'}]

    tap1 = Tapeodhistoricaldata(config=config, state=state, parse_env_config=True)

    assert tap1.streams['fundamentals'].partitions == [{'Code': 'IBM'}]

    state = {"bookmarks": {"fundamentals": {"partitions": [
        {"context": {"Code": "IBM"}, "replication_key": "UpdatedAt", "replication_key_value": "2021-07-11"}
    ]}}}

    tap1 = Tapeodhistoricaldata(config=config, state=state, parse_env_config=True)

    assert tap1.streams['fundamentals'].partitions == []

    state = {"bookmarks": {"fundamentals": {"partitions": [
        {"context": {"Code": "NON"}, "replication_key": "UpdatedAt", "replication_key_value": "2021-07-11"}
    ]}}}

    tap1 = Tapeodhistoricaldata(config=config, state=state, parse_env_config=True)

    assert tap1.streams['fundamentals'].partitions == [{'Code': 'AAPL'}, {'Code': 'F'}, {'Code': 'IBM'}]


def test_start_symbol():
    config = {"api_token": "fake_token",
              "symbols": ["AAPL", "F", "IBM"],
              "start_symbol": "F"
              }

    tap1 = Tapeodhistoricaldata(config=config, parse_env_config=True)

    assert tap1.streams['fundamentals'].partitions == [{'Code': 'F'}, {'Code': 'IBM'}]
