import csv
import os
import tarfile
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.datasets.catalog import CATALOG, DatasetCatalogEntry
from app.models.schemas import DatasetInfo, DatasetPreviewResponse, DatasetStandardOutput


class DatasetManager:
    def __init__(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        self.datasets_root = Path(os.getenv("DATASETS_ROOT", repo_root / "datasets"))

    def list_dataset_info(self) -> List[DatasetInfo]:
        items: List[DatasetInfo] = []
        for entry in CATALOG.values():
            node_count = entry.node_count
            edge_count = entry.edge_count
            community_count = entry.community_count

            edges_path, labels_path, _ = self._resolve_paths(entry)
            if edges_path.exists():
                edge_count = self._count_data_rows(edges_path)
            if labels_path.exists():
                node_count = self._count_data_rows(labels_path)
                community_count = self._count_unique_labels(labels_path)

            items.append(
                self._entry_to_info(
                    entry,
                    node_count=node_count,
                    edge_count=edge_count,
                    community_count=community_count,
                )
            )
        return items

    def get_dataset_info(self, key: str) -> Optional[DatasetInfo]:
        entry = CATALOG.get(key)
        if not entry:
            return None
        return self._entry_to_info(entry)

    def preview(self, key: str) -> DatasetPreviewResponse:
        entry = CATALOG.get(key)
        if not entry:
            raise ValueError(f"Unknown dataset: {key}")

        if entry.source == "download":
            self._ensure_downloaded(entry)

        edges_path, labels_path, features_path = self._resolve_paths(entry)
        if not edges_path.exists():
            raise FileNotFoundError(
                f"Dataset '{entry.key}' missing edges file: {edges_path}. "
                f"Please place edges.csv under {edges_path.parent}"
            )
        if entry.has_labels and not labels_path.exists():
            raise FileNotFoundError(
                f"Dataset '{entry.key}' missing labels file: {labels_path}. "
                f"Please place labels.csv under {labels_path.parent}"
            )

        edge_count, edge_preview = self._read_csv_preview(edges_path)
        label_count, label_preview = self._read_csv_preview(labels_path) if labels_path.exists() else (0, [])
        feature_count, feature_preview = self._read_csv_preview(features_path) if features_path.exists() else (0, [])

        output = DatasetStandardOutput(
            graph={
                "path": str(edges_path),
                "num_edges": edge_count,
                "sample": edge_preview,
            },
            features=(
                {
                    "path": str(features_path),
                    "num_rows": feature_count,
                    "sample": feature_preview,
                }
                if features_path.exists()
                else None
            ),
            labels=(
                {
                    "path": str(labels_path),
                    "num_rows": label_count,
                    "sample": label_preview,
                }
                if labels_path.exists()
                else None
            ),
            meta={
                "key": entry.key,
                "name": entry.name,
                "type": entry.type,
                "source": entry.source,
                "local_path": entry.local_path,
                "expected_nodes": entry.node_count,
                "expected_edges": entry.edge_count,
                "expected_communities": entry.community_count,
            },
        )

        return DatasetPreviewResponse(dataset=self._entry_to_info(entry), output=output)

    def load_metric_inputs(self, key: str) -> Dict[str, object]:
        entry = CATALOG.get(key)
        if not entry:
            raise ValueError(f"Unknown dataset: {key}")

        if entry.source == "download":
            self._ensure_downloaded(entry)

        edges_path, labels_path, features_path = self._resolve_paths(entry)
        if not edges_path.exists():
            raise FileNotFoundError(
                f"Dataset '{entry.key}' missing edges file: {edges_path}. "
                f"Please place edges.csv under {edges_path.parent}"
            )

        edges_rows = self._read_csv_rows(edges_path)
        edges: List[Tuple[str, str]] = []
        node_set = set()
        for row in edges_rows:
            if len(row) < 2:
                continue
            src = row[0].strip()
            dst = row[1].strip()
            if not src or not dst:
                continue
            edges.append((src, dst))
            node_set.add(src)
            node_set.add(dst)

        labels: Optional[Dict[str, str]] = None
        if labels_path.exists():
            labels = {}
            for row in self._read_csv_rows(labels_path):
                if len(row) < 2:
                    continue
                node = row[0].strip()
                label = row[1].strip()
                if not node:
                    continue
                labels[node] = label
                node_set.add(node)
        elif entry.has_labels:
            raise FileNotFoundError(
                f"Dataset '{entry.key}' missing labels file: {labels_path}. "
                f"Please place labels.csv under {labels_path.parent}"
            )

        nodes = sorted(node_set)

        features = None
        feature_dim = 0
        if features_path.exists():
            features_map: Dict[str, List[float]] = {}
            for row in self._read_csv_rows(features_path):
                if len(row) < 2:
                    continue
                node = row[0].strip()
                if not node:
                    continue
                vec: List[float] = []
                for value in row[1:]:
                    try:
                        vec.append(float(value))
                    except ValueError:
                        vec.append(0.0)
                features_map[node] = vec
                feature_dim = max(feature_dim, len(vec))
                if node not in node_set:
                    node_set.add(node)
            nodes = sorted(node_set)
            features = []
            for node in nodes:
                vec = features_map.get(node)
                if vec is None:
                    vec = [0.0 for _ in range(feature_dim)]
                elif len(vec) < feature_dim:
                    vec = [*vec, *([0.0] * (feature_dim - len(vec)))]
                features.append(vec)

        return {
            "edges": edges,
            "labels": labels,
            "nodes": nodes,
            "features": features,
        }

    def _entry_to_info(
        self,
        entry: DatasetCatalogEntry,
        node_count: Optional[int] = None,
        edge_count: Optional[int] = None,
        community_count: Optional[int] = None,
    ) -> DatasetInfo:
        return DatasetInfo(
            key=entry.key,
            name=entry.name,
            has_labels=entry.has_labels,
            has_features=entry.has_features,
            description=entry.description,
            type=entry.type,
            source=entry.source,
            local_path=entry.local_path,
            hash=entry.hash,
            node_count=node_count if node_count is not None else entry.node_count,
            edge_count=edge_count if edge_count is not None else entry.edge_count,
            community_count=(
                community_count if community_count is not None else entry.community_count
            ),
            downloadable=entry.source == "download",
        )

    def _resolve_paths(self, entry: DatasetCatalogEntry) -> Tuple[Path, Path, Path]:
        base = self.datasets_root / entry.local_path
        return base / "edges.csv", base / "labels.csv", base / "features.csv"

    def _ensure_downloaded(self, entry: DatasetCatalogEntry) -> None:
        edges_path, labels_path, features_path = self._resolve_paths(entry)
        if edges_path.exists() and labels_path.exists() and features_path.exists():
            return

        if not entry.download_url:
            raise RuntimeError(f"Dataset {entry.key} has no download URL configured")

        cache_dir = edges_path.parent
        raw_dir = cache_dir / "raw"
        cache_dir.mkdir(parents=True, exist_ok=True)
        raw_dir.mkdir(parents=True, exist_ok=True)

        tgz_path = raw_dir / f"{entry.key}.tgz"
        try:
            urllib.request.urlretrieve(entry.download_url, tgz_path)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to download dataset '{entry.key}' from {entry.download_url}: {exc}"
            ) from exc

        with tarfile.open(tgz_path, "r:gz") as tar:
            self._safe_extract(tar, raw_dir)

        cites_path, content_path = self._find_planetoid_files(raw_dir)
        self._convert_planetoid_to_csv(cites_path, content_path, edges_path, labels_path, features_path)

    def _safe_extract(self, tar: tarfile.TarFile, target_dir: Path) -> None:
        target = target_dir.resolve()
        for member in tar.getmembers():
            member_path = (target_dir / member.name).resolve()
            if not str(member_path).startswith(str(target)):
                raise RuntimeError("Unsafe tar archive path detected")
        tar.extractall(target_dir)

    def _find_planetoid_files(self, raw_dir: Path) -> Tuple[Path, Path]:
        cites_path = None
        content_path = None
        for file_path in raw_dir.rglob("*"):
            if file_path.name.endswith(".cites"):
                cites_path = file_path
            if file_path.name.endswith(".content"):
                content_path = file_path
        if not cites_path or not content_path:
            raise RuntimeError("Download succeeded but required .cites/.content files were not found")
        return cites_path, content_path

    def _convert_planetoid_to_csv(
        self,
        cites_path: Path,
        content_path: Path,
        edges_path: Path,
        labels_path: Path,
        features_path: Path,
    ) -> None:
        edges_path.parent.mkdir(parents=True, exist_ok=True)

        with content_path.open("r", encoding="utf-8") as fp:
            lines = [line.strip() for line in fp.readlines() if line.strip()]

        if not lines:
            raise RuntimeError("content file is empty")

        first_cols = lines[0].split()
        feat_dim = max(len(first_cols) - 2, 0)

        with labels_path.open("w", newline="", encoding="utf-8") as labels_fp, features_path.open(
            "w", newline="", encoding="utf-8"
        ) as features_fp:
            labels_writer = csv.writer(labels_fp)
            features_writer = csv.writer(features_fp)
            labels_writer.writerow(["node", "label"])
            features_writer.writerow(["node", *[f"f{i}" for i in range(feat_dim)]])

            for line in lines:
                cols = line.split()
                node = cols[0]
                label = cols[-1]
                feats = cols[1:-1]
                labels_writer.writerow([node, label])
                features_writer.writerow([node, *feats])

        with cites_path.open("r", encoding="utf-8") as cites_fp, edges_path.open(
            "w", newline="", encoding="utf-8"
        ) as edges_fp:
            edges_writer = csv.writer(edges_fp)
            edges_writer.writerow(["source", "target"])
            for line in cites_fp:
                line = line.strip()
                if not line:
                    continue
                src, dst = line.split()[:2]
                edges_writer.writerow([src, dst])

    def _read_csv_preview(self, file_path: Path, max_rows: int = 10) -> Tuple[int, List[List[str]]]:
        if not file_path.exists():
            return 0, []

        with file_path.open("r", encoding="utf-8") as fp:
            sample = fp.read(4096)
            fp.seek(0)
            has_header = csv.Sniffer().has_header(sample) if sample else False
            reader = csv.reader(fp)

            total = 0
            preview: List[List[str]] = []
            for idx, row in enumerate(reader):
                if has_header and idx == 0:
                    continue
                if not row:
                    continue
                total += 1
                if len(preview) < max_rows:
                    preview.append(row)
        return total, preview

    def _read_csv_rows(self, file_path: Path) -> List[List[str]]:
        with file_path.open("r", encoding="utf-8") as fp:
            sample = fp.read(4096)
            fp.seek(0)
            has_header = csv.Sniffer().has_header(sample) if sample else False
            reader = csv.reader(fp)
            rows: List[List[str]] = []
            for idx, row in enumerate(reader):
                if has_header and idx == 0:
                    continue
                if not row:
                    continue
                rows.append([self._clean_cell(cell) for cell in row])
            return rows

    def _count_data_rows(self, file_path: Path) -> int:
        return len(self._read_csv_rows(file_path))

    def _count_unique_labels(self, labels_path: Path) -> int:
        labels = set()
        for row in self._read_csv_rows(labels_path):
            if len(row) < 2:
                continue
            label = row[1].strip()
            if label:
                labels.add(label)
        return len(labels)

    def _clean_cell(self, value: str) -> str:
        # Normalize BOM-contaminated csv cells, e.g. "\ufeff0" -> "0".
        return value.replace("\ufeff", "").strip()


dataset_manager = DatasetManager()
