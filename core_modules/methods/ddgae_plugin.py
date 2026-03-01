from pathlib import Path
from typing import Any, Dict, List, Tuple

from core_modules.methods.base import MethodInputData, MethodPlugin


class DDGAEMethodPlugin(MethodPlugin):
    key = "ddgae"
    name = "DDGAE"
    description = "Dual-decoder graph autoencoder with clustering refinement (CUDA default)."
    requires_gpu = True

    _SUPPORTED_DATASETS = {"cora", "citeseer"}

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        torch = self._import_torch()
        if data.features is None or len(data.features) != len(data.nodes):
            raise ValueError("DDGAE requires feature matrix aligned with all dataset nodes")

        dataset_key = str(params.get("dataset_key", "")).lower().strip()
        if dataset_key and dataset_key not in self._SUPPORTED_DATASETS:
            allowed = ", ".join(sorted(self._SUPPORTED_DATASETS))
            raise ValueError(f"DDGAE currently supports only [{allowed}], got '{dataset_key}'")

        use_gpu = self._as_bool(params.get("use_gpu", True))
        if use_gpu and not torch.cuda.is_available():
            raise RuntimeError("DDGAE defaults to CUDA, but no CUDA device is available. Set `use_gpu=false` to run on CPU.")
        device = torch.device("cuda" if use_gpu else "cpu")

        self._seed_all(torch, seed)

        # Local import to avoid hard dependency at process startup.
        from core_modules.methods.ddgae.model import GAT

        n_nodes = len(data.nodes)
        x = torch.tensor(data.features, dtype=torch.float32, device=device)
        if x.ndim != 2:
            raise ValueError("DDGAE expects 2D features: [num_nodes, num_features]")

        node_to_idx = {node: idx for idx, node in enumerate(data.nodes)}
        adj_label = self._build_dense_adj(torch, n_nodes, data.edges, node_to_idx, device)
        adj = self._normalize_adj(torch, adj_label)
        m_matrix = self._compute_m(torch, adj, t_order=2)
        b_matrix = self._build_modularity_matrix(torch, adj_label)

        dataset_defaults = self._dataset_defaults(dataset_key)
        num_clusters = int(params.get("num_clusters", dataset_defaults["num_clusters"]))
        num_clusters = max(2, min(num_clusters, n_nodes))

        model = _DDGAENetwork(
            gat=GAT(
                num_features=int(x.shape[1]),
                B_dim=int(b_matrix.shape[0]),
                hidden_size=int(params.get("hidden_size", 256)),
                embedding_size=int(params.get("embedding_size", 16)),
                alpha=float(params.get("alpha", 0.2)),
            ),
            num_clusters=num_clusters,
            embedding_size=int(params.get("embedding_size", 16)),
        ).to(device)

        self._try_load_pretrain(torch, model, dataset_key, params)

        lr = float(params.get("lr", dataset_defaults["lr"]))
        weight_decay = float(params.get("weight_decay", 5e-3))
        update_interval = max(1, int(params.get("update_interval", 1)))
        max_epoch = max(1, int(params.get("max_epoch", 200)))
        lambda1 = float(params.get("lambda1", dataset_defaults["lambda1"]))
        beta = float(params.get("beta", dataset_defaults["beta"]))

        optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
        bce = torch.nn.BCELoss()
        mse = torch.nn.MSELoss()
        y_true = data.labels if data.labels and len(data.labels) == n_nodes else None

        with torch.no_grad():
            _, z0, _, _, _, _, _ = model(x, b_matrix, adj, m_matrix)
        _, centers = _kmeans_numpy(z0.detach().cpu().numpy(), num_clusters, seed, max_iter=60)
        model.cluster_layer.data = torch.tensor(centers, dtype=torch.float32, device=device)
        with torch.no_grad():
            _, _, _, _, _, _, q0 = model(x, b_matrix, adj, m_matrix)
        best_pred = q0.argmax(dim=1).detach().cpu().numpy().astype(int).tolist()
        best_loss = float("inf")
        best_acc = -1.0

        for epoch in range(max_epoch):
            model.train()
            a_hat, _, x_hat, b_hat, x_hat2, b_hat2, q = model(x, b_matrix, adj, m_matrix)
            p = _target_distribution(torch, q.detach())
            kl_loss = torch.nn.functional.kl_div(torch.log(q + 1e-10), p, reduction="batchmean")
            re_loss = bce(a_hat.view(-1), adj_label.view(-1))
            x_loss = mse(x_hat, x) + mse(x_hat2, x)
            b_loss = mse(b_hat, b_matrix) + mse(b_hat2, b_matrix)
            loss = (x_loss + b_loss) + (lambda1 * re_loss) + (beta * kl_loss)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            with torch.no_grad():
                pred_now = q.argmax(dim=1).detach().cpu().numpy().astype(int).tolist()
            loss_value = float(loss.detach().cpu().item())
            if y_true is not None:
                acc_now = self._cluster_acc(y_true, pred_now)
                if (acc_now > best_acc) or (acc_now == best_acc and loss_value < best_loss):
                    best_acc = acc_now
                    best_loss = loss_value
                    best_pred = pred_now
            elif loss_value < best_loss:
                best_loss = loss_value
                best_pred = pred_now

            # Keep cluster centers refreshed for stability.
            if (epoch + 1) % update_interval == 0:
                with torch.no_grad():
                    _, z_now, _, _, _, _, _ = model(x, b_matrix, adj, m_matrix)
                _, centers = _kmeans_numpy(
                    z_now.detach().cpu().numpy(),
                    num_clusters,
                    seed + epoch + 1,
                    max_iter=20,
                    return_centers=True,
                )
                model.cluster_layer.data = torch.tensor(centers, dtype=torch.float32, device=device)

        if len(best_pred) != n_nodes:
            raise ValueError(f"DDGAE produced {len(best_pred)} labels for {n_nodes} nodes")
        return best_pred

    def _import_torch(self):
        try:
            import torch
        except Exception as exc:
            raise RuntimeError("DDGAE requires PyTorch. Please install torch (and CUDA build if GPU is needed).") from exc
        return torch

    def _as_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "no", ""}
        return bool(value)

    def _seed_all(self, torch, seed: int) -> None:
        import random

        import numpy as np

        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        if hasattr(torch.backends, "cudnn"):
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False

    def _build_dense_adj(self, torch, n_nodes: int, edges: List[Tuple[str, str]], node_to_idx: Dict[str, int], device):
        adj = torch.zeros((n_nodes, n_nodes), dtype=torch.float32, device=device)
        for src, dst in edges:
            i = node_to_idx.get(src)
            j = node_to_idx.get(dst)
            if i is None or j is None:
                continue
            adj[i, j] = 1.0
            adj[j, i] = 1.0
        return adj

    def _normalize_adj(self, torch, adj_label):
        n = adj_label.shape[0]
        adj = adj_label + torch.eye(n, dtype=torch.float32, device=adj_label.device)
        row_sum = adj.sum(dim=1, keepdim=True).clamp_min(1e-12)
        return adj / row_sum

    def _compute_m(self, torch, adj, t_order: int = 2):
        tran_prob = adj / adj.sum(dim=0, keepdim=True).clamp_min(1e-12)
        accum = torch.zeros_like(tran_prob)
        current = tran_prob
        for _ in range(max(1, t_order)):
            accum = accum + current
            current = current @ tran_prob
        return accum / float(max(1, t_order))

    def _build_modularity_matrix(self, torch, adj_label):
        total_weight = float(adj_label.sum().item())
        if total_weight <= 0.0:
            return adj_label.clone()
        deg = adj_label.sum(dim=1, keepdim=True)
        expected = (deg @ deg.t()) / total_weight
        return adj_label - expected

    def _dataset_defaults(self, dataset_key: str) -> Dict[str, float]:
        if dataset_key == "cora":
            return {"lr": 5e-4, "lambda1": 0.5, "beta": 10.0, "num_clusters": 7}
        if dataset_key == "citeseer":
            return {"lr": 1e-2, "lambda1": 1.0, "beta": 1.0, "num_clusters": 6}
        return {"lr": 1e-3, "lambda1": 0.5, "beta": 10.0, "num_clusters": 4}

    def _cluster_acc(self, y_true: List[str], y_pred: List[int]) -> float:
        true_vals = list(y_true)
        pred_vals = [int(x) for x in y_pred]
        if len(true_vals) != len(pred_vals) or not true_vals:
            return 0.0

        true_unique = sorted(set(true_vals))
        pred_unique = sorted(set(pred_vals))
        true_idx = {v: i for i, v in enumerate(true_unique)}
        pred_idx = {v: i for i, v in enumerate(pred_unique)}

        rows = len(pred_unique)
        cols = len(true_unique)
        w = [[0 for _ in range(cols)] for _ in range(rows)]
        for t, p in zip(true_vals, pred_vals):
            w[pred_idx[p]][true_idx[t]] += 1

        match = self._hungarian_max(w)
        return match / len(pred_vals)

    def _hungarian_max(self, weight: List[List[int]]) -> int:
        n_rows = len(weight)
        n_cols = len(weight[0]) if n_rows else 0
        n = max(n_rows, n_cols)
        if n == 0:
            return 0

        max_w = 0
        for row in weight:
            for val in row:
                if val > max_w:
                    max_w = val

        cost = [[max_w for _ in range(n)] for _ in range(n)]
        for i in range(n_rows):
            for j in range(n_cols):
                cost[i][j] = max_w - weight[i][j]

        u = [0] * (n + 1)
        v = [0] * (n + 1)
        p = [0] * (n + 1)
        way = [0] * (n + 1)

        for i in range(1, n + 1):
            p[0] = i
            j0 = 0
            minv = [float("inf")] * (n + 1)
            used = [False] * (n + 1)
            while True:
                used[j0] = True
                i0 = p[j0]
                delta = float("inf")
                j1 = 0
                for j in range(1, n + 1):
                    if used[j]:
                        continue
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
                for j in range(n + 1):
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

        ans = [0] * (n + 1)
        for j in range(1, n + 1):
            ans[p[j]] = j

        total = 0
        for i in range(1, n_rows + 1):
            j = ans[i]
            if 1 <= j <= n_cols:
                total += weight[i - 1][j - 1]
        return total

    def _try_load_pretrain(self, torch, model, dataset_key: str, params: Dict[str, Any]) -> None:
        if not dataset_key:
            return
        custom_path = params.get("pretrain_path")
        if custom_path:
            path = Path(str(custom_path))
        else:
            name = "Cora" if dataset_key == "cora" else ("Citeseer" if dataset_key == "citeseer" else None)
            if name is None:
                return
            path = Path(__file__).resolve().parent / "ddgae" / "pretrain" / f"pre_ddgae_{name}.pkl"
        if not path.exists():
            return
        try:
            state = torch.load(path, map_location="cpu")
            model.gat.load_state_dict(state, strict=False)
        except Exception:
            # Keep training path available even if pretrain checkpoint cannot be loaded.
            return


