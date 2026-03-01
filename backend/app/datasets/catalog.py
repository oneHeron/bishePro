from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class DatasetCatalogEntry:
    key: str
    name: str
    type: str
    source: str
    local_path: str
    description: str
    has_labels: bool
    has_features: bool
    node_count: Optional[int] = None
    edge_count: Optional[int] = None
    community_count: Optional[int] = None
    hash: Optional[str] = None
    download_url: Optional[str] = None


CATALOG: Dict[str, DatasetCatalogEntry] = {
    "strike": DatasetCatalogEntry(
        key="strike",
        name="Strike",
        type="unattributed_network",
        source="manual",
        local_path="manual/strike",
        description="Strike social network (topology + labels provided manually).",
        has_labels=True,
        has_features=False,
        node_count=24,
        edge_count=38,
    ),
    "karate": DatasetCatalogEntry(
        key="karate",
        name="Karate",
        type="unattributed_network",
        source="manual",
        local_path="manual/karate",
        description="Zachary Karate Club (topology + labels provided manually).",
        has_labels=True,
        has_features=False,
        node_count=34,
        edge_count=78,
    ),
    "dolphins": DatasetCatalogEntry(
        key="dolphins",
        name="Dolphins",
        type="unattributed_network",
        source="manual",
        local_path="manual/dolphins",
        description="Dolphins social network (topology + labels provided manually).",
        has_labels=True,
        has_features=False,
        node_count=62,
        edge_count=159,
    ),
    "polbooks": DatasetCatalogEntry(
        key="polbooks",
        name="Polbooks",
        type="unattributed_network",
        source="manual",
        local_path="manual/polbooks",
        description="Political books network (topology + labels provided manually).",
        has_labels=True,
        has_features=False,
        node_count=105,
        edge_count=441,
    ),
    "football": DatasetCatalogEntry(
        key="football",
        name="Football",
        type="unattributed_network",
        source="manual",
        local_path="manual/football",
        description="American college football network (topology + labels provided manually).",
        has_labels=True,
        has_features=False,
        node_count=180,
        edge_count=788,
    ),
    "email_eu": DatasetCatalogEntry(
        key="email_eu",
        name="Email_Eu",
        type="unattributed_network",
        source="manual",
        local_path="manual/email_eu",
        description="EU institution email network (topology + labels provided manually).",
        has_labels=True,
        has_features=False,
        node_count=1005,
        edge_count=25571,
    ),
    "polblogs": DatasetCatalogEntry(
        key="polblogs",
        name="Polblogs",
        type="unattributed_network",
        source="manual",
        local_path="manual/polblogs",
        description="Political blogs network (topology + labels provided manually).",
        has_labels=True,
        has_features=False,
        node_count=1490,
        edge_count=16717,
    ),
    "cora": DatasetCatalogEntry(
        key="cora",
        name="Cora",
        type="attributed_network",
        source="download",
        local_path="cache/cora",
        description="Citation network with labels and bag-of-words features.",
        has_labels=True,
        has_features=True,
        node_count=2708,
        edge_count=5429,
        community_count=7,
        download_url="https://linqs-data.soe.ucsc.edu/public/lbc/cora.tgz",
    ),
    "citeseer": DatasetCatalogEntry(
        key="citeseer",
        name="Citeseer",
        type="attributed_network",
        source="download",
        local_path="cache/citeseer",
        description="Citation network with labels and bag-of-words features.",
        has_labels=True,
        has_features=True,
        node_count=3327,
        edge_count=4732,
        community_count=6,
        download_url="https://linqs-data.soe.ucsc.edu/public/lbc/citeseer.tgz",
    ),
}
