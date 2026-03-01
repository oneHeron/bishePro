import os
import re
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

os.environ["DATABASE_URL"] = f"sqlite:////tmp/community_test_{uuid.uuid4().hex}.db"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["DATASETS_ROOT"] = f"/tmp/community_datasets_{uuid.uuid4().hex}"
os.environ["RUNNER_BACKEND"] = "inline"

from app.api.auth import login, register
from app.api.public import get_dataset_preview, get_datasets, get_methods, get_metrics
from app.api.runs import create_run, get_my_runs, get_run_results
from app.core.auth import require_user
from app.db import SessionLocal, Base, engine
from app.models.schemas import LoginRequest, RegisterRequest, RunCreateRequest
from app.services.plugin_loader import load_builtin_plugins


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    load_builtin_plugins()


def test_public_registry_loaded() -> None:
    methods = get_methods()
    datasets = get_datasets()
    metrics = get_metrics()

    assert len(methods) >= 4
    assert len(datasets) >= 9
    assert len(metrics) >= 4
    assert all(item.local_path for item in datasets)


def test_dataset_preview_manual_success_and_missing_file() -> None:
    root = Path(os.environ["DATASETS_ROOT"])
    karate_dir = root / "manual" / "karate"
    karate_dir.mkdir(parents=True, exist_ok=True)
    (karate_dir / "edges.csv").write_text("source,target\n1,2\n2,3\n", encoding="utf-8")
    (karate_dir / "labels.csv").write_text("node,label\n1,A\n2,A\n3,B\n", encoding="utf-8")

    preview = get_dataset_preview("karate")
    assert preview.dataset.key == "karate"
    assert preview.output.graph["num_edges"] == 2
    assert preview.output.labels["num_rows"] == 3

    with pytest.raises(HTTPException) as exc:
        get_dataset_preview("strike")
    assert exc.value.status_code == 400
    assert "missing edges file" in str(exc.value.detail)


def test_auth_and_protected_create_run() -> None:
    db = SessionLocal()
    try:
        reg = register(RegisterRequest(username="alice", password="password123"), db=db)
        log = login(LoginRequest(username="alice", password="password123"), db=db)

        assert reg.username == "alice"
        assert log.token

        assert require_user(f"Bearer {log.token}") == "alice"

        run_id = create_run(
            RunCreateRequest(
                method_key="louvain",
                dataset_key="cora",
                metric_keys=["nmi", "ari", "modularity_q"],
                seed=7,
                params={"resolution": 1.0},
            ),
            username="alice",
            db=db,
        ).run_id
        assert re.match(r"^r\d{8}-\d{6}-[0-9a-f]{6,10}$", run_id)

        runs = get_my_runs(username="alice", db=db)
        assert len(runs) == 1
        assert runs[0].run_id == run_id

        result = get_run_results(run_id=run_id, username="alice", db=db)
        assert result.run_id == run_id
        assert result.status.value in {"pending", "running", "finished", "failed", "cancelled"}
    finally:
        db.close()


def test_require_user_rejects_missing_or_invalid_token() -> None:
    with pytest.raises(HTTPException) as exc:
        require_user("")
    assert exc.value.status_code == 401

    with pytest.raises(HTTPException) as exc:
        require_user("Bearer invalid-token")
    assert exc.value.status_code == 401
