from typing import Any, Dict, List, Tuple

from .config import GNNTemplateConfig
from .data import build_edge_index, ensure_feature_matrix
from .model import GNNTemplateModel
from .utils import resolve_device, seed_everything


def train_and_predict(
    *,
    nodes: List[str],
    edges: List[Tuple[str, str]],
    features: List[List[float]],
    config: GNNTemplateConfig,
    seed: int,
) -> List[int]:
    if not nodes:
        return []

    try:
        import torch
    except Exception as exc:
        raise RuntimeError(
            "GNN-Template requires PyTorch. Install torch in backend environment first."
        ) from exc

    seed_everything(seed, torch_module=torch)
    device = resolve_device(torch_module=torch, use_gpu=config.use_gpu)
    if config.use_gpu and device != "cuda":
        raise RuntimeError(
            "GNN-Template requested GPU (use_gpu=true) but CUDA is unavailable. "
            "Set params.use_gpu=false to run on CPU."
        )

    # Build graph tensors/features here (placeholder form).
    _src_idx, _dst_idx = build_edge_index(nodes, edges)
    feats = ensure_feature_matrix(features, len(nodes))

    model = GNNTemplateModel(num_clusters=config.num_clusters)
    y_pred = model.fit_predict(feats, seed=seed)

    if len(y_pred) != len(nodes):
        raise RuntimeError(
            f"GNN-Template produced {len(y_pred)} labels for {len(nodes)} nodes"
        )

    return [int(v) for v in y_pred]


def explain_required_params() -> Dict[str, Any]:
    return {
        "num_clusters": "int, required for supervised comparison baseline",
        "hidden_dim": "int, GNN hidden size",
        "num_layers": "int, number of graph layers",
        "dropout": "float in [0,1)",
        "lr": "float learning rate",
        "weight_decay": "float",
        "epochs": "int",
        "use_gpu": "bool",
    }
