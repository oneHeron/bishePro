from typing import Dict, Optional

from app.models.schemas import DatasetInfo, MethodInfo, MetricInfo
from core_modules.methods.base import MethodPlugin


class PluginRegistry:
    def __init__(self) -> None:
        self.methods: Dict[str, MethodInfo] = {}
        self.method_plugins: Dict[str, MethodPlugin] = {}
        self.datasets: Dict[str, DatasetInfo] = {}
        self.metrics: Dict[str, MetricInfo] = {}

    def register_method(self, item: MethodInfo, plugin: Optional[MethodPlugin] = None) -> None:
        self.methods[item.key] = item
        if plugin is not None:
            self.method_plugins[item.key] = plugin

    def register_dataset(self, item: DatasetInfo) -> None:
        self.datasets[item.key] = item

    def register_metric(self, item: MetricInfo) -> None:
        self.metrics[item.key] = item

    def clear(self) -> None:
        self.methods.clear()
        self.method_plugins.clear()
        self.datasets.clear()
        self.metrics.clear()


registry = PluginRegistry()
