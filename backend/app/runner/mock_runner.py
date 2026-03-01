import os
import threading
import time
from datetime import datetime
import json
import re
import signal
from pathlib import Path
import subprocess
import shutil
import tempfile
from typing import Optional, Tuple, Dict, Set

from app.datasets import dataset_manager
from app.db import SessionLocal
from app.models.db_models import Run
from app.models.schemas import RunStatus
from core_modules.methods.metrics import evaluate_metrics
from core_modules.registry import registry

_RUN_CANCEL_LOCK = threading.RLock()
_RUN_CANCEL_REQUESTS: Set[str] = set()
_RUN_ACTIVE_PROCS: Dict[str, subprocess.Popen] = {}


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


def _mark_cancel_requested(run_id: str) -> None:
    with _RUN_CANCEL_LOCK:
        _RUN_CANCEL_REQUESTS.add(str(run_id))


def _clear_cancel_requested(run_id: str) -> None:
    with _RUN_CANCEL_LOCK:
        _RUN_CANCEL_REQUESTS.discard(str(run_id))


def _is_cancel_requested(run_id: str) -> bool:
    with _RUN_CANCEL_LOCK:
        return str(run_id) in _RUN_CANCEL_REQUESTS


def _register_active_proc(run_id: str, proc: subprocess.Popen) -> None:
    with _RUN_CANCEL_LOCK:
        _RUN_ACTIVE_PROCS[str(run_id)] = proc


def _unregister_active_proc(run_id: str, proc: Optional[subprocess.Popen] = None) -> None:
    with _RUN_CANCEL_LOCK:
        existing = _RUN_ACTIVE_PROCS.get(str(run_id))
        if existing is None:
            return
        if proc is not None and existing is not proc:
            return
        _RUN_ACTIVE_PROCS.pop(str(run_id), None)


def _terminate_proc_tree(proc: subprocess.Popen) -> None:
    if proc is None:
        return
    if proc.poll() is not None:
        return

    try:
        if os.name != "nt":
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            proc.terminate()
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass

    try:
        proc.wait(timeout=3)
    except Exception:
        try:
            if os.name != "nt":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def cancel_run_execution(run_id: str) -> dict:
    run_key = str(run_id)
    _mark_cancel_requested(run_key)
    active = None
    with _RUN_CANCEL_LOCK:
        active = _RUN_ACTIVE_PROCS.get(run_key)
    if active is not None:
        _terminate_proc_tree(active)
        return {"cancel_requested": True, "had_active_process": True}
    return {"cancel_requested": True, "had_active_process": False}


