import os
import threading
import time
from datetime import datetime
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
from typing import Optional

from app.datasets import dataset_manager
from app.db import SessionLocal
from app.models.db_models import Run
from app.models.schemas import RunStatus
from core_modules.methods.metrics import evaluate_metrics
from core_modules.registry import registry


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _extract_json_line(text: str) -> Optional[dict]:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    for line in reversed(lines):
        if not line.startswith("{"):
            continue
        try:
            return json.loads(line)
        except Exception:
            continue
    return None


def _resolve_conda_executable() -> str:
    # Priority: explicit env -> PATH -> common local installs.
    from_env = (os.getenv("RUNNER_CONDA_EXE") or os.getenv("CONDA_EXE") or "").strip()
    if from_env and Path(from_env).exists():
        return from_env

    from_path = shutil.which("conda")
    if from_path:
        return from_path

    candidates = [
        "/root/miniconda3/bin/conda",
        "/opt/conda/bin/conda",
        "/usr/local/miniconda3/bin/conda",
        "/home/bishePro/miniconda3/bin/conda",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    raise RuntimeError(
        "Conda executable not found. Set RUNNER_CONDA_EXE or CONDA_EXE to the full conda path "
        "(example: /root/miniconda3/bin/conda)."
    )


def _run_method_in_conda(
    method_key: str,
    nodes: list,
    edges: list,
    features: Optional[list],
    method_labels: Optional[list],
    seed: int,
    plugin_params: dict,
) -> list:
    conda_env_name = os.getenv("RUNNER_CONDA_ENV", "bsenv").strip() or "bsenv"
    timeout_sec = int(os.getenv("RUNNER_METHOD_TIMEOUT_SEC", "7200"))

    payload = {
        "method_key": method_key,
        "nodes": nodes,
        "edges": edges,
        "features": features,
        "labels": method_labels,
        "seed": seed,
        "params": plugin_params,
    }

    env = os.environ.copy()
    repo_root = str(_repo_root())
    backend_root = str(_backend_root())
    py_path_items = [repo_root, backend_root]
    if env.get("PYTHONPATH"):
        py_path_items.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(py_path_items)

    conda_exe = _resolve_conda_executable()
    cmd = [
        conda_exe,
        "run",
        "-n",
        conda_env_name,
        "python",
        "-m",
        "app.runner.method_subprocess",
    ]
    payload_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            prefix="runner_payload_",
            delete=False,
            encoding="utf-8",
        ) as fp:
            json.dump(payload, fp, ensure_ascii=False)
            payload_file = fp.name

        cmd.extend(["--payload-file", payload_file])
        proc = subprocess.run(
            cmd,
            cwd=backend_root,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_sec,
            check=False,
        )
    finally:
        if payload_file:
            try:
                os.remove(payload_file)
            except OSError:
                pass

    parsed = _extract_json_line(proc.stdout)
    if parsed and parsed.get("ok"):
        y_pred = parsed.get("y_pred")
        if not isinstance(y_pred, list):
            raise RuntimeError("Method runner returned invalid predictions")
        return y_pred

    if parsed and parsed.get("error"):
        raise RuntimeError(str(parsed.get("error")))

    err_text = (proc.stderr or proc.stdout or "").strip()
    if proc.returncode != 0:
        raise RuntimeError(
            f"Failed to execute method in conda env '{conda_env_name}' (exit={proc.returncode}): {err_text[:800]}"
        )
    raise RuntimeError("Method runner returned invalid response")


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
        conda_env_name = os.getenv("RUNNER_CONDA_ENV", "bsenv").strip() or "bsenv"
        run.logs = [*(run.logs or []), f"Dispatching method to conda env: {conda_env_name}"]
        db.commit()

        y_pred = _run_method_in_conda(
            method_key=method_key,
            nodes=nodes,
            edges=edges,
            features=features,
            method_labels=method_labels,
            seed=run.seed,
            plugin_params=plugin_params,
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
        "runner_conda_env": os.getenv("RUNNER_CONDA_ENV", "bsenv"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "methods_count": str(len(registry.methods)),
        "datasets_count": str(len(registry.datasets)),
        "metrics_count": str(len(registry.metrics)),
    }
