from app.datasets.catalog import CATALOG
from app.models.schemas import DatasetInfo
from core_modules.registry import registry


def register() -> None:
    for entry in CATALOG.values():
        registry.register_dataset(
            DatasetInfo(
                key=entry.key,
                name=entry.name,
                has_labels=entry.has_labels,
                has_features=entry.has_features,
                description=entry.description,
                type=entry.type,
                source=entry.source,
                local_path=entry.local_path,
                hash=entry.hash,
                node_count=entry.node_count,
                edge_count=entry.edge_count,
                community_count=entry.community_count,
                downloadable=entry.source == "download",
            )
        )
