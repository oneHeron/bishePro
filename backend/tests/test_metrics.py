import pytest

from app import REPO_ROOT  # noqa: F401 - ensure repo root is in sys.path
from core_modules.methods.metrics import MetricEvaluationError, evaluate_metrics


def test_metrics_perfect_partition() -> None:
    nodes = ["0", "1", "2", "3"]
    y_true = ["A", "A", "B", "B"]
    y_pred = [1, 1, 0, 0]
    edges = [("0", "1"), ("2", "3")]

    result = evaluate_metrics(
        metric_keys=["nmi", "acc", "ari", "modularity_q"],
        y_pred=y_pred,
        y_true=y_true,
        graph_edges=edges,
        nodes=nodes,
    )

    assert result["nmi"] == pytest.approx(1.0, rel=1e-6)
    assert result["acc"] == pytest.approx(1.0, rel=1e-6)
    assert result["ari"] == pytest.approx(1.0, rel=1e-6)
    assert result["modularity_q"] == pytest.approx(0.5, rel=1e-6)


def test_metrics_nonideal_partition() -> None:
    nodes = ["0", "1", "2", "3"]
    y_true = ["A", "A", "B", "B"]
    y_pred = [0, 1, 0, 1]
    edges = [("0", "1"), ("2", "3")]

    result = evaluate_metrics(
        metric_keys=["nmi", "acc", "ari", "modularity_q"],
        y_pred=y_pred,
        y_true=y_true,
        graph_edges=edges,
        nodes=nodes,
    )

    assert result["nmi"] == pytest.approx(0.0, abs=1e-6)
    assert result["acc"] == pytest.approx(0.5, rel=1e-6)
    assert result["ari"] == pytest.approx(-0.5, rel=1e-6)
    assert result["modularity_q"] == pytest.approx(-0.5, rel=1e-6)


def test_metric_error_messages_are_clear() -> None:
    with pytest.raises(MetricEvaluationError, match="requires y_true"):
        evaluate_metrics(metric_keys=["nmi"], y_pred=[0, 1], nodes=["0", "1"])

    with pytest.raises(MetricEvaluationError, match="requires graph edges"):
        evaluate_metrics(metric_keys=["modularity_q"], y_pred=[0, 1], nodes=["0", "1"])
