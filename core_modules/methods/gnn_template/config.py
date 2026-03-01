from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class GNNTemplateConfig:
    num_clusters: int = 4
    hidden_dim: int = 64
    num_layers: int = 2
    dropout: float = 0.3
    lr: float = 1e-3
    weight_decay: float = 1e-5
    epochs: int = 200
    use_gpu: bool = True

    @classmethod
    def from_params(cls, params: Dict[str, Any], n_nodes: int) -> "GNNTemplateConfig":
        cfg = cls(
            num_clusters=max(2, min(int(params.get("num_clusters", 4)), max(2, n_nodes))),
            hidden_dim=max(8, int(params.get("hidden_dim", 64))),
            num_layers=max(1, int(params.get("num_layers", 2))),
            dropout=float(params.get("dropout", 0.3)),
            lr=float(params.get("lr", 1e-3)),
            weight_decay=float(params.get("weight_decay", 1e-5)),
            epochs=max(1, int(params.get("epochs", 200))),
            use_gpu=bool(params.get("use_gpu", True)),
        )
        if cfg.dropout < 0 or cfg.dropout >= 1:
            raise ValueError("dropout must be in [0, 1)")
        return cfg
