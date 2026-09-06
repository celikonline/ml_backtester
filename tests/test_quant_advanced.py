import numpy as np

from backend.quant.ablation import ablation_report, run_ablation, shap_stability_report
from backend.quant.fitness import QuantFitnessCalculator


class _Dummy:
    def __init__(self, score):
        self.score = score


def test_metrics_generated():
    base = {"sharpe": 1.0, "return": 0.1, "max_drawdown": -0.05}
    ablated = {"f1": {"sharpe": 0.6, "return": 0.05, "max_drawdown": -0.07}}
    df = ablation_report(base, ablated)
    assert list(df.columns) == ["feature", "base_sharpe", "ablation_sharpe",
                                "sharpe_delta", "return_delta", "drawdown_delta"]
    assert df.iloc[0]["sharpe_delta"] == -0.4


def test_feature_removed():
    seen = []

    def train_fn(feats):
        seen.append(tuple(feats))
        return _Dummy(len(feats))

    def metric_fn(model):
        return {"sharpe": model.score / 10, "return": 0.01 * model.score, "max_drawdown": -0.01}

    df = run_ablation(train_fn, metric_fn, {"g1": ["a"], "g2": ["b"]}, ["a", "b", "c"])
    assert set(df["feature"]) == {"g1", "g2"}
    assert all(len(s) == 2 for s in seen[1:])


def test_shap_stability_columns():
    df = shap_stability_report({"a": [0.5, 0.4, 0.6], "b": [0.1, 0.05, 0.08]})
    assert list(df.columns) == ["feature", "mean_shap", "std_shap", "cv_shap",
                                "mean_rank", "rank_std"]
    assert df.iloc[0]["feature"] == "a"


def test_fitness_adapter_weights():
    calc = QuantFitnessCalculator()
    fit = calc.calculate(sharpe=1.0, feature_quality=0.8, max_drawdown=-0.1, turnover=5.0)
    parts = calc.breakdown(sharpe=1.0, feature_quality=0.8, max_drawdown=-0.1, turnover=5.0)
    assert fit == (parts["sharpe_contribution"] + parts["feature_quality_contribution"]
                   - parts["drawdown_penalty"] - parts["turnover_penalty"])
    # daha yuksek sharpe daha yuksek fitness vermeli
    assert calc.calculate(2.0, 0.8, -0.1, 5.0) > fit
