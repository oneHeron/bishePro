import ctypes
import os
import random
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core_modules.methods.base import MethodInputData, MethodPlugin


class CSEAMethodPlugin(MethodPlugin):
    key = "csea"
    name = "CSEA"
    description = "CSEA community detection method for unattributed networks."
    requires_gpu = True

    _DATASET_DEFAULTS = {
        "dolphins": {"clusters": 2, "network_dims": [32, 24, 12]},
        "karate": {"clusters": 2, "network_dims": [24, 18]},
        "strike": {"clusters": 3, "network_dims": [24, 18]},
        "polbooks": {"clusters": 3, "network_dims": [32, 24]},
        "email_eu": {"clusters": 42, "network_dims": [64, 48, 32, 28, 12]},
        "polblogs": {"clusters": 2, "network_dims": [256, 128, 64, 128, 90]},
        "citeseer": {"clusters": 6, "network_dims": [72, 64, 48, 32]},
        "cora": {"clusters": 7, "network_dims": [128, 64, 256]},
        "youtube": {"clusters": 11, "network_dims": [1024, 512, 256, 128, 96]},
    }

    def run(self, data: MethodInputData, seed: int, params: Dict[str, Any]) -> List[int]:
        np, tf = self._import_runtime()
        from sklearn.cluster import KMeans

        if not data.nodes:
            return []

        random.seed(seed)
        np.random.seed(seed)
        tf.random.set_seed(seed)

        dataset_key = str(params.get("dataset_key", "")).strip().lower()
        defaults = self._DATASET_DEFAULTS.get(dataset_key, {})

        network_dims = self._resolve_network_dims(params, defaults)
        if not network_dims:
            network_dims = [32, 24, 12]
        latent_dim = int(max(2, params.get("latent_dim", network_dims[-1])))
        encoder_dims = [int(max(2, x)) for x in network_dims[:-1]]

        use_gpu = self._as_bool(params.get("use_gpu", True))
        train_device = self._resolve_train_device(tf, use_gpu=use_gpu)
        learning_rate = float(params.get("lr", 0.014))
        epochs = max(1, int(params.get("epochs", 50)))
        batch_size = max(1, int(params.get("batch_size", 10)))

        n_nodes = len(data.nodes)
        default_clusters = int(defaults.get("clusters", max(2, int(round(n_nodes ** 0.5)))))
        n_clusters = max(2, min(int(params.get("num_clusters", default_clusters)), n_nodes))

        node_to_idx = {node: idx for idx, node in enumerate(data.nodes)}
        adj = np.zeros((n_nodes, n_nodes), dtype=np.int32)
        for src, dst in data.edges:
            i = node_to_idx.get(src)
            j = node_to_idx.get(dst)
            if i is None or j is None:
                continue
            adj[i, j] = 1
            adj[j, i] = 1

        sim = self._compute_similarity(adj)
        if sim.shape != (n_nodes, n_nodes):
            raise ValueError(f"CSEA similarity shape mismatch: got {sim.shape}, expected {(n_nodes, n_nodes)}")

        embedding = self._variational_auto_encoder(
            tf=tf,
            np=np,
            x=sim,
            encoder_dims=encoder_dims,
            latent_dim=latent_dim,
            lr=learning_rate,
            epochs=epochs,
            batch_size=batch_size,
            train_device=train_device,
        )

        km = KMeans(n_clusters=n_clusters, random_state=seed, n_init=10)
        labels = km.fit_predict(embedding)
        return labels.astype(int).tolist()

    def _import_runtime(self):
        try:
            import numpy as np
            import tensorflow as tf
        except Exception as exc:
            raise RuntimeError("CSEA requires numpy + tensorflow runtime.") from exc
        return np, tf

    def _as_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() not in {"", "0", "false", "no"}
        return bool(value)

    def _resolve_network_dims(self, params: Dict[str, Any], defaults: Dict[str, Any]) -> List[int]:
        raw = params.get("network_dims")
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            dims = [int(x) for x in raw if int(x) > 1]
            if dims:
                return dims

        raw_csv = str(params.get("network_dims_csv", "")).strip()
        if raw_csv:
            dims: List[int] = []
            for item in raw_csv.split(","):
                item = item.strip()
                if not item:
                    continue
                try:
                    value = int(item)
                except ValueError:
                    continue
                if value > 1:
                    dims.append(value)
            if dims:
                return dims

        return [int(x) for x in defaults.get("network_dims", []) if int(x) > 1]

    def _resolve_train_device(self, tf, use_gpu: bool) -> str:
        gpus = tf.config.list_physical_devices("GPU")
        if use_gpu and not gpus:
            return "/CPU:0"

        if use_gpu and gpus:
            for gpu in gpus:
                try:
                    tf.config.experimental.set_memory_growth(gpu, True)
                except RuntimeError:
                    pass
            return "/GPU:0"
        return "/CPU:0"

    def _compute_similarity(self, adj) -> Any:
        method_dir = Path(__file__).resolve().parent / "csea"
        lib = self._load_ktruss_lib(method_dir)
        fn = getattr(lib, "k_truss_cycle", None)
        if fn is None:
            fn = getattr(lib, "_Z13k_truss_cyclePKcS0_", None)
        if fn is None:
            raise RuntimeError("CSEA k-truss shared library missing symbol: k_truss_cycle")
        fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        fn.restype = ctypes.c_int

        with tempfile.TemporaryDirectory(prefix="csea_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "adj.csv"
            output_path = tmp_path / "sim.csv"
            self._save_csv_matrix(adj, input_path)
            ret = fn(str(input_path).encode(), str(output_path).encode())
            if ret < 0:
                raise RuntimeError(f"CSEA k-truss native call failed with code {ret}")
            if not output_path.exists():
                raise RuntimeError("CSEA k-truss native call did not produce output file")
            import numpy as np

            sim = np.loadtxt(str(output_path), delimiter=",", dtype=np.float32)
            if sim.ndim == 1:
                sim = np.expand_dims(sim, axis=0)
            return sim

    def _save_csv_matrix(self, matrix, path: Path) -> None:
        import numpy as np

        np.savetxt(str(path), matrix, fmt="%d", delimiter=",")

    def _load_ktruss_lib(self, method_dir: Path):
        is_win = os.name == "nt"
        candidates = ["k-truss.dll", "k-trussd.dll"] if is_win else ["libk-truss.so", "libk-trussd.so"]
        for name in candidates:
            lib_path = method_dir / name
            if lib_path.exists():
                return ctypes.cdll.LoadLibrary(str(lib_path))
        raise RuntimeError(f"CSEA k-truss shared library not found under {method_dir}")

    def _variational_auto_encoder(
        self,
        tf,
        np,
        x,
        encoder_dims: List[int],
        latent_dim: int,
        lr: float,
        epochs: int,
        batch_size: int,
        train_device: str,
    ):
        from tensorflow.keras import backend as K
        from tensorflow.keras import metrics, optimizers
        from tensorflow.keras.layers import Dense, Input, Lambda
        from tensorflow.keras.models import Model

        if not encoder_dims:
            return x

        rows = x.shape[0]
        dim_input = rows

        def sampling(args):
            z_mean, z_log_var = args
            epsilon_std = 1.0
            batch_l = K.shape(z_mean)[0]
            dim_l = K.int_shape(z_mean)[1]
            epsilon = K.random_normal(shape=(batch_l, dim_l), mean=0.0, stddev=epsilon_std)
            return z_mean + K.exp(0.5 * z_log_var) * epsilon

        with tf.device(train_device):
            input_matrix = Input(shape=(dim_input,))
            activation = "softsign"
            h = Dense(encoder_dims[0], activation=activation)(input_matrix)
            for i in range(1, len(encoder_dims)):
                h = Dense(encoder_dims[i], activation=activation)(h)

            z_mean = Dense(latent_dim)(h)
            z_log_var = Dense(latent_dim)(h)
            z = Lambda(sampling, output_shape=(latent_dim,))([z_mean, z_log_var])

            if len(encoder_dims) == 1:
                decoder_h = Dense(encoder_dims[0], activation=activation)(z)
            else:
                decoder_h = Dense(encoder_dims[-2], activation=activation)(z)
                for i in range(len(encoder_dims) - 3, -1, -1):
                    decoder_h = Dense(encoder_dims[i], activation=activation)(decoder_h)
            x_decoded_mean = Dense(dim_input, activation="softplus")(decoder_h)

            vae = Model(input_matrix, x_decoded_mean)
            encoder = Model(input_matrix, z_mean)
            xent_loss = dim_input * metrics.categorical_crossentropy(input_matrix, x_decoded_mean)
            kl_loss = -0.5 * K.sum(1 + z_log_var - K.square(z_mean) - K.exp(z_log_var), axis=-1)
            vae_loss = K.mean(xent_loss + kl_loss)
            vae.add_loss(vae_loss)
            optimizer = optimizers.Adamax(
                learning_rate=lr,
                beta_1=0.9,
                beta_2=0.999,
                epsilon=1e-7,
                decay=0.0,
            )
            vae.compile(optimizer=optimizer, metrics=["accuracy"])

        x_train = x.astype(np.float32).reshape((len(x), int(np.prod(x.shape[1:]))))
        with tf.device(train_device):
            vae.fit(
                x_train,
                x_train,
                epochs=epochs,
                batch_size=batch_size,
                shuffle=True,
                verbose=0,
            )
            res = encoder.predict(x_train, verbose=0)
        tf.keras.backend.clear_session()
        return res