def _run_method_in_conda(
    run_id: str,
    method_key: str,
    nodes: list,
    edges: list,
    features: Optional[list],
    method_labels: Optional[list],
    seed: int,
    plugin_params: dict,
) -> list:
    default_env_map = {
        "csea": "bsenv-tf",
    }
    requested_env = str(plugin_params.get("_conda_env", "")).strip()
    conda_env_name = requested_env or default_env_map.get(method_key) or (os.getenv("RUNNER_CONDA_ENV", "bsenv").strip() or "bsenv")
    timeout_sec = int(os.getenv("RUNNER_METHOD_TIMEOUT_SEC", "7200"))
    plugin_runtime_params = dict(plugin_params or {})
    plugin_runtime_params.pop("_conda_env", None)

    payload = {
        "method_key": method_key,
        "nodes": nodes,
        "edges": edges,
        "features": features,
        "labels": method_labels,
        "seed": seed,
        "params": plugin_runtime_params,
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
        proc = subprocess.Popen(
            cmd,
            cwd=backend_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=(os.name != "nt"),
        )
        _register_active_proc(run_id, proc)
        stdout_text = ""
        stderr_text = ""
        deadline = time.time() + max(1, timeout_sec)
        while True:
            if _is_cancel_requested(run_id):
                _terminate_proc_tree(proc)
                _unregister_active_proc(run_id, proc)
                raise RuntimeError("Run cancelled by user.")
            if time.time() > deadline:
                _terminate_proc_tree(proc)
                _unregister_active_proc(run_id, proc)
                raise RuntimeError(f"Method execution timed out after {timeout_sec}s.")
            try:
                out, err = proc.communicate(timeout=0.3)
                stdout_text = out or ""
                stderr_text = err or ""
                break
            except subprocess.TimeoutExpired:
                continue
        _unregister_active_proc(run_id, proc)
        proc_stdout = stdout_text
        proc_stderr = stderr_text
    finally:
        _unregister_active_proc(run_id)
        if payload_file:
            try:
                os.remove(payload_file)
            except OSError:
                pass

    parsed = _extract_json_line(proc_stdout)
    if parsed and parsed.get("ok"):
        y_pred = parsed.get("y_pred")
        if not isinstance(y_pred, list):
            raise RuntimeError("Method runner returned invalid predictions")
        return y_pred

    if parsed and parsed.get("error"):
        message = str(parsed.get("error"))
        detail = str(parsed.get("error_detail") or "").strip()
        if detail:
            raise RuntimeError(f"{message}\n\n{subprocess_traceback_header()}\n{detail}")
        raise RuntimeError(message)

    err_text = (proc_stderr or proc_stdout or "").strip()
    if proc.returncode != 0:
        raise RuntimeError(
            f"Failed to execute method in conda env '{conda_env_name}' (exit={proc.returncode}): {err_text[:4000]}"
        )
    raise RuntimeError("Method runner returned invalid response")


def subprocess_traceback_header() -> str:
    return "[method subprocess traceback]"


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no"}
    return bool(value)


_TF_GPU_PROBE_CACHE: dict = {}
_TORCH_GPU_PROBE_CACHE: dict = {}


def _probe_tensorflow_gpu(conda_env_name: str) -> Tuple[Optional[bool], str]:
    cache_key = str(conda_env_name).strip() or "bsenv"
    if cache_key in _TF_GPU_PROBE_CACHE:
        return _TF_GPU_PROBE_CACHE[cache_key]

    conda_exe = _resolve_conda_executable()
    cmd = [
        conda_exe,
        "run",
        "-n",
        cache_key,
        "python",
        "-c",
        "import tensorflow as tf; print(len(tf.config.list_physical_devices('GPU')))",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(_backend_root()),
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except Exception as exc:
        result = (None, f"TensorFlow GPU probe failed: {exc}")
        _TF_GPU_PROBE_CACHE[cache_key] = result
        return result

    combined = "\n".join([proc.stdout or "", proc.stderr or ""]).strip()
    gpu_count = None
    for line in reversed(combined.splitlines()):
        text = line.strip()
        if not text:
            continue
        if re.fullmatch(r"\d+", text):
            gpu_count = int(text)
            break

    if proc.returncode != 0 or gpu_count is None:
        result = (None, f"TensorFlow GPU probe failed in env '{cache_key}' (exit={proc.returncode}).")
        _TF_GPU_PROBE_CACHE[cache_key] = result
        return result

    result = (gpu_count > 0, f"TensorFlow visible GPUs: {gpu_count}")
    _TF_GPU_PROBE_CACHE[cache_key] = result
    return result


def _probe_torch_gpu(conda_env_name: str) -> Tuple[Optional[bool], str]:
    cache_key = str(conda_env_name).strip() or "bsenv"
    if cache_key in _TORCH_GPU_PROBE_CACHE:
        return _TORCH_GPU_PROBE_CACHE[cache_key]

    conda_exe = _resolve_conda_executable()
    cmd = [
        conda_exe,
        "run",
        "-n",
        cache_key,
        "python",
        "-c",
        "import torch; print(int(torch.cuda.is_available())); print(torch.cuda.device_count())",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(_backend_root()),
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except Exception as exc:
        result = (None, f"PyTorch GPU probe failed: {exc}")
        _TORCH_GPU_PROBE_CACHE[cache_key] = result
        return result

    combined = "\n".join([proc.stdout or "", proc.stderr or ""]).strip()
    numbers = []
    for line in combined.splitlines():
        text = line.strip()
        if re.fullmatch(r"\d+", text):
            numbers.append(int(text))

    if proc.returncode != 0 or len(numbers) < 1:
        result = (None, f"PyTorch GPU probe failed in env '{cache_key}' (exit={proc.returncode}).")
        _TORCH_GPU_PROBE_CACHE[cache_key] = result
        return result

    is_available = numbers[-2] if len(numbers) >= 2 else numbers[-1]
    device_count = numbers[-1]
    result = (bool(is_available), f"PyTorch CUDA available={bool(is_available)}, device_count={device_count}")
    _TORCH_GPU_PROBE_CACHE[cache_key] = result
    return result


def _resolve_runtime_choice(method_key: str, requested_gpu: bool, conda_env_name: str) -> Tuple[bool, dict, Optional[str]]:
    framework_by_method = {
        "csea": "tensorflow",
        "ddgae": "torch",
        "cdbne": "torch",
    }
    framework = framework_by_method.get(str(method_key).strip().lower(), "")
    requested = "gpu" if requested_gpu else "cpu"

    if not requested_gpu:
        runtime = {
            "framework": framework or "unknown",
            "requested_device": requested,
            "actual_device": "cpu",
            "fallback": False,
            "probe_message": "GPU disabled by request.",
            "conda_env": conda_env_name,
        }
        return False, runtime, None

    if framework == "tensorflow":
        gpu_ok, probe_msg = _probe_tensorflow_gpu(conda_env_name)
    elif framework == "torch":
        gpu_ok, probe_msg = _probe_torch_gpu(conda_env_name)
    else:
        runtime = {
            "framework": framework or "unknown",
            "requested_device": requested,
            "actual_device": "gpu",
            "fallback": False,
            "probe_message": "No runtime probe configured for this method.",
            "conda_env": conda_env_name,
        }
        return True, runtime, None

    if gpu_ok is True:
        runtime = {
            "framework": framework,
            "requested_device": requested,
            "actual_device": "cuda",
            "fallback": False,
            "probe_message": probe_msg,
            "conda_env": conda_env_name,
        }
        return True, runtime, None

    notice = (
        f"检测到当前运行环境不可用 GPU（{framework}），已自动切换为 CPU 继续执行。"
        f"详情：{probe_msg or 'unknown'}"
    )
    runtime = {
        "framework": framework,
        "requested_device": requested,
        "actual_device": "cpu",
        "fallback": True,
        "probe_message": probe_msg or "",
        "conda_env": conda_env_name,
    }
    return False, runtime, notice


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
        if _is_cancel_requested(run_id):
            raise RuntimeError("Run cancelled by user.")
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
        run_notices = []
        conda_env_name = (
            str(plugin_params.get("_conda_env", "")).strip()
            or {"csea": "bsenv-tf"}.get(method_key)
            or (os.getenv("RUNNER_CONDA_ENV", "bsenv").strip() or "bsenv")
        )
        run.logs = [*(run.logs or []), f"Dispatching method to conda env: {conda_env_name}"]
        db.commit()

        requested_gpu = _as_bool(plugin_params.get("use_gpu", False))
        effective_use_gpu, runtime_info, fallback_notice = _resolve_runtime_choice(
            method_key=method_key,
            requested_gpu=requested_gpu,
            conda_env_name=conda_env_name,
        )
        plugin_params["use_gpu"] = effective_use_gpu
        runtime_line = (
            f"[runtime] framework={runtime_info.get('framework','unknown')}, "
            f"requested={runtime_info.get('requested_device','cpu')}, "
            f"actual={runtime_info.get('actual_device','cpu')}, env={conda_env_name}"
        )
        run.logs = [*(run.logs or []), runtime_line]
        db.commit()
        if fallback_notice:
            run_notices.append(fallback_notice)
            run.logs = [*(run.logs or []), f"[notice] {fallback_notice}"]
            db.commit()

        y_pred = _run_method_in_conda(
            run_id=run_id,
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
        if len(nodes) <= 200:
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
            "notices": run_notices,
            "runtime": runtime_info,
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
            full_error = str(exc)
            error_summary = full_error.splitlines()[0].strip() if full_error else "Run failed"
            is_cancelled = error_summary.lower() == "run cancelled by user."
            run.status = RunStatus.cancelled.value if is_cancelled else RunStatus.failed.value
            run.error = error_summary[:500]
            run.results = {
                "error_detail": full_error,
            }
            run.duration = round(time.time() - started_at, 3)
            run.duration_sec = run.duration
            run.finished_at = datetime.utcnow()
            run.logs = [*(run.logs or []), "Run cancelled" if is_cancelled else "Run failed"]
            db.commit()
    finally:
        _clear_cancel_requested(run_id)
        db.close()


def _resolve_rq_queue_name(run: Run) -> str:
    run_queue = (os.getenv("RUN_QUEUE") or "runs").strip() or "runs"
    cpu_queue = (os.getenv("RUN_QUEUE_CPU") or "").strip()
    gpu_queue = (os.getenv("RUN_QUEUE_GPU") or "").strip()

    # Backward compatibility: if no split queues are configured, keep original single queue behavior.
    if not cpu_queue and not gpu_queue:
        return run_queue

    cpu_queue = cpu_queue or run_queue
    gpu_queue = gpu_queue or cpu_queue

    params = run.params or {}
    run_mode = str(params.get("run_mode", "local") or "local").strip().lower()
    remote = params.get("remote") if isinstance(params.get("remote"), dict) else {}
    remote_ip = str((remote or {}).get("ip", "")).strip()
    if run_mode == "remote" and remote_ip:
        target = re.sub(r"[^a-zA-Z0-9]+", "-", remote_ip).strip("-").lower() or "remote"
        remote_cpu_tpl = (os.getenv("RUN_QUEUE_REMOTE_CPU") or f"remote-{target}-cpu").strip()
        remote_gpu_tpl = (os.getenv("RUN_QUEUE_REMOTE_GPU") or f"remote-{target}-gpu").strip()
        cpu_queue = remote_cpu_tpl.replace("{target}", target)
        gpu_queue = remote_gpu_tpl.replace("{target}", target)

    method_key = str(run.method_id or run.method_key or "").strip().lower()
    requested_gpu = _as_bool(params.get("use_gpu", False))
    method_meta = registry.methods.get(method_key)
    requires_gpu = bool(getattr(method_meta, "requires_gpu", False)) if method_meta else False
    use_gpu_queue = requested_gpu or (requires_gpu and not _as_bool(params.get("force_cpu", False)))
    return gpu_queue if use_gpu_queue else cpu_queue


def _try_enqueue_rq(run_id: str, queue_name: str) -> bool:
    try:
        from redis import Redis
        from rq import Queue
    except Exception:
        return False

    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    selected_queue = str(queue_name).strip() or (os.getenv("RUN_QUEUE", "runs").strip() or "runs")

    try:
        conn = Redis.from_url(redis_url)
        q = Queue(selected_queue, connection=conn)
        q.enqueue("app.runner.mock_runner.execute_run_job", run_id)
        return True
    except Exception:
        return False


def submit_run(run: Run) -> str:
    backend = os.getenv("RUNNER_BACKEND", "auto").lower()
    params = run.params or {}
    run_mode = str(params.get("run_mode", "local") or "local").strip().lower()
    remote = params.get("remote") if isinstance(params.get("remote"), dict) else {}
    remote_ip = str((remote or {}).get("ip", "")).strip()
    remote_requested = run_mode == "remote"
    remote_config_ok = remote_requested and bool(remote_ip)

    if backend in {"inline", "sync"} and not remote_requested:
        _run_pipeline(run.run_id)
        return run.run_id
    if backend in {"inline", "sync"} and remote_requested:
        raise RuntimeError("Remote mode requires RQ backend and cannot run in inline mode.")

    if backend in {"auto", "rq", "redis"}:
        queue_name = _resolve_rq_queue_name(run)
        enqueued = _try_enqueue_rq(run.run_id, queue_name=queue_name)
        if enqueued:
            return run.run_id
        if remote_requested:
            if not remote_config_ok:
                raise RuntimeError("Remote mode requires remote.ip in params.remote.")
            raise RuntimeError("Remote queue unavailable; please check REDIS_URL and remote worker queue binding.")
        if backend in {"rq", "redis"}:
            # Explicitly requested queue backend but unavailable.
            raise RuntimeError("RQ/Redis backend unavailable; please check REDIS_URL and worker status")

    if remote_requested:
        raise RuntimeError("Remote mode requires RQ backend; local thread fallback is disabled for remote runs.")

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
