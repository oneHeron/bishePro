import os
import threading
import time
from datetime import datetime
from typing import Optional

from app.datasets import dataset_manager
from app.db import SessionLocal
from app.models.db_models import Run
from app.models.schemas import RunStatus
from core_modules.methods.base import MethodInputData
from core_modules.methods.metrics import evaluate_metrics
from core_modules.registry import registry


def _run_pipeline(run_id: str) -> None:
    db = SessionLocal()
    run = db.query(Run).filter(Run.run_id == run_id).first()
    if not run:
        db.close()
        return

    run.status = RunStatus.running.value
    run.started_at = datetime.utcnow()
    run.logs = [*(run.logs or []), "Run started"]
    db.commit()
    started_at = time.time()

    try:
        run = db.query(Run).filter(Run.run_id == run_id).first()
        run.logs = [*(run.logs or []), "Preparing data"]
        db.commit()

        dataset_key = run.dataset_id or run.dataset_key
        method_key = run.method_id or run.method_key
        metric_keys = run.metrics or run.metric_keys or []

        dataset_inputs = dataset_manager.load_metric_inputs(dataset_key)
        nodes = dataset_inputs["nodes"]
        labels_map = dataset_inputs["labels"]
        edges = dataset_inputs["edges"]
        features = dataset_inputs.get("features")
        method_labels = None
        if labels_map is not None and all(node in labels_map for node in nodes):
            method_labels = [labels_map[node] for node in nodes]

        plugin = registry.method_plugins.get(method_key)
        if plugin is None:
            raise ValueError(f"Method plugin not found for key: {method_key}")

        run = db.query(Run).filter(Run.run_id == run_id).first()
        run.logs = [*(run.logs or []), f"Executing method: {plugin.name}"]
        db.commit()

        plugin_params = {**(run.params or {}), "dataset_key": dataset_key}

        y_pred = plugin.run(
            data=MethodInputData(nodes=nodes, edges=edges, features=features, labels=method_labels),
            seed=run.seed,
            params=plugin_params,
        )
        if len(y_pred) != len(nodes):
            raise ValueError(
                f"Method '{method_key}' produced {len(y_pred)} labels, "
                f"but dataset has {len(nodes)} nodes"
            )

        node_to_idx = {node: idx for idx, node in enumerate(nodes)}
        metric_results: dict = {}
        labeled_nodes = [node for node in nodes if labels_map is not None and node in labels_map]

        if labels_map is not None and len(labeled_nodes) < len(nodes):
            run = db.query(Run).filter(Run.run_id == run_id).first()
            run.logs = [
                *(run.logs or []),
                f"Partial labels detected: {len(labeled_nodes)}/{len(nodes)} nodes have labels. "
                "Label-based metrics will use labeled subset only.",
            ]
            db.commit()

        for metric_key in metric_keys:
            metric = registry.metrics[metric_key]
            if metric.requires_labels:
                if labels_map is None:
                    raise ValueError(
                        f"Metric '{metric_key}' requires labels, but dataset '{dataset_key}' has no labels file"
                    )
                if not labeled_nodes:
                    raise ValueError(
                        f"Metric '{metric_key}' requires labels, but no labeled nodes were found in dataset '{dataset_key}'"
                    )

                sub_y_true = [labels_map[node] for node in labeled_nodes]
                sub_y_pred = [y_pred[node_to_idx[node]] for node in labeled_nodes]
                sub_result = evaluate_metrics(
                    metric_keys=[metric_key],
                    y_pred=sub_y_pred,
                    y_true=sub_y_true,
                    graph_edges=edges,
                    nodes=labeled_nodes,
                )
            else:
                sub_result = evaluate_metrics(
                    metric_keys=[metric_key],
                    y_pred=y_pred,
                    y_true=None,
                    graph_edges=edges,
                    nodes=nodes,
                )

            metric_results.update(sub_result)

        community_assignment = [
            {"node": node, "community": int(y_pred[idx])} for idx, node in enumerate(nodes)
        ]
        viz = None
        if len(nodes) < 100:
            node_set = set(nodes)
            viz = {
                "nodes": community_assignment,
                "edges": [[src, dst] for src, dst in edges if src in node_set and dst in node_set],
            }
        results = {
            "metrics": metric_results,
            "community_assignment": community_assignment,
            "node_count": len(nodes),
            "viz": viz,
        }

        run = db.query(Run).filter(Run.run_id == run_id).first()
        run.status = RunStatus.finished.value
        run.results = results
        run.metrics_result = metric_results
        run.duration = round(time.time() - started_at, 3)
        run.duration_sec = run.duration
        run.finished_at = datetime.utcnow()
        run.logs = [*(run.logs or []), "Run finished"]
        db.commit()
    except Exception as exc:
        run = db.query(Run).filter(Run.run_id == run_id).first()
        if run:
            run.status = RunStatus.failed.value
            run.error = str(exc)
            run.duration = round(time.time() - started_at, 3)
            run.duration_sec = run.duration
            run.finished_at = datetime.utcnow()
            run.logs = [*(run.logs or []), "Run failed"]
            db.commit()
    finally:
        db.close()


def _try_enqueue_rq(run_id: str) -> bool:
    try:
        from redis import Redis
        from rq import Queue
    except Exception:
        return False

    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    queue_name = os.getenv("RUN_QUEUE", "runs")

    try:
        conn = Redis.from_url(redis_url)
        q = Queue(queue_name, connection=conn)
        q.enqueue("app.runner.mock_runner.execute_run_job", run_id)
        return True
    except Exception:
        return False


def submit_run(run: Run) -> str:
    backend = os.getenv("RUNNER_BACKEND", "auto").lower()

    if backend in {"inline", "sync"}:
        _run_pipeline(run.run_id)
        return run.run_id

    if backend in {"auto", "rq", "redis"}:
        enqueued = _try_enqueue_rq(run.run_id)
        if enqueued:
            return run.run_id
        if backend in {"rq", "redis"}:
            # Explicitly requested queue backend but unavailable.
            raise RuntimeError("RQ/Redis backend unavailable; please check REDIS_URL and worker status")

    # Fallback local async thread
    thread = threading.Thread(target=_run_pipeline, args=(run.run_id,), daemon=True)
    thread.start()
    return run.run_id


def execute_run_job(run_id: str) -> None:
    _run_pipeline(run_id)


def build_version_info() -> dict:
    return {
        "backend": "0.1.0",
        "runner": os.getenv("RUNNER_BACKEND", "auto"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "methods_count": str(len(registry.methods)),
        "datasets_count": str(len(registry.datasets)),
        "metrics_count": str(len(registry.metrics)),
    }
