from typing import Dict, List, Tuple


def build_node_index(nodes: List[str]) -> Dict[str, int]:
    return {node: idx for idx, node in enumerate(nodes)}


def build_edge_index(nodes: List[str], edges: List[Tuple[str, str]]) -> Tuple[List[int], List[int]]:
    node2idx = build_node_index(nodes)
    src_idx: List[int] = []
    dst_idx: List[int] = []

    for src, dst in edges:
        if src not in node2idx or dst not in node2idx:
            continue
        s = node2idx[src]
        d = node2idx[dst]
        src_idx.extend([s, d])
        dst_idx.extend([d, s])
    return src_idx, dst_idx


def ensure_feature_matrix(features: List[List[float]], n_nodes: int) -> List[List[float]]:
    if features and len(features) == n_nodes:
        return features

    # Fallback: identity-like feature for topology-only graphs.
    return [[1.0 if i == j else 0.0 for j in range(n_nodes)] for i in range(n_nodes)]
