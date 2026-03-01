import math
import random
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from app.models.schemas import MetricInfo
from core_modules.registry import registry


class MetricEvaluationError(ValueError):
    pass


MetricFn = Callable[[Optional[Sequence[str]], Sequence[int], Optional[List[Tuple[str, str]]], Sequence[str]], float]


# Single metrics module shared by all methods.
METRIC_CATALOG: Dict[str, MetricInfo] = {
    "nmi": MetricInfo(
        key="nmi",
        name="NMI",
        requires_labels=True,
        description="Normalized mutual information.",
    ),
    "acc": MetricInfo(
        key="acc",
        name="ACC",
        requires_labels=True,
        description="Clustering accuracy.",
    ),
    "ari": MetricInfo(
        key="ari",
        name="ARI",
        requires_labels=True,
        description="Adjusted Rand index.",
    ),
    "modularity_q": MetricInfo(
        key="modularity_q",
        name="Modularity Q",
        requires_labels=False,
        description="Graph modularity score.",
    ),
}


def register_builtin_metrics() -> None:
    for metric in METRIC_CATALOG.values():
        registry.register_metric(metric)


def evaluate_metrics(
    metric_keys: List[str],
    y_pred: Sequence[int],
    y_true: Optional[Sequence[str]] = None,
    graph_edges: Optional[List[Tuple[str, str]]] = None,
    nodes: Optional[Sequence[str]] = None,
) -> Dict[str, float]:
    if not y_pred:
        raise MetricEvaluationError("y_pred is empty; method output is required for metric evaluation")

    if nodes is None:
        nodes = [str(i) for i in range(len(y_pred))]

    if len(nodes) != len(y_pred):
        raise MetricEvaluationError("nodes and y_pred length mismatch")

    metric_impl: Dict[str, MetricFn] = {
        "nmi": _metric_nmi,
        "acc": _metric_acc,
        "ari": _metric_ari,
        "modularity_q": _metric_modularity_q,
    }

    result: Dict[str, float] = {}
    for key in metric_keys:
        if key not in metric_impl:
            raise MetricEvaluationError(f"Unsupported metric: {key}")

        metric = METRIC_CATALOG.get(key)
        if metric and metric.requires_labels and y_true is None:
            raise MetricEvaluationError(f"Metric '{key}' requires y_true, but labels are missing")

        try:
            value = metric_impl[key](y_true, y_pred, graph_edges, nodes)
        except MetricEvaluationError:
            raise
        except Exception as exc:
            raise MetricEvaluationError(f"Metric '{key}' evaluation failed: {exc}") from exc
        result[key] = round(float(value), 6)

    return result


def mock_predict(nodes: Sequence[str], y_true: Optional[Sequence[str]], seed: int) -> List[int]:
    if not nodes:
        raise MetricEvaluationError("Dataset has no nodes; cannot generate prediction")

    if y_true:
        k = max(2, len(set(y_true)))
    else:
        k = max(2, min(8, int(math.sqrt(len(nodes))) or 2))

    rng = random.Random(seed)
    return [rng.randint(0, k - 1) for _ in nodes]


def _metric_nmi(
    y_true: Optional[Sequence[str]],
    y_pred: Sequence[int],
    _graph_edges: Optional[List[Tuple[str, str]]],
    _nodes: Sequence[str],
) -> float:
    true_labels = _require_y_true(y_true)
    _validate_equal_length(true_labels, y_pred, "nmi")

    contingency, true_ids, pred_ids = _contingency_table(true_labels, y_pred)
    n = len(y_pred)
    if n == 0:
        raise MetricEvaluationError("Metric 'nmi' got empty labels")

    row_sums = [sum(row) for row in contingency]
    col_sums = [sum(contingency[i][j] for i in range(len(contingency))) for j in range(len(contingency[0]))]

    mi = 0.0
    for i in range(len(true_ids)):
        for j in range(len(pred_ids)):
            nij = contingency[i][j]
            if nij == 0:
                continue
            mi += (nij / n) * math.log((nij * n) / (row_sums[i] * col_sums[j]))

    h_true = -sum((v / n) * math.log(v / n) for v in row_sums if v > 0)
    h_pred = -sum((v / n) * math.log(v / n) for v in col_sums if v > 0)

    if h_true + h_pred == 0:
        return 1.0
    return 2.0 * mi / (h_true + h_pred)


def _metric_ari(
    y_true: Optional[Sequence[str]],
    y_pred: Sequence[int],
    _graph_edges: Optional[List[Tuple[str, str]]],
    _nodes: Sequence[str],
) -> float:
    true_labels = _require_y_true(y_true)
    _validate_equal_length(true_labels, y_pred, "ari")

    contingency, true_ids, pred_ids = _contingency_table(true_labels, y_pred)
    n = len(y_pred)
    if n < 2:
        return 1.0

    sum_comb = 0.0
    for i in range(len(true_ids)):
        for j in range(len(pred_ids)):
            sum_comb += _comb2(contingency[i][j])

    row_sums = [sum(row) for row in contingency]
    col_sums = [sum(contingency[i][j] for i in range(len(contingency))) for j in range(len(contingency[0]))]

    sum_row = sum(_comb2(v) for v in row_sums)
    sum_col = sum(_comb2(v) for v in col_sums)
    total_pairs = _comb2(n)

    expected = (sum_row * sum_col) / total_pairs if total_pairs else 0.0
    max_index = 0.5 * (sum_row + sum_col)
    denom = max_index - expected
    if denom == 0:
        return 1.0
    return (sum_comb - expected) / denom


