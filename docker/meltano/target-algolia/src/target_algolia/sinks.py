from typing import Dict, List, Optional

from algoliasearch.search_client import SearchClient
from algoliasearch.search_index import SearchIndex
from singer_sdk.plugin_base import PluginBase
from singer_sdk.sinks import BatchSink

from target_algolia.utils import parse_config


class AlgoliaSink(BatchSink):
    """Algolia target sink class, which handles writing streams."""

    max_size = 1000  # Max records to write in one batch

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
        self.index_config, self.search_index = self._init_search_index()

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

    def _init_search_index(self) -> (Dict, SearchIndex):
        """Create an Algolia search client and initialize the search index.

        :return: configured Search Index
        """

        search_client = SearchClient.create(self.config["app_id"], self.config["api_key"])
        index_config = self._get_index_config()

        search_index = search_client.init_index(index_config["name"])

        if "settings" in index_config:
            self.logger.info(f"Applying index settings to index: {index_config['name']}")
            search_index.set_settings(index_config["settings"])

        return index_config, search_index

    def _get_index_config(self):
        indices_config = parse_config(self.config["index_mapping_file"])
        for index_config in indices_config:
            table_config = index_config["index"]["source"]["table"]
            if self.stream_name == f"{table_config['schema']}-{table_config['name']}":
                return index_config["index"]

        raise ValueError(f"Index for stream `{self.stream_name}` was not found in the index mapping")

    def _to_search_record(self, record: Dict) -> Dict:
        # Creates a new records using all attributes needed for search
        search_record = {attr: record.get(attr, None) for attr in self.index_config["source"]["attributes"]}

        # Creates a surrogate `objectID` based on primary key attributes
        search_record["objectID"] = "".join(
            [str(record[key_attr]) for key_attr in self.index_config["source"]["primary_key"]]
        )

        return search_record
