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
                   - parts["drawdown_penalty"] - parts["turnover_penalty"]
                   - parts["feature_count_penalty"])
    # daha yuksek sharpe daha yuksek fitness vermeli
    assert calc.calculate(2.0, 0.8, -0.1, 5.0) > fit


def test_fitness_increases_with_sharpe():
    calc = QuantFitnessCalculator()
    assert calc.calculate(2.0, 0.5, -0.1, 5.0) > calc.calculate(0.5, 0.5, -0.1, 5.0)


def test_fitness_decreases_with_drawdown():
    calc = QuantFitnessCalculator()
    assert calc.calculate(1.0, 0.5, -0.05, 5.0) > calc.calculate(1.0, 0.5, -0.5, 5.0)


def test_fitness_decreases_with_turnover():
    calc = QuantFitnessCalculator()
    assert calc.calculate(1.0, 0.5, -0.1, 2.0) > calc.calculate(1.0, 0.5, -0.1, 50.0)


def test_feature_quality_affects_fitness():
    calc = QuantFitnessCalculator()
    assert calc.calculate(1.0, 0.9, -0.1, 5.0) > calc.calculate(1.0, 0.1, -0.1, 5.0)


def test_fitness_weights_config():
    base = QuantFitnessCalculator()
    custom = QuantFitnessCalculator({"sharpe_weight": 0.9, "feature_quality_weight": 0.05,
                                     "drawdown_weight": 0.03, "turnover_weight": 0.02})
    assert custom.weights["sharpe_weight"] == 0.9
    assert custom.calculate(2.0, 0.1, -0.1, 5.0) - custom.calculate(1.0, 0.1, -0.1, 5.0) > \
        base.calculate(2.0, 0.1, -0.1, 5.0) - base.calculate(1.0, 0.1, -0.1, 5.0)


def test_feature_count_penalty_disabled_by_default():
    calc = QuantFitnessCalculator()
    assert calc.count_penalty.get("enabled") is False
    assert calc.calculate(1.0, 0.5, -0.1, 5.0, n_features=100) == \
        calc.calculate(1.0, 0.5, -0.1, 5.0, n_features=3)
    penalized = QuantFitnessCalculator(None, {"enabled": True, "max_features": 5,
                                              "penalty_weight": 0.05})
    assert penalized.calculate(1.0, 0.5, -0.1, 5.0, n_features=10) < \
        penalized.calculate(1.0, 0.5, -0.1, 5.0, n_features=5)


def test_final_holdout_not_used():
    import inspect
    from backend.platform import research
    params = list(inspect.signature(research.optimize).parameters)
    assert "test" not in params and "holdout" not in params
    assert "x_dev" in params and "y_dev" in params
    src = inspect.getsource(research._execute)
    assert src.index("optimization = optimize(") < src.index("forecast = model.predict(x.iloc[b:]")
    assert "DEVELOPMENT_ONLY" in inspect.getsource(research.optimize)


def _mini_spec(**overrides):
    from backend.platform.schema import ExperimentSpec
    base = ExperimentSpec()
    data = base.model_dump()
    data["optimization"] = {**data["optimization"], "algorithm": "genetic",
                            "population": 4, "generations": 1, "min_features": 2,
                            "max_features": 3, **overrides}
    data["models"] = ["ridge"]
    return ExperimentSpec.model_validate(data)


def _mini_dev(n=120):
    import pandas as pd
    rng = np.random.default_rng(0)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    X = pd.DataFrame(rng.normal(size=(n, 4)), columns=["a", "b", "c", "d"], index=idx)
    y = (X["a"].to_numpy() * 0.01 + rng.normal(scale=0.001, size=n))
    return X, y


def test_same_seed_same_initial_population():
    from backend.platform.research import optimize
    X, y = _mini_dev()
    emit = lambda *a, **k: None
    r1 = optimize(X, y, _mini_spec(), 252.0, emit)
    r2 = optimize(X, y, _mini_spec(), 252.0, emit)
    assert r1["best"]["id"] == r2["best"]["id"]
    assert len(r1["candidates"]) == len(r2["candidates"])
    assert r1["reproducibility"]["random_seed"] == r2["reproducibility"]["random_seed"]


def test_ga_breakdown_and_reproducibility():
    from backend.platform.research import optimize
    X, y = _mini_dev()
    out = optimize(X, y, _mini_spec(), 252.0, lambda *a, **k: None)
    best = out["best"]
    assert "fitness_breakdown" in best and "feature_quality" in best
    bd = best["fitness_breakdown"]
    for k in ["candidate_id", "generation", "sharpe", "feature_quality",
              "max_drawdown", "turnover", "fitness"]:
        assert k in bd
    rep = out["reproducibility"]
    for k in ["random_seed", "population_size", "generation_count", "mutation_rate",
              "crossover_rate", "fitness_weights", "feature_universe"]:
        assert k in rep
    assert rep["feature_universe"] == ["a", "b", "c", "d"]


def test_old_ga_behavior_preserved_by_default():
    from backend.platform.research import optimize
    X, y = _mini_dev()
    emit = lambda *a, **k: None
    out_old = optimize(X, y, _mini_spec(use_quant_fitness=False), 252.0, emit)
    out_new = optimize(X, y, _mini_spec(use_quant_fitness=True), 252.0, emit)
    # Her ikisi de breakdown kaydeder; ranking modu farklı olabilir ama şema aynı.
    assert "fitness_breakdown" in out_old["best"]
    assert "fitness_breakdown" in out_new["best"]
    assert out_old["reproducibility"]["use_quant_fitness"] is False
    assert out_new["reproducibility"]["use_quant_fitness"] is True
