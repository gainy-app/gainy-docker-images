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
            "api_key",
            th.StringType,
            description="Algolia API key with following permissions: addObject, deleteObject, editSettings",
            required=True
        ),
        th.Property(
            "index_mapping_file",
            th.StringType,
            description="YAML file with Algolia index configurations",
            required=True
        )
    ).to_dict()
