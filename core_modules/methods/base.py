from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class MethodInputData:
    nodes: List[str]
    edges: List[Tuple[str, str]]
    features: Optional[List[List[float]]] = None
    labels: Optional[List[str]] = None


class MethodPlugin(ABC):
    key: str
    name: str
    description: str
    requires_gpu: bool = False

    @abstractmethod
    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        raise NotImplementedError
