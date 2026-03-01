from typing import Any, Dict, List

from core_modules.methods.base import MethodInputData, MethodPlugin

from .config import GNNTemplateConfig
from .trainer import train_and_predict


class GNNTemplatePlugin(MethodPlugin):
    key = "gnn_template"
    name = "GNN-Template"
    description = "Template for complex GPU-enabled neural community detection methods."
    requires_gpu = True

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        cfg = GNNTemplateConfig.from_params(params, n_nodes=len(data.nodes))
        features = data.features or []

        return train_and_predict(
            nodes=data.nodes,
            edges=data.edges,
            features=features,
            config=cfg,
            seed=seed,
        )
