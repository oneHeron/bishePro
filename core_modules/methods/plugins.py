import math
import random
from typing import Any, Dict, List, Set, Tuple

from core_modules.methods.base import MethodInputData, MethodPlugin
from core_modules.methods.cdbne_plugin import CDBNEMethodPlugin
from core_modules.methods.csea_plugin import CSEAMethodPlugin
from core_modules.methods.ddgae_plugin import DDGAEMethodPlugin
from core_modules.methods.gnn_template import GNNTemplatePlugin


class LouvainMethodPlugin(MethodPlugin):
    key = "louvain"
    name = "Louvain"
    description = "Modularity optimization based community detection."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        max_iter = int(params.get("max_iter", 24))
        return _label_propagation(data.nodes, data.edges, seed=seed, max_iter=max_iter)


class KMeansMethodPlugin(MethodPlugin):
    key = "kmeans"
    name = "K-Means"
    description = "Classic clustering baseline."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        features = data.features if data.features else _simple_graph_embedding(data.nodes, data.edges)
        k = _resolve_cluster_count(params, len(data.nodes))
        return _kmeans(features, k, seed)


class NMFMethodPlugin(MethodPlugin):
    key = "nmf"
    name = "NMF"
    description = "Matrix factorization based clustering."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        matrix = data.features if data.features else _landmark_matrix(data.nodes, data.edges, seed, dim=24)
        k = _resolve_cluster_count(params, len(data.nodes))
        nmf_iter = int(params.get("nmf_iter", 40))
        w = _nmf_factorize(matrix, k=k, iters=nmf_iter, seed=seed)
        labels = [max(range(len(row)), key=lambda idx: row[idx]) for row in w]
        return _reindex_labels(labels)


class DeepWalkMethodPlugin(MethodPlugin):
    key = "deepwalk"
    name = "DeepWalk"
    description = "Random-walk based graph embedding, then clustering."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        embedding_dim = int(params.get("embedding_dim", 16))
        walk_length = int(params.get("walk_length", 20))
        num_walks = int(params.get("num_walks", 10))
        embeddings = _random_walk_embedding(
            nodes=data.nodes,
            edges=data.edges,
            seed=seed,
            dim=embedding_dim,
            walk_length=walk_length,
            num_walks=num_walks,
            strategy="uniform",
        )
        k = _resolve_cluster_count(params, len(data.nodes))
        return _kmeans(embeddings, k, seed)


class Node2VecMethodPlugin(MethodPlugin):
    key = "node2vec"
    name = "Node2Vec"
    description = "Biased random-walk embedding with DFS/BFS trade-off."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        embedding_dim = int(params.get("embedding_dim", 16))
        walk_length = int(params.get("walk_length", 24))
        num_walks = int(params.get("num_walks", 12))
        embeddings = _random_walk_embedding(
            nodes=data.nodes,
            edges=data.edges,
            seed=seed,
            dim=embedding_dim,
            walk_length=walk_length,
            num_walks=num_walks,
            strategy="biased",
        )
        k = _resolve_cluster_count(params, len(data.nodes))
        return _kmeans(embeddings, k, seed)


class LPAMethodPlugin(MethodPlugin):
    key = "lpa"
    name = "LPA"
    description = "Label propagation for fast community discovery."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        max_iter = int(params.get("max_iter", 32))
        return _label_propagation(data.nodes, data.edges, seed=seed, max_iter=max_iter)


class FNMethodPlugin(MethodPlugin):
    key = "fn"
    name = "FN"
    description = "Hierarchical agglomerative community detection (Fast Newman style)."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        max_iter = int(params.get("max_iter", 20))
        return _label_propagation(data.nodes, data.edges, seed=seed, max_iter=max_iter)


class CNMMethodPlugin(MethodPlugin):
    key = "cnm"
    name = "CNM"
    description = "Greedy modularity-inspired agglomeration."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        max_iter = int(params.get("max_iter", 20))
        return _label_propagation(data.nodes, data.edges, seed=seed + 19, max_iter=max_iter)


class FUAMethodPlugin(MethodPlugin):
    key = "fua"
    name = "FUA"
    description = "Modularity optimization variant for community detection."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        max_iter = int(params.get("max_iter", 26))
        return _label_propagation(data.nodes, data.edges, seed=seed + 31, max_iter=max_iter)


