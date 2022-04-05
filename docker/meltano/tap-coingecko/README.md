# tap-coingecko

`tap-coingecko` is a Singer tap for [coingecko.com](https://coingecko.com).

Built with the [Meltano SDK for Singer Taps](https://gitlab.com/meltano/singer-sdk).

## Installation

```bash
pip install tap-coingecko
```

## Configuration

### Accepted Config Options

A full list of supported settings and capabilities for this
tap is available by running:

```bash
tap-coingecko --about 
```

### Source Authentication and Authorization

A valid coingecko.com api_token is required in `config.json`

## Usage

You can easily run `tap-coingecko` by itself.

### Executing the Tap Directly

```bash
tap-coingecko --version
tap-coingecko --help
tap-coingecko --config CONFIG --discover > ./catalog.json
```

### Initialize your Development Environment

```bash
pip install poetry
poetry install
```

### Create and Run Tests

Create tests within the `tap_coingecko/tests` subfolder and
  then run:

```bash
poetry run pytest
```

You can also test the `tap-coingecko` CLI interface directly using `poetry run`:

```bash
poetry run tap-coingecko --help
```

### Install updated tap

```bash
meltano install extractor tap-coingecko
```

### SDK Dev Guide

See the [dev guide](https://gitlab.com/meltano/singer-sdk/-/blob/main/docs/dev_guide.md) for more instructions on how to use the SDK to 
develop your own taps and targets.

### Generate new schema

TODO: describe native way of creating and updating schemas

[https://www.liquid-technologies.com/online-json-to-schema-converter](https://www.liquid-technologies.com/online-json-to-schema-converter)

WARNING: This tool relies on data in provided JSON to generate data types. If the sample json dataset does not cover all use cases it may result in json validation errors for valid json responses. Always manually verify schemas after using this tool.
