from datetime import datetime, timezone
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_user
from app.db import get_db
from app.models.db_models import Run, User
from app.models.schemas import (
    RunCreateRequest,
    RunCreateResponse,
    RunDeleteRequest,
    RunDeleteResponse,
    RunRecord,
    RunResultsResponse,
    RunStatus,
)
from core_modules.registry import registry
from app.runner.mock_runner import build_version_info, submit_run

router = APIRouter(prefix="/runs", tags=["runs"])


def _to_epoch_ms(dt: Optional[datetime]) -> Optional[int]:
    if dt is None:
        return None
    # DB stores naive UTC datetimes; interpret them explicitly as UTC before timestamp conversion.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _validate_run(payload: RunCreateRequest) -> None:
    if payload.method_key not in registry.methods:
        raise HTTPException(status_code=400, detail=f"Unknown method: {payload.method_key}")
    if payload.dataset_key not in registry.datasets:
        raise HTTPException(status_code=400, detail=f"Unknown dataset: {payload.dataset_key}")

    missing_metrics = [m for m in payload.metric_keys if m not in registry.metrics]
    if missing_metrics:
        raise HTTPException(status_code=400, detail=f"Unknown metrics: {missing_metrics}")

    dataset = registry.datasets[payload.dataset_key]
    if payload.method_key == "ddgae":
        if payload.dataset_key not in {"cora", "citeseer"}:
            raise HTTPException(
                status_code=400,
                detail="Method DDGAE currently supports only datasets: cora, citeseer",
            )
        if not dataset.has_features:
            raise HTTPException(
                status_code=400,
                detail=f"Method DDGAE requires node features, but dataset {dataset.name} has no features",
            )
    if payload.method_key == "cdbne":
        if payload.dataset_key not in {"cora", "citeseer"}:
            raise HTTPException(
                status_code=400,
                detail="Method CDBNE currently supports only datasets: cora, citeseer",
            )
        if not dataset.has_features:
            raise HTTPException(
                status_code=400,
                detail=f"Method CDBNE requires node features, but dataset {dataset.name} has no features",
            )

    for metric_key in payload.metric_keys:
        metric = registry.metrics[metric_key]
        if metric.requires_labels and not dataset.has_labels:
            raise HTTPException(
                status_code=400,
                detail=f"Metric {metric.name} requires labels, but dataset {dataset.name} has no labels",
            )


