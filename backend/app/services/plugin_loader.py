from core_modules.datasets import builtin as datasets_builtin
from core_modules.methods import builtin as methods_builtin
from core_modules.methods.metrics import register_builtin_metrics
from core_modules.registry import registry


def load_builtin_plugins() -> None:
    registry.clear()
    methods_builtin.register()
    datasets_builtin.register()
    register_builtin_metrics()
