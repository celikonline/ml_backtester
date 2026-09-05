import numpy as np
import pytest
from hmmlearn.hmm import GaussianHMM
from backend.engine import backtest, causal_probabilities, demo_prices, features, metrics, read_prices, run_experiment
from backend.app import RunConfig


def test_csv_validation_and_normalization():
    df = demo_prices(500)
    assert len(read_prices(df.to_csv().encode())) == 500
    malformed = df.copy()
    malformed.iloc[0, malformed.columns.get_loc("high")] = 0.2
    with pytest.raises(ValueError, match="OHLC"):
        read_prices(malformed.to_csv().encode())
    with pytest.raises(ValueError, match="Tekrarlanan"):
        read_prices(df.reset_index().assign(timestamp="2024-01-01").to_csv(index=False).encode())
    with pytest.raises(ValueError, match="Eksik"):
        read_prices(b"timestamp,close\n2024-01-01,1.1")


def test_features_do_not_change_when_future_changes():
    original = demo_prices(600)
    modified = original.copy()
    modified.iloc[400:] *= 2
    np.testing.assert_allclose(features(original).loc[:original.index[399]], features(modified).loc[:original.index[399]])


def test_forward_filter_does_not_see_future():
    model = GaussianHMM(n_components=2, covariance_type="diag")
    model.n_features = 1
    model.startprob_ = np.array([0.5, 0.5])
    model.transmat_ = np.array([[0.9, 0.1], [0.1, 0.9]])
    model.means_ = np.array([[-1.0], [1.0]])
    model.covars_ = np.array([[0.5], [0.5]])
    x = np.array([[-0.5], [-0.2], [0.3], [0.9]])
    np.testing.assert_allclose(causal_probabilities(model, x)[:2], causal_probabilities(model, x[:2]))
    np.testing.assert_allclose(causal_probabilities(model, x).sum(axis=1), 1)


def test_costs_charge_reversal_and_final_exit():
    r, s = backtest(np.array([1, 1, -1]), np.array([.01, .01, -.01]), .001)
    np.testing.assert_allclose(r, [.009, .01, .007])
    m = metrics(np.array([-.1, .01]), np.ones(2), 252)
    assert m["max_drawdown"] == pytest.approx(-.1)


def test_experiment_is_finite_and_purged():
    result = run_experiment(demo_prices(700), RunConfig().model_dump(), lambda *_: None)
    assert len(result["curve"]) == result["split"]["test"]
    assert result["split"]["purged"] == 4
    assert len(result["comparison"]) == 6
    assert sum(r["share"] for r in result["regimes"]) == pytest.approx(1)
    assert all(np.isfinite(list(result["metrics"].values())))
    for r in result["regimes"]:
        assert sum(r["weights"]) == pytest.approx(1)
    for point in result["curve"]:
        assert point["timestamp"] > point["signal_timestamp"]


def test_downsampling_cannot_invent_higher_frequency():
    config = RunConfig(interval="1h").model_dump()
    with pytest.raises(ValueError, match="küçük olamaz"):
        run_experiment(demo_prices(500), config, lambda *_: None)