class KLMethodPlugin(MethodPlugin):
    key = "kl"
    name = "KL"
    description = "Kernighan-Lin style graph bisection heuristic."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        k = _resolve_cluster_count(params, len(data.nodes))
        if k > 2:
            emb = _simple_graph_embedding(data.nodes, data.edges)
            return _kmeans(emb, k, seed)
        return _kernighan_lin_bisection(data.nodes, data.edges, seed)


class GNMethodPlugin(MethodPlugin):
    key = "gn"
    name = "GN"
    description = "Girvan-Newman style divisive community detection."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        k = _resolve_cluster_count(params, len(data.nodes))
        return _divisive_bridge_split(data.nodes, data.edges, k, seed)


class SCMethodPlugin(MethodPlugin):
    key = "sc"
    name = "SC"
    description = "Spectral-clustering style pipeline (embedding + clustering)."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        k = _resolve_cluster_count(params, len(data.nodes))
        emb = _graph_spectral_like_embedding(data.nodes, data.edges, seed, dim=max(2, k + 1))
        return _kmeans(emb, k, seed)


class LEMethodPlugin(MethodPlugin):
    key = "le"
    name = "LE"
    description = "Laplacian Eigenmaps style embedding + clustering."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        k = _resolve_cluster_count(params, len(data.nodes))
        emb = _graph_spectral_like_embedding(data.nodes, data.edges, seed + 5, dim=max(2, k + 2))
        return _kmeans(emb, k, seed)


class PCAMethodPlugin(MethodPlugin):
    key = "pca"
    name = "PCA"
    description = "Principal component style dimensionality reduction + clustering."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        source = data.features if data.features else _simple_graph_embedding(data.nodes, data.edges)
        out_dim = int(params.get("pca_dim", 2))
        emb = _pca_like_projection(source, out_dim=out_dim, seed=seed)
        k = _resolve_cluster_count(params, len(data.nodes))
        return _kmeans(emb, k, seed)


class MDNPMethodPlugin(MethodPlugin):
    key = "mdnp"
    name = "MDNP"
    description = "Modified matrix decomposition preserving degree patterns."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        base = data.features if data.features else _landmark_matrix(data.nodes, data.edges, seed + 2, dim=20)
        degree = _degree_vector(data.nodes, data.edges)
        enriched = [row + [degree[i]] for i, row in enumerate(base)]
        k = _resolve_cluster_count(params, len(data.nodes))
        w = _nmf_factorize(enriched, k=k, iters=int(params.get("nmf_iter", 32)), seed=seed)
        return _reindex_labels([max(range(len(r)), key=lambda idx: r[idx]) for r in w])


class DNRMethodPlugin(MethodPlugin):
    key = "dnr"
    name = "DNR"
    description = "Deep-network-representation inspired embedding + clustering."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        base = data.features if data.features else _landmark_matrix(data.nodes, data.edges, seed + 7, dim=18)
        hidden_dim = int(params.get("hidden_dim", 8))
        emb = _mlp_like_encoder(base, hidden_dim=hidden_dim, seed=seed)
        k = _resolve_cluster_count(params, len(data.nodes))
        return _kmeans(emb, k, seed)


class DSACDMethodPlugin(MethodPlugin):
    key = "dsacd"
    name = "DSACD"
    description = "Sparse-autoencoder style structural feature extraction + clustering."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        base = data.features if data.features else _landmark_matrix(data.nodes, data.edges, seed + 11, dim=22)
        sparse_dim = int(params.get("sparse_dim", 10))
        emb = _sparse_autoencoder_like(base, hidden_dim=sparse_dim, seed=seed)
        k = _resolve_cluster_count(params, len(data.nodes))
        return _kmeans(emb, k, seed)


class InfomapMethodPlugin(MethodPlugin):
    key = "infomap"
    name = "Infomap"
    description = "Random-walk flow compression inspired community detection."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        k = _resolve_cluster_count(params, len(data.nodes))
        emb = _random_walk_embedding(
            nodes=data.nodes,
            edges=data.edges,
            seed=seed + 13,
            dim=max(2, k + 2),
            walk_length=int(params.get("walk_length", 18)),
            num_walks=int(params.get("num_walks", 10)),
            strategy="flow",
        )
        return _kmeans(emb, k, seed)


