"""Algolia target class."""

from singer_sdk.target_base import Target
from singer_sdk import typing as th

from target_algolia.sinks import (
    AlgoliaSink
)


class TargetAlgolia(Target):

    name = "target-algolia"
    default_sink_class = AlgoliaSink

    config_jsonschema = th.PropertiesList(
        th.Property(
            "app_id",
            th.StringType,
            description="Algolia ID of application",
            required=True
        ),
        th.Property(
            "index_name",
            th.StringType,
            description="Algolia index name",
            required=True
        ),
        th.Property(
            "api_key",
            th.StringType,
            description="Algolia API key with following permissions: addObject, deleteObject, editSettings",
            required=True
        ),
        th.Property(
            "index_settings_file",
            th.StringType,
            description="JSON file with Algolia index settings",
            required=False
        ),
        th.Property(
            "attributes",
            th.ArrayType(th.StringType),
            description="List of attributes for indexing",
            required=False
        ),
        th.Property(
            "primary_key",
            th.ArrayType(th.StringType),
            description="List of primary key columns",
            required=True
        )
    ).to_dict()
