from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    finished = "finished"
    failed = "failed"


class MethodInfo(BaseModel):
    key: str
    name: str
    requires_gpu: bool = False
    description: str = ""
    algorithm_note: str = ""
    implementation_level: str = "approximate"
    supports_attributed: bool = True
    supports_unattributed: bool = True


class DatasetInfo(BaseModel):
    key: str
    name: str
    has_labels: bool = False
    has_features: bool = False
    description: str = ""
    type: str = "unattributed_network"
    source: str = "manual"
    local_path: str = ""
    hash: Optional[str] = None
    node_count: Optional[int] = None
    edge_count: Optional[int] = None
    community_count: Optional[int] = None
    downloadable: bool = False


class DatasetStandardOutput(BaseModel):
    graph: Dict[str, Any]
    features: Optional[Dict[str, Any]] = None
    labels: Optional[Dict[str, Any]] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class DatasetPreviewResponse(BaseModel):
    dataset: DatasetInfo
    output: DatasetStandardOutput


class MetricInfo(BaseModel):
    key: str
    name: str
    requires_labels: bool = False
    description: str = ""


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    username: str


class RunCreateRequest(BaseModel):
    method_key: str
    dataset_key: str
    metric_keys: List[str]
    seed: int = 42
    params: Dict[str, Any] = Field(default_factory=dict)


class RunCreateResponse(BaseModel):
    run_id: str


class RunDeleteRequest(BaseModel):
    run_ids: List[str] = Field(default_factory=list)


class RunDeleteResponse(BaseModel):
    deleted: int = 0
    blocked_running: List[str] = Field(default_factory=list)
    not_found: List[str] = Field(default_factory=list)


class RunRecord(BaseModel):
    run_id: str
    user: str
    method_id: str
    dataset_id: str
    metrics: List[str]
    method_key: str
    dataset_key: str
    metric_keys: List[str]
    seed: int
    params: Dict[str, Any]
    status: RunStatus
    logs: List[str] = Field(default_factory=list)
    duration_sec: Optional[float] = None
    metrics_result: Optional[Dict[str, float]] = None
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    version_info: Dict[str, str] = Field(default_factory=dict)
    created_at_ts: Optional[int] = None
    updated_at_ts: Optional[int] = None
    started_at_ts: Optional[int] = None
    finished_at_ts: Optional[int] = None


class RunResultsResponse(BaseModel):
    run_id: str
    status: RunStatus
    metrics: Optional[Dict[str, float]] = None
    community_assignment: Optional[List[Dict[str, Any]]] = None
    node_count: Optional[int] = None
    results: Optional[Dict[str, Any]] = None
    duration: Optional[float] = None
    error: Optional[str] = None
    started_at_ts: Optional[int] = None
    finished_at_ts: Optional[int] = None
