from app.models.schemas import MethodInfo
from core_modules.methods.plugins import build_method_plugins
from core_modules.registry import registry

METHOD_META = {
    "louvain": {
        "algorithm_note": "基于图拓扑的标签传播式模块度优化流程。",
        "implementation_level": "standard-lite",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "kmeans": {
        "algorithm_note": "对特征或图结构嵌入进行 K-Means 聚类。",
        "implementation_level": "standard-lite",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "nmf": {
        "algorithm_note": "对特征/结构矩阵做 NMF 分解后根据主成分聚类。",
        "implementation_level": "standard-lite",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "deepwalk": {
        "algorithm_note": "随机游走构造节点表示，再执行聚类。",
        "implementation_level": "standard-lite",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "node2vec": {
        "algorithm_note": "带偏置随机游走（BFS/DFS 折中）后聚类。",
        "implementation_level": "approximate",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "sc": {
        "algorithm_note": "谱嵌入后进行聚类。",
        "implementation_level": "approximate",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "kl": {
        "algorithm_note": "KL 图划分启发式（二分优先）。",
        "implementation_level": "approximate",
        "supports_attributed": False,
        "supports_unattributed": True,
    },
    "fn": {
        "algorithm_note": "Fast Newman 风格层次聚合。",
        "implementation_level": "approximate",
        "supports_attributed": False,
        "supports_unattributed": True,
    },
    "mdnp": {
        "algorithm_note": "保留度信息的改进分解方法。",
        "implementation_level": "approximate",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "dnr": {
        "algorithm_note": "结构表示学习后聚类。",
        "implementation_level": "approximate",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "pca": {
        "algorithm_note": "降维后聚类。",
        "implementation_level": "approximate",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "dsacd": {
        "algorithm_note": "稀疏编码特征提取后聚类。",
        "implementation_level": "approximate",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "gn": {
        "algorithm_note": "分裂式社区检测（桥边优先切分）。",
        "implementation_level": "approximate",
        "supports_attributed": False,
        "supports_unattributed": True,
    },
    "le": {
        "algorithm_note": "Laplacian Eigenmaps 风格嵌入后聚类。",
        "implementation_level": "approximate",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "lpa": {
        "algorithm_note": "标签传播社区检测。",
        "implementation_level": "standard-lite",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "cnm": {
        "algorithm_note": "贪心模块度聚合。",
        "implementation_level": "approximate",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "fua": {
        "algorithm_note": "模块度优化启发式算法。",
        "implementation_level": "approximate",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "infomap": {
        "algorithm_note": "信息流压缩思想的随机游走聚类。",
        "implementation_level": "approximate",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "edmot": {
        "algorithm_note": "模体增强边后社区传播。",
        "implementation_level": "approximate",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "cdme": {
        "algorithm_note": "考虑节点度效应的聚类策略。",
        "implementation_level": "approximate",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "gnn_template": {
        "algorithm_note": "复杂神经网络社区检测方法模板（支持 GPU 训练）。",
        "implementation_level": "template",
        "supports_attributed": True,
        "supports_unattributed": True,
    },
    "ddgae": {
        "algorithm_note": "双解码图自编码器 + 聚类细化（默认 CUDA）。",
        "implementation_level": "standard-lite",
        "supports_attributed": True,
        "supports_unattributed": False,
    },
    "cdbne": {
        "algorithm_note": "CDBNE 图嵌入聚类方法（默认 CUDA）。",
        "implementation_level": "standard-lite",
        "supports_attributed": True,
        "supports_unattributed": False,
    },
    "csea": {
        "algorithm_note": "CSEA 无属性网络社区检测方法（基于 k-truss + VAE + KMeans）。",
        "implementation_level": "standard-lite",
        "supports_attributed": False,
        "supports_unattributed": True,
    },
}


def register() -> None:
    for plugin in build_method_plugins():
        meta = METHOD_META.get(plugin.key, {})
        registry.register_method(
            MethodInfo(
                key=plugin.key,
                name=plugin.name,
                requires_gpu=plugin.requires_gpu,
                description=plugin.description,
                algorithm_note=meta.get("algorithm_note", plugin.description),
                implementation_level=meta.get("implementation_level", "approximate"),
                supports_attributed=meta.get("supports_attributed", True),
                supports_unattributed=meta.get("supports_unattributed", True),
            ),
            plugin=plugin,
        )