def _metric_acc(
    y_true: Optional[Sequence[str]],
    y_pred: Sequence[int],
    _graph_edges: Optional[List[Tuple[str, str]]],
    _nodes: Sequence[str],
) -> float:
    true_labels = _require_y_true(y_true)
    _validate_equal_length(true_labels, y_pred, "acc")

    true_idx, true_classes = _factorize(true_labels)
    pred_idx, pred_classes = _factorize(list(y_pred))

    rows = max(len(pred_classes), 1)
    cols = max(len(true_classes), 1)
    weight = [[0 for _ in range(cols)] for _ in range(rows)]

    for t, p in zip(true_idx, pred_idx):
        weight[p][t] += 1

    matched = _hungarian_max(weight)
    return matched / len(y_pred)


def _metric_modularity_q(
    _y_true: Optional[Sequence[str]],
    y_pred: Sequence[int],
    graph_edges: Optional[List[Tuple[str, str]]],
    nodes: Sequence[str],
) -> float:
    if graph_edges is None:
        raise MetricEvaluationError("Metric 'modularity_q' requires graph edges")

    community_by_node: Dict[str, int] = {}
    for idx, node in enumerate(nodes):
        community_by_node[node] = int(y_pred[idx])

    if not graph_edges:
        raise MetricEvaluationError("Metric 'modularity_q' received empty graph")

    degree: Dict[str, int] = {}
    internal_edges: Dict[int, int] = {}
    degree_sum_by_community: Dict[int, int] = {}
    m = 0

    for src, dst in graph_edges:
        if src not in community_by_node or dst not in community_by_node:
            raise MetricEvaluationError(
                "Metric 'modularity_q' failed because graph nodes are missing in y_pred"
            )
        m += 1
        degree[src] = degree.get(src, 0) + 1
        degree[dst] = degree.get(dst, 0) + 1

        c_src = community_by_node[src]
        c_dst = community_by_node[dst]
        if c_src == c_dst:
            internal_edges[c_src] = internal_edges.get(c_src, 0) + 1

    if m == 0:
        raise MetricEvaluationError("Metric 'modularity_q' cannot run on graph with zero edges")

    for node, deg in degree.items():
        c = community_by_node[node]
        degree_sum_by_community[c] = degree_sum_by_community.get(c, 0) + deg

    q = 0.0
    for community, d_c in degree_sum_by_community.items():
        l_c = internal_edges.get(community, 0)
        q += (l_c / m) - (d_c / (2.0 * m)) ** 2

    return q


def _require_y_true(y_true: Optional[Sequence[str]]) -> Sequence[str]:
    if y_true is None:
        raise MetricEvaluationError("labels are required but y_true is missing")
    return y_true


def _validate_equal_length(y_true: Sequence[str], y_pred: Sequence[int], metric_key: str) -> None:
    if len(y_true) != len(y_pred):
        raise MetricEvaluationError(
            f"Metric '{metric_key}' requires y_true and y_pred with same length, "
            f"got {len(y_true)} and {len(y_pred)}"
        )


def _factorize(values: Sequence[object]) -> Tuple[List[int], List[object]]:
    mapping: Dict[object, int] = {}
    ids: List[int] = []
    classes: List[object] = []
    for value in values:
        if value not in mapping:
            mapping[value] = len(mapping)
            classes.append(value)
        ids.append(mapping[value])
    return ids, classes


def _contingency_table(y_true: Sequence[str], y_pred: Sequence[int]) -> Tuple[List[List[int]], List[object], List[object]]:
    true_idx, true_classes = _factorize(y_true)
    pred_idx, pred_classes = _factorize(list(y_pred))

    table = [[0 for _ in range(len(pred_classes))] for _ in range(len(true_classes))]
    for t, p in zip(true_idx, pred_idx):
        table[t][p] += 1
    return table, true_classes, pred_classes


def _comb2(n: int) -> float:
    return 0.0 if n < 2 else float(n * (n - 1) / 2)


def _hungarian_max(weight: List[List[int]]) -> int:
    n = len(weight)
    m = len(weight[0]) if n else 0
    size = max(n, m)
    if size == 0:
        return 0

    padded = [[0 for _ in range(size)] for _ in range(size)]
    max_w = 0
    for i in range(n):
        for j in range(m):
            w = weight[i][j]
            padded[i][j] = w
            max_w = max(max_w, w)

    cost = [[max_w - padded[i][j] for j in range(size)] for i in range(size)]

    u = [0 for _ in range(size + 1)]
    v = [0 for _ in range(size + 1)]
    p = [0 for _ in range(size + 1)]
    way = [0 for _ in range(size + 1)]

    for i in range(1, size + 1):
        p[0] = i
        j0 = 0
        minv = [float("inf") for _ in range(size + 1)]
        used = [False for _ in range(size + 1)]
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float("inf")
            j1 = 0
            for j in range(1, size + 1):
                if used[j]:
                    continue
                cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(size + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break

        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    assignment = [-1 for _ in range(size)]
    for j in range(1, size + 1):
        if p[j] > 0:
            assignment[p[j] - 1] = j - 1

    matched = 0
    for i in range(n):
        j = assignment[i]
        if 0 <= j < m:
            matched += weight[i][j]
    return matched
