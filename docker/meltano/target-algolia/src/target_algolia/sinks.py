import json
import os
from typing import Dict, List, Optional

from algoliasearch.search_client import SearchClient
from algoliasearch.search_index import SearchIndex
from singer_sdk.plugin_base import PluginBase
from singer_sdk.sinks import BatchSink


class AlgoliaSink(BatchSink):
    """Algolia target sink class, which handles writing streams."""

    max_size = 1000  # Max records to write in one batch

    settings_dir = os.path.join(os.path.dirname(__file__), "../../settings")  # Index settings folder

    def __init__(
            self,
            target: PluginBase,
            stream_name: str,
            schema: Dict,
            key_properties: Optional[List[str]],
    ) -> None:
        """Initialize target sink.

        Args:
            target: Target instance.
            stream_name: Name of the stream to sink.
            schema: Schema of the stream to sink.
            key_properties: Primary key of the stream to sink.
        """

        super().__init__(target, stream_name, schema, key_properties)
        self.search_index = self._init_search_index()

    def process_record(self, record: dict, context: dict) -> None:
        """Load the latest record from the stream and converts into a search records.

        Creates `context["records"]` list and append all search records for processing during
        :meth:`~singer_sdk.BatchSink.process_batch()`.

        Args:
            record: Individual record in the stream.
            context: Stream partition or context dictionary.
        """

        super().process_record(self._to_search_record(record), context)

    def process_batch(self, context: dict) -> None:
        """Takes records from context, prepares for indexing and save into Algolia index.

        Args:
            context: Stream partition or context dictionary.
        """
        if "records" in context:
            self.search_index.save_objects(context["records"])

    def _init_search_index(self) -> SearchIndex:
        """Create an Algolia search client and initialize the search index.

        :return: configured Search Index
        """

        search_client = SearchClient.create(self.config["app_id"], self.config["api_key"])
        search_index = search_client.init_index(self.config["index_name"])

        if "index_settings_file" in self.config:
            index_settings_path = self.config["index_settings_file"]
            if not os.path.isabs(index_settings_path):
                index_settings_path = os.path.join(self.settings_dir, index_settings_path)

            self.logger.info(f"Applying index settings from file: {index_settings_path}")
            with open(index_settings_path) as index_settings_file:
                index_settings = json.load(index_settings_file)
                search_index.set_settings(index_settings)

        return search_index

    def _to_search_record(self, record: Dict) -> Dict:
        # Creates a new records using all attributes needed for search
        search_record = {attr: record.get(attr, None) for attr in self.config["attributes"]}

        # Creates a surrogate `objectID` based on primary key attributes
        search_record["objectID"] = "".join([record[key_attr] for key_attr in self.config["primary_key"]])

        return search_record
