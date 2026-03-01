from typing import List


class GNNTemplateModel:
    """
    Lightweight placeholder model wrapper.

    You can replace internals with your own GNN stack (e.g. GCN/GAT/GraphSAGE).
    Keep `fit_predict(...) -> List[int]` interface unchanged to minimize integration work.
    """

    def __init__(self, num_clusters: int) -> None:
        self.num_clusters = num_clusters

    def fit_predict(self, embeddings: List[List[float]], seed: int) -> List[int]:
        # Placeholder: simple seeded partition as baseline.
        # Replace this with your neural network forward + clustering head.
        if not embeddings:
            return []
        n = len(embeddings)
        return [int((i + seed) % self.num_clusters) for i in range(n)]
