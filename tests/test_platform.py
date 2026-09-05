import time
import pytest
import numpy as np
import pandas as pd

from backend.engine import demo_prices
from backend.platform.schema import CloneSpec, DomainError, ExperimentSpec
from backend.platform.service import ExperimentService
from backend.platform.research import feature_frame, execute_research
from backend.engine import read_prices


def make_spec(name, algorithm="none"):
    return ExperimentSpec.model_validate({
        "name": name, "dataset_id": "demo", "models": ["ridge"],
        "features": {"groups": ["technical"], "names": []},
        "optimization": {"algorithm": algorithm, "population": 4, "generations": 2, "elitism": 1,
                         "min_features": 3, "max_features": 10, "max_drawdown": .9},
        "validation": {"method": "walk_forward", "train_ratio": .65, "folds": 2, "gap": 2, "locked_test": True},
        "backtest": {"capital": 10000, "cost_bps": .5, "slippage_bps": .2},
    })


def wait_until_done(service, identifier):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        item = service.get(identifier)
        if item["status"] in {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"}:
            return item
        time.sleep(.1)
    raise AssertionError("Worker timeout")


def test_registry_snapshot_clone_idempotency_and_locked_test(tmp_path):
    def loader(identifier):
        assert identifier == "demo"
        return demo_prices(700), "E2E demo", True
    service = ExperimentService(dataset_loader=loader, url="sqlite:///" + (tmp_path / "registry.db").as_posix(), storage=tmp_path / "artifacts")
    service.start()
    actor = {"id": "tester", "source": "REST", "request_id": "test"}
    try:
        parent = service.create(make_spec("baseline"), actor)
        assert parent["code"].startswith("EXP-")
        assert parent["snapshot"]["sha256"]
        run = service.run(parent["id"], "reproducible-key", actor)
        assert service.run(parent["id"], "reproducible-key", actor)["id"] == run["id"]
        done = wait_until_done(service, parent["id"])
        assert done["status"] == "COMPLETED"
        result = service.result(parent["id"])
        assert result["test_policy"]["optimizer_access"] is False
        assert result["test_policy"]["test_evaluations"] == 1
        assert result["feature_analysis"]["scope"] == "development_only"
        with pytest.raises(DomainError, match="bir kez"):
            service.run(parent["id"], "different-key", actor)
        with pytest.raises(DomainError, match="sabittir"):
            service.patch(parent["id"], make_spec("mutated"), actor)
        child = service.clone(parent["id"], CloneSpec(name="comparison clone"), actor)
        assert child["parent_id"] == parent["id"]
        assert child["snapshot_id"] == parent["snapshot_id"]
        service.run(child["id"], "clone-key", actor)
        assert wait_until_done(service, child["id"])["status"] == "COMPLETED"
        comparison = service.compare([parent["id"], child["id"]])
        assert comparison["comparable"] is True
        assert len(comparison["items"]) == 2
    finally:
        service.close()


def test_lagged_external_series_is_preserved_and_causal(tmp_path):
    index = pd.date_range("2024-01-01", periods=500, freq="h", tz="UTC")
    base = demo_prices(500).copy()
    base.index = index
    base.index.name = "timestamp"
    base["macro__us10y"] = np.linspace(4.0, 5.0, len(base))
    base["macro__us10y__available_at"] = index
    raw = base.reset_index().to_csv(index=False).encode()
    parsed = read_prices(raw)
    assert "macro__us10y" in parsed
    assert str(parsed["macro__us10y__available_at"].dtype).startswith("datetime64[ns, UTC]")

    changed = parsed.copy()
    changed.loc[index[280]:, "macro__us10y"] += 100
    before, after = feature_frame(parsed), feature_frame(changed)
    cutoff = index[280]
    pd.testing.assert_series_equal(before.loc[:cutoff, "lag__macro__us10y"], after.loc[:cutoff, "lag__macro__us10y"])


def test_sparse_external_series_does_not_shorten_technical_features():
    base = demo_prices(700)
    enriched = base.copy()
    enriched["macro__monthly"] = np.nan
    enriched.loc[enriched.index[::80], "macro__monthly"] = np.arange(0, len(enriched.index[::80]))
    assert len(feature_frame(base)) == len(feature_frame(enriched))


def test_selected_lagged_external_feature_runs_end_to_end(tmp_path):
    df = demo_prices(700)
    df["macro__policy_rate"] = 4.5 + np.arange(len(df)) // 180 * .25
    df["macro__policy_rate__available_at"] = df.index - pd.Timedelta(hours=1)
    spec = ExperimentSpec.model_validate({
        "name": "lagged external", "dataset_id": "demo", "models": ["ridge"],
        "features": {"groups": ["technical"], "families": [], "names": ["return_1", "volatility_14", "lag__macro__policy_rate"]},
        "optimization": {"algorithm": "none", "population": 4, "generations": 1, "elitism": 1, "min_features": 1, "max_features": 3, "max_drawdown": .9},
        "validation": {"method": "walk_forward", "train_ratio": .65, "folds": 2, "gap": 2, "locked_test": True},
        "backtest": {"capital": 10000, "cost_bps": .5, "slippage_bps": .2},
    })
    result = execute_research(df, spec, lambda *_: None, tmp_path)
    assert result["selected_features"]
    assert result["split"]["test"] > 0


def test_policy_rejects_excessive_work(tmp_path):
    service = ExperimentService(dataset_loader=lambda _: (demo_prices(700), "demo", True), url="sqlite:///" + (tmp_path / "x.db").as_posix(), storage=tmp_path / "a")
    try:
        base = make_spec("too expensive", "genetic")
        invalid = base.model_copy(update={"optimization": base.optimization.model_copy(update={"population": 32, "generations": 20})})
        with pytest.raises(DomainError, match="Hesaplama sınırı"):
            service.create(invalid, {"id": "tester"})
    finally:
        service.close()


def test_versioned_search_space_and_durable_candidate_registry(tmp_path):
    service = ExperimentService(dataset_loader=lambda _: (demo_prices(700), "demo", True), url="sqlite:///" + (tmp_path / "x.db").as_posix(), storage=tmp_path / "a")
    service.start(); actor={"id":"tester","source":"REST"}
    try:
        space=service.create_search_space({"name":"small ridge","feature_groups":["technical"],"features":["return_1","volatility_14","momentum_14"],"min_features":3,"max_features":3,"models":["ridge"],"thresholds_bps":[0,.5]},actor)
        draft=make_spec("registry", "none").model_copy(update={"search_space_id":space["id"]})
        experiment=service.create(draft,actor)
        assert experiment["specification"]["models"] == ["ridge"]
        service.run(experiment["id"],"candidate-registry",actor)
        assert wait_until_done(service,experiment["id"])["status"] == "COMPLETED"
        candidates=service.candidates(experiment["id"])
        assert candidates and candidates[0]["decision"] == "selected"
        assert service.candidate(candidates[0]["id"])["candidate_key"]
        features=service.feature_evaluations(experiment["id"])
        assert features and len(features[0]["stability_runs"]) == 4
    finally: service.close()