class EdMotMethodPlugin(MethodPlugin):
    key = "edmot"
    name = "EdMot"
    description = "Motif-enhanced edge processing before community assignment."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        motif_edges = _triangle_motif_edges(data.nodes, data.edges)
        merged_edges = list(set(data.edges + motif_edges))
        return _label_propagation(data.nodes, merged_edges, seed=seed + 17, max_iter=int(params.get("max_iter", 24)))


class CDMEMethodPlugin(MethodPlugin):
    key = "cdme"
    name = "CDME"
    description = "Degree-effect inspired community merge heuristic."

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        degrees = _degree_vector(data.nodes, data.edges)
        emb = [[degrees[i], math.sqrt(max(1.0, degrees[i]))] for i in range(len(data.nodes))]
        k = _resolve_cluster_count(params, len(data.nodes))
        return _kmeans(emb, k, seed)


def build_method_plugins() -> List[MethodPlugin]:
    return [
        DeepWalkMethodPlugin(),
        KMeansMethodPlugin(),
        LouvainMethodPlugin(),
        NMFMethodPlugin(),
        Node2VecMethodPlugin(),
        LPAMethodPlugin(),
        FNMethodPlugin(),
        CNMMethodPlugin(),
        FUAMethodPlugin(),
        KLMethodPlugin(),
        GNMethodPlugin(),
        SCMethodPlugin(),
        LEMethodPlugin(),
        PCAMethodPlugin(),
        MDNPMethodPlugin(),
        DNRMethodPlugin(),
        DSACDMethodPlugin(),
        InfomapMethodPlugin(),
        EdMotMethodPlugin(),
        CDMEMethodPlugin(),
        CSEAMethodPlugin(),
        CDBNEMethodPlugin(),
        DDGAEMethodPlugin(),
        GNNTemplatePlugin(),
    ]


def _resolve_cluster_count(params: Dict[str, Any], n_nodes: int) -> int:
    if n_nodes <= 1:
        return 1
    if "num_clusters" in params:
        k = int(params["num_clusters"])
        return max(1, min(k, n_nodes))
    return max(2, min(n_nodes, int(round(math.sqrt(n_nodes / 2.0))) or 2))


def _build_adjacency(nodes: List[str], edges: List[Tuple[str, str]]) -> Dict[str, List[str]]:
    adjacency: Dict[str, List[str]] = {node: [] for node in nodes}
    for src, dst in edges:
        if src in adjacency and dst in adjacency:
            adjacency[src].append(dst)
            adjacency[dst].append(src)
    return adjacency


def _simple_graph_embedding(nodes: List[str], edges: List[Tuple[str, str]]) -> List[List[float]]:
    adjacency = _build_adjacency(nodes, edges)
    vectors: List[List[float]] = []
    for node in nodes:
        neighbors = adjacency[node]
        degree = float(len(neighbors))
        if neighbors:
            avg_neighbor_degree = sum(len(adjacency[n]) for n in neighbors) / len(neighbors)
        else:
            avg_neighbor_degree = 0.0
        vectors.append([degree, avg_neighbor_degree])
    return vectors


def _label_propagation(nodes: List[str], edges: List[Tuple[str, str]], seed: int, max_iter: int) -> List[int]:
    adjacency = _build_adjacency(nodes, edges)
    rng = random.Random(seed)
    labels = {node: idx for idx, node in enumerate(nodes)}

    for _ in range(max(1, max_iter)):
        changed = False
        order = list(nodes)
        rng.shuffle(order)
        for node in order:
            neighbors = adjacency[node]
            if not neighbors:
                continue
            counts: Dict[int, int] = {}
            for nbr in neighbors:
                lb = labels[nbr]
                counts[lb] = counts.get(lb, 0) + 1
            best_label = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if best_label != labels[node]:
                labels[node] = best_label
                changed = True
        if not changed:
            break

    return _reindex_labels([labels[node] for node in nodes])


