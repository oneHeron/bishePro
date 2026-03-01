import json
import sys
from typing import Any, Dict
import argparse

from app.services.plugin_loader import load_builtin_plugins
from core_modules.methods.base import MethodInputData
from core_modules.registry import registry


def _fail(message: str, exit_code: int = 2) -> int:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False))
    return exit_code


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _read_payload(args: argparse.Namespace) -> str:
    if args.payload_file:
        with open(args.payload_file, "r", encoding="utf-8") as fp:
            return fp.read()
    return sys.stdin.read()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-file", default="", help="Path to JSON payload file.")
    args = parser.parse_args()

    raw = _read_payload(args)
    if not raw.strip():
        return _fail("Empty payload received by method subprocess")

    try:
        payload = json.loads(raw)
    except Exception as exc:
        return _fail(f"Invalid JSON payload: {exc}")

    method_key = str(payload.get("method_key", "")).strip().lower()
    if not method_key:
        return _fail("Missing method_key")

    nodes = payload.get("nodes") or []
    edges = payload.get("edges") or []
    features = payload.get("features")
    labels = payload.get("labels")
    seed = int(payload.get("seed", 42))
    params = _as_dict(payload.get("params"))

    load_builtin_plugins()
    plugin = registry.method_plugins.get(method_key)
    if plugin is None:
        return _fail(f"Method plugin not found for key: {method_key}")

    try:
        y_pred = plugin.run(
            data=MethodInputData(nodes=nodes, edges=edges, features=features, labels=labels),
            seed=seed,
            params=params,
        )
    except Exception as exc:
        return _fail(str(exc))

    try:
        normalized = [int(x) for x in y_pred]
    except Exception:
        return _fail("Method output is not a valid label list")

    print(json.dumps({"ok": True, "y_pred": normalized}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
