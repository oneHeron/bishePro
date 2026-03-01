import random
from typing import Optional


def seed_everything(seed: int, torch_module: Optional[object] = None) -> None:
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except Exception:
        pass

    if torch_module is None:
        return
    torch_module.manual_seed(seed)
    if hasattr(torch_module, "cuda") and torch_module.cuda.is_available():
        torch_module.cuda.manual_seed_all(seed)


def resolve_device(torch_module: object, use_gpu: bool) -> str:
    if use_gpu and hasattr(torch_module, "cuda") and torch_module.cuda.is_available():
        return "cuda"
    return "cpu"