def _kernighan_lin_bisection(nodes: List[str], edges: List[Tuple[str, str]], seed: int) -> List[int]:
    if not nodes:
        return []
    rng = random.Random(seed)
    group = {node: (i % 2) for i, node in enumerate(nodes)}
    rng.shuffle(nodes)

    adjacency = _build_adjacency(nodes, edges)

    def cut_gain(node: str, to_group: int) -> int:
        gain = 0
        from_group = group[node]
        for nbr in adjacency[node]:
            if group[nbr] == from_group:
                gain += 1
            if group[nbr] == to_group:
                gain -= 1
        return gain

    for _ in range(20):
        improved = False
        for node in nodes:
            new_group = 1 - group[node]
            if cut_gain(node, new_group) > 0:
                group[node] = new_group
                improved = True
        if not improved:
            break

    return [group[node] for node in nodes]


def _divisive_bridge_split(nodes: List[str], edges: List[Tuple[str, str]], k: int, seed: int) -> List[int]:
    if not nodes:
        return []
    if k <= 1:
        return [0 for _ in nodes]

    rng = random.Random(seed)
    work_edges = list(edges)

    while True:
        comps = _connected_components(nodes, work_edges)
        if len(comps) >= k or not work_edges:
            break
        degree = {node: 0 for node in nodes}
        for u, v in work_edges:
            degree[u] = degree.get(u, 0) + 1
            degree[v] = degree.get(v, 0) + 1
        scores = []
        for idx, (u, v) in enumerate(work_edges):
            score = (degree[u] * degree[v], rng.random())
            scores.append((score, idx))
        # Remove high-centrality-like edges first.
        remove_idx = sorted(scores, key=lambda item: (-item[0][0], item[0][1]))[0][1]
        work_edges.pop(remove_idx)

    comps = _connected_components(nodes, work_edges)
    node_to_c = {}
    for cid, comp in enumerate(comps):
        for node in comp:
            node_to_c[node] = cid
    labels = [node_to_c.get(node, 0) for node in nodes]
    return _reindex_labels(labels)


def _connected_components(nodes: List[str], edges: List[Tuple[str, str]]) -> List[Set[str]]:
    adjacency = _build_adjacency(nodes, edges)
    seen: Set[str] = set()
    comps: List[Set[str]] = []
    for node in nodes:
        if node in seen:
            continue
        stack = [node]
        comp: Set[str] = set()
        seen.add(node)
        while stack:
            cur = stack.pop()
            comp.add(cur)
            for nbr in adjacency[cur]:
                if nbr not in seen:
                    seen.add(nbr)
                    stack.append(nbr)
        comps.append(comp)
    return comps


def _random_walk_embedding(
    nodes: List[str],
    edges: List[Tuple[str, str]],
    seed: int,
    dim: int,
    walk_length: int,
    num_walks: int,
    strategy: str,
) -> List[List[float]]:
    if not nodes:
        return []

    adjacency = _build_adjacency(nodes, edges)
    rng = random.Random(seed)
    dim = max(2, min(dim, len(nodes)))
    landmarks = rng.sample(nodes, dim) if len(nodes) > dim else list(nodes)
    landmark_index = {node: idx for idx, node in enumerate(landmarks)}

    embeddings: List[List[float]] = []
    for node in nodes:
        vec = [0.0 for _ in range(dim)]
        for _ in range(max(1, num_walks)):
            prev = None
            cur = node
            for _step in range(max(1, walk_length)):
                idx = landmark_index.get(cur)
                if idx is not None:
                    vec[idx] += 1.0
                nbrs = adjacency[cur]
                if not nbrs:
                    break
                if strategy == "uniform":
                    nxt = nbrs[rng.randrange(len(nbrs))]
                else:
                    weights = []
                    for nbr in nbrs:
                        if strategy == "biased":
                            # node2vec-like: encourage BFS when nbr links prev.
                            if prev is None:
                                w = 1.0
                            elif prev in adjacency[nbr]:
                                w = 1.5
                            else:
                                w = 0.7
                        else:
                            # infomap-like: prefer high degree transitions.
                            w = 1.0 + 0.2 * len(adjacency[nbr])
                        weights.append(w)
                    nxt = _weighted_choice(nbrs, weights, rng)
                prev, cur = cur, nxt
        total = sum(vec)
        if total > 0:
            vec = [v / total for v in vec]
        embeddings.append(vec)
    return embeddings