@router.post("", response_model=RunCreateResponse)
def create_run(
    payload: RunCreateRequest,
    username: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> RunCreateResponse:
    _validate_run(payload)
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")

    run_id = _generate_run_id(db)
    record = Run(
        run_id=run_id,
        user_id=user.id,
        method_id=payload.method_key,
        dataset_id=payload.dataset_key,
        metrics=payload.metric_keys,
        method_key=payload.method_key,
        dataset_key=payload.dataset_key,
        metric_keys=payload.metric_keys,
        seed=payload.seed,
        params=payload.params,
        status=RunStatus.pending.value,
        logs=["Run submitted"],
        version_info=build_version_info(),
    )
    db.add(record)
    db.commit()
    submit_run(record)
    return RunCreateResponse(run_id=run_id)


def _generate_run_id(db: Session) -> str:
    # Human-readable run id: rYYYYMMDD-HHMMSS-<suffix>
    for _ in range(10):
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        suffix = uuid.uuid4().hex[:6]
        run_id = f"r{ts}-{suffix}"
        exists = db.query(Run.run_id).filter(Run.run_id == run_id).first()
        if not exists:
            return run_id
    return f"r{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:10]}"


@router.get("/me", response_model=List[RunRecord])
def get_my_runs(username: str = Depends(require_user), db: Session = Depends(get_db)) -> List[RunRecord]:
    rows = (
        db.query(Run, User.username)
        .join(User, Run.user_id == User.id)
        .filter(User.username == username)
        .order_by(Run.created_at.desc())
        .all()
    )
    return [_to_schema(run=row[0], username=row[1]) for row in rows]


@router.delete("/{run_id}", response_model=RunDeleteResponse)
def delete_run(run_id: str, username: str = Depends(require_user), db: Session = Depends(get_db)) -> RunDeleteResponse:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")

    run = db.query(Run).filter(Run.run_id == run_id, Run.user_id == user.id).first()
    if not run:
        return RunDeleteResponse(deleted=0, not_found=[run_id])
    if run.status in {RunStatus.pending.value, RunStatus.running.value}:
        return RunDeleteResponse(deleted=0, blocked_running=[run_id])

    db.delete(run)
    db.commit()
    return RunDeleteResponse(deleted=1)


@router.post("/batch-delete", response_model=RunDeleteResponse)
def batch_delete_runs(
    payload: RunDeleteRequest,
    username: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> RunDeleteResponse:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")

    run_ids = [str(x).strip() for x in payload.run_ids if str(x).strip()]
    if not run_ids:
        return RunDeleteResponse()

    rows = db.query(Run).filter(Run.user_id == user.id, Run.run_id.in_(run_ids)).all()
    found_map = {row.run_id: row for row in rows}

    deleted = 0
    blocked_running: List[str] = []
    not_found: List[str] = []

    for run_id in run_ids:
        row = found_map.get(run_id)
        if not row:
            not_found.append(run_id)
            continue
        if row.status in {RunStatus.pending.value, RunStatus.running.value}:
            blocked_running.append(run_id)
            continue
        db.delete(row)
        deleted += 1

    db.commit()
    return RunDeleteResponse(deleted=deleted, blocked_running=blocked_running, not_found=not_found)


@router.get("/{run_id}")
def get_run(run_id: str, username: str = Depends(require_user), db: Session = Depends(get_db)) -> Dict:
    row = (
        db.query(Run, User.username)
        .join(User, Run.user_id == User.id)
        .filter(Run.run_id == run_id)
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    run, owner_name = row
    if owner_name != username:
        raise HTTPException(status_code=403, detail="You are not allowed to access this run")

    return _to_schema(run=run, username=owner_name).model_dump()


@router.get("/{run_id}/results", response_model=RunResultsResponse)
def get_run_results(run_id: str, username: str = Depends(require_user), db: Session = Depends(get_db)) -> RunResultsResponse:
    row = (
        db.query(Run, User.username)
        .join(User, Run.user_id == User.id)
        .filter(Run.run_id == run_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    run, owner_name = row
    if owner_name != username:
        raise HTTPException(status_code=403, detail="You are not allowed to access this run")

    raw_results = run.results or {}
    metrics = (
        raw_results.get("metrics")
        if isinstance(raw_results, dict)
        else (run.metrics_result if isinstance(run.metrics_result, dict) else None)
    )
    community_assignment = raw_results.get("community_assignment") if isinstance(raw_results, dict) else None
    node_count = raw_results.get("node_count") if isinstance(raw_results, dict) else None

    return RunResultsResponse(
        run_id=run.run_id,
        status=RunStatus(run.status),
        metrics=metrics,
        community_assignment=community_assignment,
        node_count=node_count,
        results=raw_results if isinstance(raw_results, dict) else None,
        duration=run.duration if run.duration is not None else run.duration_sec,
        error=run.error,
        started_at_ts=_to_epoch_ms(run.started_at),
        finished_at_ts=_to_epoch_ms(run.finished_at),
    )


def _to_schema(run: Run, username: str) -> RunRecord:
    return RunRecord(
        run_id=run.run_id,
        user=username,
        method_id=run.method_id or run.method_key,
        dataset_id=run.dataset_id or run.dataset_key,
        metrics=run.metrics or run.metric_keys or [],
        method_key=run.method_key,
        dataset_key=run.dataset_key,
        metric_keys=run.metric_keys or [],
        seed=run.seed,
        params=run.params or {},
        status=RunStatus(run.status),
        logs=run.logs or [],
        duration_sec=run.duration if run.duration is not None else run.duration_sec,
        metrics_result=(
            run.results.get("metrics")
            if isinstance(run.results, dict) and isinstance(run.results.get("metrics"), dict)
            else run.metrics_result
        ),
        results=run.results if isinstance(run.results, dict) else None,
        error=run.error,
        version_info=run.version_info or {},
        created_at_ts=_to_epoch_ms(run.created_at),
        updated_at_ts=_to_epoch_ms(run.updated_at),
        started_at_ts=_to_epoch_ms(run.started_at),
        finished_at_ts=_to_epoch_ms(run.finished_at),
    )
