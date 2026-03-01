from typing import List

from fastapi import APIRouter, HTTPException

from app.datasets import dataset_manager
from app.models.schemas import DatasetInfo, DatasetPreviewResponse, MethodInfo, MetricInfo
from core_modules.registry import registry

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/methods", response_model=List[MethodInfo])
def get_methods() -> List[MethodInfo]:
    return list(registry.methods.values())


@router.get("/datasets", response_model=List[DatasetInfo])
def get_datasets() -> List[DatasetInfo]:
    return dataset_manager.list_dataset_info()


@router.get("/datasets/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def get_dataset_preview(dataset_id: str) -> DatasetPreviewResponse:
    try:
        return dataset_manager.preview(dataset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/metrics", response_model=List[MetricInfo])
def get_metrics() -> List[MetricInfo]:
    return list(registry.metrics.values())