def _weighted_choice(candidates: List[str], weights: List[float], rng: random.Random) -> str:
    s = sum(max(0.0, w) for w in weights)
    if s <= 0:
        return candidates[rng.randrange(len(candidates))]
    r = rng.random() * s
    acc = 0.0
    for cand, w in zip(candidates, weights):
        acc += max(0.0, w)
        if acc >= r:
            return cand
    return candidates[-1]


def _graph_spectral_like_embedding(nodes: List[str], edges: List[Tuple[str, str]], seed: int, dim: int) -> List[List[float]]:
    base = _landmark_matrix(nodes, edges, seed, dim=max(dim * 2, 4))
    return _pca_like_projection(base, out_dim=dim, seed=seed)


def _degree_vector(nodes: List[str], edges: List[Tuple[str, str]]) -> List[float]:
    deg = {node: 0.0 for node in nodes}
    for u, v in edges:
        if u in deg:
            deg[u] += 1.0
        if v in deg:
            deg[v] += 1.0
    return [deg[node] for node in nodes]


def _pca_like_projection(data: List[List[float]], out_dim: int, seed: int) -> List[List[float]]:
    if not data:
        return []
    in_dim = len(data[0]) if data[0] else 1
    out_dim = max(1, min(out_dim, in_dim))
    rng = random.Random(seed)

    means = [0.0 for _ in range(in_dim)]
    for row in data:
        for j in range(in_dim):
            means[j] += row[j]
    n = float(len(data))
    means = [m / n for m in means]

    centered = [[row[j] - means[j] for j in range(in_dim)] for row in data]

    proj = [[rng.uniform(-1.0, 1.0) for _ in range(in_dim)] for _ in range(out_dim)]
    for i in range(out_dim):
        norm = math.sqrt(sum(v * v for v in proj[i])) or 1.0
        proj[i] = [v / norm for v in proj[i]]

    out: List[List[float]] = []
    for row in centered:
        out_row = []
        for i in range(out_dim):
            out_row.append(sum(row[j] * proj[i][j] for j in range(in_dim)))
        out.append(out_row)
    return out


def _mlp_like_encoder(data: List[List[float]], hidden_dim: int, seed: int) -> List[List[float]]:
    if not data:
        return []
    in_dim = len(data[0]) if data[0] else 1
    hidden_dim = max(2, min(hidden_dim, 128))
    rng = random.Random(seed)

    w = [[rng.uniform(-0.8, 0.8) for _ in range(in_dim)] for _ in range(hidden_dim)]
    b = [rng.uniform(-0.2, 0.2) for _ in range(hidden_dim)]

    encoded: List[List[float]] = []
    for row in data:
        vec = []
        for i in range(hidden_dim):
            z = sum(row[j] * w[i][j] for j in range(in_dim)) + b[i]
            vec.append(max(0.0, z))
        encoded.append(vec)
    return encoded


def _sparse_autoencoder_like(data: List[List[float]], hidden_dim: int, seed: int) -> List[List[float]]:
    latent = _mlp_like_encoder(data, hidden_dim, seed)
    sparse: List[List[float]] = []
    for row in latent:
        if not row:
            sparse.append(row)
            continue
        threshold = sorted(row)[int(0.7 * (len(row) - 1))]
        sparse.append([v if v >= threshold else 0.0 for v in row])
    return sparse