class _DDGAENetwork:
    def __init__(self, gat, num_clusters: int, embedding_size: int, v: float = 1.0):
        import torch

        self.gat = gat
        self.num_clusters = num_clusters
        self.v = v
        self.cluster_layer = torch.nn.Parameter(torch.empty((num_clusters, embedding_size)))
        torch.nn.init.xavier_normal_(self.cluster_layer.data)

    def to(self, device):
        self.gat = self.gat.to(device)
        import torch

        self.cluster_layer = torch.nn.Parameter(self.cluster_layer.data.to(device))
        self._params = torch.nn.ParameterList([self.cluster_layer])
        return self

    def parameters(self):
        return list(self.gat.parameters()) + list(self._params.parameters())

    def train(self):
        self.gat.train()

    def eval(self):
        self.gat.eval()

    def __call__(self, x, b_matrix, adj, m_matrix):
        import torch

        a_hat, z, x_hat, b_hat, x_hat2, b_hat2 = self.gat(x, b_matrix, adj, m_matrix)
        q = 1.0 / (1.0 + torch.sum(torch.pow(z.unsqueeze(1) - self.cluster_layer, 2), dim=2) / self.v)
        q = q.pow((self.v + 1.0) / 2.0)
        q = (q.t() / torch.sum(q, dim=1).clamp_min(1e-12)).t()
        return a_hat, z, x_hat, b_hat, x_hat2, b_hat2, q


def _target_distribution(torch, q):
    weight = q.pow(2) / q.sum(dim=0).clamp_min(1e-12)
    return (weight.t() / weight.sum(dim=1).clamp_min(1e-12)).t()


def _kmeans_numpy(data, k: int, seed: int, max_iter: int = 100, return_centers: bool = True):
    import numpy as np

    if data.ndim != 2:
        raise ValueError("kmeans expects 2D matrix")
    n, _ = data.shape
    if n == 0:
        raise ValueError("kmeans got empty input")
    k = max(1, min(int(k), n))

    rng = np.random.default_rng(seed)
    center_idx = rng.choice(n, size=k, replace=False)
    centers = data[center_idx].astype(float).copy()
    labels = np.zeros(n, dtype=int)

    for _ in range(max(1, max_iter)):
        dist2 = ((data[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        new_labels = dist2.argmin(axis=1)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for cluster_id in range(k):
            members = data[labels == cluster_id]
            if len(members) == 0:
                centers[cluster_id] = data[rng.integers(0, n)]
            else:
                centers[cluster_id] = members.mean(axis=0)

    if return_centers:
        return labels.tolist(), centers
    return labels.tolist()
