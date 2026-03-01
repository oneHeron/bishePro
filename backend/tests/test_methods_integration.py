from pathlib import Path

from app.datasets import dataset_manager
from app.services.plugin_loader import load_builtin_plugins
from core_modules.methods.base import MethodInputData
from core_modules.methods.metrics import evaluate_metrics
from core_modules.registry import registry


def _write_karate_like_dataset(root: Path) -> None:
    karate_dir = root / "manual" / "karate"
    karate_dir.mkdir(parents=True, exist_ok=True)

    # Two dense communities with a bridge edge.
    edges = [
        ("0", "1"),
        ("1", "2"),
        ("2", "3"),
        ("0", "3"),
        ("4", "5"),
        ("5", "6"),
        ("6", "7"),
        ("4", "7"),
        ("3", "4"),
    ]

    labels = {
        "0": "A",
        "1": "A",
        "2": "A",
        "3": "A",
        "4": "B",
        "5": "B",
        "6": "B",
        "7": "B",
    }

    with (karate_dir / "edges.csv").open("w", encoding="utf-8") as fp:
        fp.write("source,target\n")
        for src, dst in edges:
            fp.write(f"{src},{dst}\n")

    with (karate_dir / "labels.csv").open("w", encoding="utf-8") as fp:
        fp.write("node,label\n")
        for node, label in labels.items():
            fp.write(f"{node},{label}\n")


def test_all_methods_can_run_karate_method_to_metrics(tmp_path: Path) -> None:
    dataset_manager.datasets_root = tmp_path
    _write_karate_like_dataset(tmp_path)
    load_builtin_plugins()

    inputs = dataset_manager.load_metric_inputs("karate")
    nodes = inputs["nodes"]
    y_true = [inputs["labels"][node] for node in nodes]

    method_keys = ["louvain", "kmeans", "nmf", "deepwalk"]

    for method_key in method_keys:
        plugin = registry.method_plugins[method_key]
        y_pred = plugin.run(
            data=MethodInputData(nodes=nodes, edges=inputs["edges"], features=inputs["features"]),
            seed=42,
            params={"num_clusters": 2},
        )

        assert len(y_pred) == len(nodes)

        metric_result = evaluate_metrics(
            metric_keys=["nmi", "acc", "ari", "modularity_q"],
            y_pred=y_pred,
            y_true=y_true,
            graph_edges=inputs["edges"],
            nodes=nodes,
        )
        assert set(metric_result.keys()) == {"nmi", "acc", "ari", "modularity_q"}