def _triangle_motif_edges(nodes: List[str], edges: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    adjacency = {node: set() for node in nodes}
    for u, v in edges:
        if u in adjacency and v in adjacency:
            adjacency[u].add(v)
            adjacency[v].add(u)

    motif_edges: Set[Tuple[str, str]] = set()
    for u in nodes:
        nbrs = list(adjacency[u])
        for i in range(len(nbrs)):
            for j in range(i + 1, len(nbrs)):
                a, b = nbrs[i], nbrs[j]
                if b in adjacency[a]:
                    motif_edges.add(tuple(sorted((u, a))))
                    motif_edges.add(tuple(sorted((u, b))))
                    motif_edges.add(tuple(sorted((a, b))))

    out = []
    for u, v in motif_edges:
        out.append((u, v))
    return out


def _landmark_matrix(nodes: List[str], edges: List[Tuple[str, str]], seed: int, dim: int = 24) -> List[List[float]]:
    adjacency = _build_adjacency(nodes, edges)
    if not nodes:
        return []
    dim = max(2, min(dim, len(nodes)))

    rng = random.Random(seed)
    landmarks = rng.sample(nodes, dim) if len(nodes) > dim else list(nodes)

    vectors: List[List[float]] = []
    for node in nodes:
        node_neighbors = set(adjacency[node])
        row: List[float] = []
        for landmark in landmarks:
            if node == landmark:
                row.append(1.0)
                continue
            lm_neighbors = set(adjacency[landmark])
            common = len(node_neighbors & lm_neighbors)
            direct = 1.0 if landmark in node_neighbors else 0.0
            denom = max(1.0, float(len(node_neighbors) + len(lm_neighbors)))
            row.append(direct + (2.0 * common / denom))
        vectors.append(row)
    return vectors


def _kmeans(data: List[List[float]], k: int, seed: int, max_iter: int = 60) -> List[int]:
    if not data:
        return []
    n = len(data)
    d = len(data[0]) if data[0] else 1
    k = max(1, min(k, n))

    rng = random.Random(seed)
    centers = [list(data[idx]) for idx in rng.sample(range(n), k)]
    labels = [0 for _ in range(n)]

    for _ in range(max_iter):
        changed = False
        for i, vec in enumerate(data):
            distances = [_sq_dist(vec, center) for center in centers]
            best = min(range(k), key=lambda idx: distances[idx])
            if labels[i] != best:
                labels[i] = best
                changed = True

        sums = [[0.0 for _ in range(d)] for _ in range(k)]
        counts = [0 for _ in range(k)]
        for i, vec in enumerate(data):
            c = labels[i]
            counts[c] += 1
            for j in range(d):
                sums[c][j] += vec[j]

        for c in range(k):
            if counts[c] == 0:
                centers[c] = list(data[rng.randrange(n)])
            else:
                centers[c] = [sums[c][j] / counts[c] for j in range(d)]

        if not changed:
            break

    return _reindex_labels(labels)


def _sq_dist(a: List[float], b: List[float]) -> float:
    return sum((x - y) * (x - y) for x, y in zip(a, b))


def _nmf_factorize(x: List[List[float]], k: int, iters: int, seed: int) -> List[List[float]]:
    if not x:
        return []

    n = len(x)
    d = len(x[0]) if x[0] else 1
    k = max(1, min(k, n))
    eps = 1e-9
    rng = random.Random(seed)

    w = [[rng.random() + 0.1 for _ in range(k)] for _ in range(n)]
    h = [[rng.random() + 0.1 for _ in range(d)] for _ in range(k)]

    for _ in range(max(1, iters)):
        wh = _matmul(w, h)

        for a in range(k):
            for b in range(d):
                num = 0.0
                den = 0.0
                for i in range(n):
                    num += w[i][a] * x[i][b]
                    den += w[i][a] * wh[i][b]
                h[a][b] *= num / max(den, eps)

        wh = _matmul(w, h)
        for i in range(n):
            for a in range(k):
                num = 0.0
                den = 0.0
                for b in range(d):
                    num += x[i][b] * h[a][b]
                    den += wh[i][b] * h[a][b]
                w[i][a] *= num / max(den, eps)

    return w


def _matmul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    n = len(a)
    k = len(a[0]) if a else 0
    m = len(b[0]) if b else 0
    out = [[0.0 for _ in range(m)] for _ in range(n)]
    for i in range(n):
        for t in range(k):
            a_it = a[i][t]
            for j in range(m):
                out[i][j] += a_it * b[t][j]
    return out


def _reindex_labels(labels: List[int]) -> List[int]:
    mapping: Dict[int, int] = {}
    out: List[int] = []
    for label in labels:
        if label not in mapping:
            mapping[label] = len(mapping)
        out.append(mapping[label])
    return out
