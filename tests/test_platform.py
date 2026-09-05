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


def test_seal_invalidate_rotate_and_epoch(tmp_path):
    service = ExperimentService(dataset_loader=lambda _: (demo_prices(700), "demo", True), url="sqlite:///" + (tmp_path / "seal.db").as_posix(), storage=tmp_path / "seal")
    actor = {"id": "tester", "source": "REST", "request_id": "seal"}
    try:
        exp = service.create(make_spec("sealed"), actor)
        snap = exp["snapshot_id"]
        first = service.seal_status(snap)
        assert first["epoch"] == 1 and first["invalidated_at"] is None
        with pytest.raises(DomainError, match="nedeni gerekli"):
            service.invalidate_seal(first["seal_id"], "  ", actor)
        with pytest.raises(DomainError, match="bulunamadı"):
            service.invalidate_seal("00000000-0000-0000-0000-000000000000", "x", actor)
        burned = service.invalidate_seal(first["seal_id"], "exposed in review", actor)
        assert burned["invalidated_at"] and burned["invalidation_reason"] == "exposed in review"
        assert service.invalidate_seal(first["seal_id"], "other", actor)["invalidation_reason"] == "exposed in review"
        with pytest.raises(DomainError, match="geçersiz"):
            service.create(make_spec("after burn"), actor, snapshot_id=snap)
        second = service.rotate_seal(snap, "fresh epoch for follow-up", actor)
        assert second["epoch"] == 2 and second["invalidated_at"] is None and second["seal_id"] != first["seal_id"]
        history = service.seal_history(snap)
        assert [h["epoch"] for h in history] == [1, 2] and history[0]["invalidated_at"] is not None
        follow = service.create(make_spec("follow-up"), actor, snapshot_id=snap)
        assert follow["status"] == "DRAFT"
        kinds = [e["event_type"] for e in service.ledger()]
        assert "seal_invalidated" in kinds and "seal_rotated" in kinds
    finally:
        service.close()


def test_final_test_gate_rejects_burned_seal(tmp_path):
    service = ExperimentService(dataset_loader=lambda _: (demo_prices(700), "demo", True), url="sqlite:///" + (tmp_path / "gate.db").as_posix(), storage=tmp_path / "gate")
    actor = {"id": "tester", "source": "REST", "request_id": "gate"}
    try:
        exp = service.create(make_spec("gated"), actor)
        run = service.run(exp["id"], "gate-key", actor)
        service.invalidate_seal(service.seal_status(exp["snapshot_id"])["seal_id"], "compromised", actor)
        with pytest.raises(DomainError, match="geçersiz"):
            service.open_final_test(run["id"])
    finally:
        service.close()


def test_workspace_crud_archive_and_scoping(tmp_path):
    from backend.platform.scope import workspace_scope
    service = ExperimentService(dataset_loader=lambda _: (demo_prices(700), "demo", True), url="sqlite:///" + (tmp_path / "ws.db").as_posix(), storage=tmp_path / "ws")
    actor = {"id": "tester", "source": "REST", "request_id": "ws"}
    try:
        default = service.get_workspace("WS-DEFAULT")
        assert default["name"] == "EUR/USD Research"
        ws = service.create_workspace({"name": "Crypto Research", "market": "CRYPTO"}, actor)
        assert ws["code"].startswith("WS-") and ws["experiment_count"] == 0
        assert service.patch_workspace(ws["id"], {"description": "d"}, actor)["description"] == "d"
        with pytest.raises(DomainError, match="bulunamadı"):
            service.get_workspace("WS-NOPE")
        a = service.create(make_spec("in default"), actor)
        assert a["workspace_id"] == default["id"]
        b = service.create(make_spec("in crypto"), actor, workspace_id=ws["code"])
        assert b["workspace_id"] == ws["id"] and b["snapshot"]["workspace_id"] == ws["id"]
        with pytest.raises(DomainError, match="bulunamadı"):
            service.create(make_spec("nope"), actor, workspace_id="WS-NOPE")
        assert {e["id"] for e in service.list(workspace_id=ws["id"])} == {b["id"]}
        assert len(service.list()) == 2
        with pytest.raises(DomainError, match="bulunamadı"):
            service.get(a["id"], workspace_id=ws["id"])
        assert service.get(b["id"], workspace_id=ws["code"])["id"] == b["id"]
        child = service.clone(b["id"], CloneSpec(name="c"), actor)
        assert child["workspace_id"] == ws["id"]
        service.archive_workspace(ws["id"], actor)
        assert service.get_workspace(ws["id"])["is_archived"] == 1
        assert all(w["id"] != ws["id"] for w in service.list_workspaces())
        assert any(w["id"] == ws["id"] for w in service.list_workspaces(include_archived=True))
        with pytest.raises(DomainError, match="Arşiv"):
            service.create(make_spec("late"), actor, workspace_id=ws["id"])
        with pytest.raises(DomainError, match="arşivlenemez"):
            service.archive_workspace("WS-DEFAULT", actor)
        token = workspace_scope.set(ws["id"])
        try:
            with pytest.raises(DomainError, match="bulunamadı"):
                service.get(a["id"])
            assert service.get(b["id"])["id"] == b["id"]
        finally:
            workspace_scope.reset(token)
    finally:
        service.close()


def test_search_space_workspace_binding(tmp_path):
    service = ExperimentService(dataset_loader=lambda _: (demo_prices(700), "demo", True), url="sqlite:///" + (tmp_path / "wss.db").as_posix(), storage=tmp_path / "wss")
    actor = {"id": "tester", "source": "REST"}
    definition = {"name": "ws-a space", "feature_groups": ["technical"], "features": ["return_1", "volatility_14", "momentum_14"],
                  "min_features": 3, "max_features": 3, "models": ["ridge"], "thresholds_bps": [0, .5]}
    try:
        ws_a = service.create_workspace({"name": "A"}, actor)
        ws_b = service.create_workspace({"name": "B"}, actor)
        space = service.create_search_space(definition, actor, ws_a["id"])
        assert space["workspace_id"] == ws_a["id"]
        assert {s["id"] for s in service.list_search_spaces(ws_b["id"])} == set()
        draft = make_spec("cross", "none").model_copy(update={"search_space_id": space["id"]})
        with pytest.raises(DomainError, match="bulunamadı"):
            service.create(draft, actor, workspace_id=ws_b["id"])
        ok = service.create(draft, actor, workspace_id=ws_a["id"])
        assert ok["specification"]["models"] == ["ridge"]
    finally:
        service.close()


def test_budget_isolated_per_workspace(tmp_path):
    service = ExperimentService(dataset_loader=lambda _: (demo_prices(700), "demo", True), url="sqlite:///" + (tmp_path / "bud.db").as_posix(), storage=tmp_path / "bud")
    actor = {"id": "tester", "source": "REST", "request_id": "bud"}
    try:
        ws_a = service.create_workspace({"name": "Budget A"}, actor)
        ws_b = service.create_workspace({"name": "Budget B"}, actor)
        service.create(make_spec("a1"), actor, workspace_id=ws_a["id"])
        b1 = service.create(make_spec("b1"), actor, workspace_id=ws_b["id"])
        service.create(make_spec("b2"), actor, workspace_id=ws_b["id"])
        service.run(b1["id"], "budget-key", actor)
        ba = service.budget_status(ws_a["id"])
        bb = service.budget_status(ws_b["id"])
        assert ba["workspace_id"] == ws_a["id"] and bb["workspace_id"] == ws_b["id"]
        assert ba["usage"]["experiments"] == 1 and bb["usage"]["experiments"] == 2
        assert bb["usage"]["candidates"] > 0 and ba["usage"]["candidates"] == 0
        assert {e["budget_id"] for e in service.ledger(workspace_id=ws_b["id"])} == {bb["id"]}
        assert len(service.ledger()) == len(service.ledger(workspace_id=ws_a["id"])) + len(service.ledger(workspace_id=ws_b["id"]))
        est = service.estimate(make_spec("scoped"), None, ws_b["id"])
        assert "sealed_test_accesses" in est and "post_test_iteration" in est
        upd = service.update_budget_limits({"max_experiments": 5}, actor, ws_a["id"])
        assert upd["limits"]["max_experiments"] == 5 and upd["limits"]["max_candidates"] == 2000
        with pytest.raises(DomainError, match="Geçersiz"):
            service.update_budget_limits({"max_experiments": -1}, actor, ws_a["id"])
        with pytest.raises(DomainError, match="Geçersiz"):
            service.update_budget_limits({"nope": 1}, actor, ws_a["id"])
        with pytest.raises(DomainError, match="bulunamadı"):
            service.budget_status("WS-NOPE")
    finally:
        service.close()


def test_budget_migration_reassigns_legacy_global(tmp_path):
    from sqlalchemy import text
    from alembic.config import Config
    from alembic import command
    from backend.platform.db import ROOT
    service = ExperimentService(dataset_loader=lambda _: (demo_prices(700), "demo", True), url="sqlite:///" + (tmp_path / "mig.db").as_posix(), storage=tmp_path / "mig")
    actor = {"id": "tester", "source": "REST"}
    try:
        service.create(make_spec("pre-migration"), actor)
        with service.engine.begin() as con:
            con.execute(text("INSERT INTO research_budgets (id, limits, created_at, updated_at) VALUES ('global', '{\"a\": 1}', 't', 't')"))
            con.execute(text("INSERT INTO research_trial_events (budget_id, experiment_id, event_type, quantity, details, created_at) VALUES ('global', NULL, 'legacy_probe', 3, '{}', 't')"))
        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
        with service.engine.begin() as conn:
            cfg.attributes["connection"] = conn
            command.downgrade(cfg, "0006_workspaces")
            command.upgrade(cfg, "head")
        default = service.get_workspace("WS-DEFAULT")
        status = service.budget_status(default["id"])
        assert status["usage"]["experiments"] == 1
        kinds = {(e["event_type"], e["quantity"]) for e in service.ledger(workspace_id=default["id"])}
        assert ("legacy_probe", 3) in kinds
        with service.engine.connect() as con:
            assert not con.execute(text("SELECT id FROM research_budgets WHERE id = 'global'")).first()
    finally:
        service.close()


def test_policy_rejects_excessive_work(tmp_path):
    service = ExperimentService(dataset_loader=lambda _: (demo_prices(700), "demo", True), url="sqlite:///" + (tmp_path / "x.db").as_posix(), storage=tmp_path / "a")
    try:
        base = make_spec("too expensive", "genetic")
        invalid = base.model_copy(update={"optimization": base.optimization.model_copy(update={"population": 32, "generations": 20})})
        with pytest.raises(DomainError, match="Hesaplama sınırı"):
            service.create(invalid, {"id": "tester"})
    finally:
        service.close()


def test_pareto_ranks_form_nondominated_layers():
    from backend.platform.research import pareto_ranks

    def cand(cid, sharpe, ret, dd, feasible=True):
        return {"id": cid, "feasible": feasible,
                "metrics": {"sharpe": sharpe, "return": ret, "max_drawdown": dd}}

    front_a = cand("a", 2.0, 0.10, -0.05)
    front_c = cand("c", 3.0, 0.02, -0.20)  # best sharpe, worst return/drawdown: tradeoff, still front
    second = cand("d", 1.5, 0.08, -0.06)  # dominated by "a" only
    third = cand("b", 1.0, 0.05, -0.10)  # dominated by "a" and "d"
    infeasible = cand("e", 9.0, 0.50, -0.01, feasible=False)
    ranks = pareto_ranks([front_a, front_c, second, third, infeasible])
    assert ranks["a"] == 0 and ranks["c"] == 0
    assert ranks["d"] == 1 and ranks["b"] == 2
    assert "e" not in ranks


def test_optimize_tracks_generation_parents_and_ranks():
    from backend.platform.research import optimize, pareto_front
    df = demo_prices(700)
    spec = make_spec("lineage", "genetic")
    x = feature_frame(df)
    target = (df.open.shift(-2) / df.open.shift(-1) - 1).reindex(x.index)
    x = x.loc[target.notna()]
    y = target.dropna().to_numpy()
    dev_end = int(len(x) * (spec.validation.train_ratio + .15)) - spec.validation.gap
    annual = 252 * 24 / (df.index.to_series().diff().median().total_seconds() / 3600)
    out = optimize(x.iloc[:dev_end].copy(), y[:dev_end].copy(), spec, annual, lambda *_: None)
    cands = out["candidates"]
    assert cands
    by_id = {c["id"]: c for c in cands}
    assert all(isinstance(c["generation"], int) and c["generation"] >= 1 for c in cands)
    assert all(set(c["parents"]) <= set(by_id) for c in cands)
    assert all(c["parents"] == [] for c in cands if c["generation"] == 1)
    assert any(c["generation"] > 1 and c["parents"] for c in cands)
    front_ids = {c["id"] for c in pareto_front(cands)}
    assert {c["id"] for c in cands if c.get("pareto_rank") == 0} == front_ids
    assert all(c["pareto_rank"] is None for c in cands if not c["feasible"])
    assert all(isinstance(c["dominance_count"], int) for c in cands)


def test_candidate_parents_persisted_and_read(tmp_path):
    service = ExperimentService(dataset_loader=lambda _: (demo_prices(700), "demo", True), url="sqlite:///" + (tmp_path / "parents.db").as_posix(), storage=tmp_path / "lineage")
    service.start(); actor={"id":"tester","source":"REST"}
    try:
        experiment=service.create(make_spec("parents", "none"),actor)

        def cand(cid, sharpe, ret, dd, feasible=True, generation=1, parents=(), pareto=False, selected=False):
            return {"id": cid, "genome": {"mask": [True], "model": "ridge", "param": 1, "threshold": 0.0},
                    "features": ["return_1"], "model": "ridge", "parameters": {"alpha": 10}, "threshold_bps": 0.0,
                    "metrics": {"sharpe": sharpe, "return": ret, "max_drawdown": dd},
                    "fitness": sharpe if feasible else -1000000, "feasible": feasible, "folds": [],
                    "generation": generation, "parents": list(parents),
                    "pareto_rank": 0 if pareto else None, "dominance_count": 0,
                    "pareto": pareto, "selected": selected}

        payload=[cand("a" * 16, 2.0, 0.10, -0.05, pareto=True, selected=True),
                 cand("b" * 16, 1.0, 0.05, -0.10, generation=2, parents=["a" * 16]),
                 cand("c" * 16, 9.0, 0.50, -0.01, feasible=False, parents=["a" * 16, "b" * 16])]
        service.persist_candidates(experiment["id"], payload, "frozen_candidate.json")
        rows=service.candidates(experiment["id"])
        by_key={r["candidate_key"]: r for r in rows}
        assert by_key["a" * 16]["generation"] == 1 and by_key["a" * 16]["pareto_rank"] == 0
        assert by_key["a" * 16]["parents"] == [] and by_key["a" * 16]["decision"] == "selected"
        assert by_key["b" * 16]["generation"] == 2 and by_key["b" * 16]["parents"] == ["a" * 16]
        assert by_key["c" * 16]["decision"] == "rejected_constraint"
        assert sorted(by_key["c" * 16]["parents"]) == ["a" * 16, "b" * 16]
        assert service.candidate(by_key["b" * 16]["id"])["parents"] == ["a" * 16]
        service.persist_candidates(experiment["id"], payload, "frozen_candidate.json")
        assert len(service.candidates(experiment["id"])) == 3
    finally:
        service.close()


def test_classify_lineage_maps_spec_edits_to_relations():
    from backend.platform.service import classify_lineage
    base = make_spec("parent", "genetic").model_dump()
    assert classify_lineage(base, dict(base))[:2] == ("CLONED_FROM", "exact_clone")

    def mutate(**overrides):
        child = {**base, **overrides}
        return classify_lineage(base, child)

    parent_names = ["return_1", "volatility_14", "momentum_30"]
    named = {**base, "features": {**base["features"], "names": parent_names}}
    relation, reason, summary = classify_lineage(named, {**named, "features": {**named["features"], "names": ["return_1"]}})
    assert (relation, reason) == ("FEATURE_REDUCED_FROM", "feature_subset")
    assert summary["features_removed"] == ["momentum_30", "volatility_14"]
    assert mutate(features={**base["features"], "names": ["return_1", "rsi"]})[:2] == ("CLONED_FROM", "mixed_changes")
    assert mutate(validation={**base["validation"], "folds": 3})[:2] == ("VALIDATION_CHANGED_FROM", "validation_changed")
    assert mutate(regime_states=4)[:2] == ("REGIME_SPECIALIZED_FROM", "regime_states_changed")
    assert mutate(optimization={**base["optimization"], "population": 8})[:2] == ("AUTO_REFINED_FROM", "optimization_retuned")
    wide = {**base, "models": ["ridge", "xgboost"]}
    assert classify_lineage(wide, {**wide, "models": ["ridge"]})[:2] == ("REGULARIZED_FROM", "model_subset")
    tightened = {**base["optimization"], "max_features": 5, "max_drawdown": 0.5}
    assert mutate(optimization=tightened)[:2] == ("REGULARIZED_FROM", "capacity_tightened")
    loosened = {**base["optimization"], "max_features": 20}
    assert mutate(optimization=loosened)[:2] == ("AUTO_REFINED_FROM", "optimization_retuned")
    assert mutate(seed=7)[:2] == ("AUTO_REFINED_FROM", "reseeded")
    assert mutate(validation={**base["validation"], "folds": 3}, models=["random_forest"])[:2] == ("CLONED_FROM", "mixed_changes")


def test_clone_writes_specific_lineage_relations(tmp_path):
    service = ExperimentService(dataset_loader=lambda _: (demo_prices(700), "demo", True), url="sqlite:///" + (tmp_path / "lineage.db").as_posix(), storage=tmp_path / "edges")
    service.start(); actor={"id":"tester","source":"REST"}
    try:
        parent_data = make_spec("edge parent", "none").model_dump()
        parent_data["features"] = {"groups": ["technical"], "families": [], "names": ["return_1", "volatility_14", "momentum_30"]}
        parent = service.create(parent_data, actor)

        def child_spec(**overrides):
            data = dict(parent["specification"])
            data.update(overrides)
            return ExperimentSpec.model_validate(data)

        reduced = service.clone(parent["id"], CloneSpec(name="reduced",
            specification=child_spec(features={"groups": ["technical"], "families": [], "names": ["return_1"]})), actor)
        assert service.lineage(reduced["id"])[0]["relation_type"] == "FEATURE_REDUCED_FROM"
        revalidated = service.clone(parent["id"], CloneSpec(name="revalidated",
            specification=child_spec(validation={**parent["specification"]["validation"], "folds": 3})), actor)
        assert service.lineage(revalidated["id"])[0]["relation_type"] == "VALIDATION_CHANGED_FROM"
        pure = service.clone(parent["id"], CloneSpec(name="pure"), actor)
        edge = service.lineage(pure["id"])[0]
        assert edge["relation_type"] == "CLONED_FROM" and edge["from_experiment_id"] == parent["id"]
        assert {e["to_experiment_id"] for e in service.lineage(parent["id"])} == {reduced["id"], revalidated["id"], pure["id"]}
    finally:
        service.close()


def test_feature_analysis_reports_missingness_and_regime_metrics():
    from backend.platform.research import feature_analysis
    rng = np.random.default_rng(7)
    n = 120
    frame = pd.DataFrame({"a": rng.normal(size=n), "b": rng.normal(size=n)})
    frame.loc[:29, "b"] = np.nan
    missingness = {c: float(frame[c].isna().mean()) for c in frame}
    x = frame.dropna()
    y = (x["a"].to_numpy() * 0.001 + rng.normal(scale=0.001, size=len(x)))
    states = np.array([0] * 60 + [1] * (len(x) - 60))
    out = feature_analysis(x, y, 7, missingness, states, 2)
    by_feature = {item["feature"]: item for item in out["features"]}
    assert by_feature["a"]["missingness"] == 0.0
    assert by_feature["b"]["missingness"] == pytest.approx(0.25)
    for item in out["features"]:
        assert [rm["regime"] for rm in item["regime_metrics"]] == [0, 1]
        assert sum(rm["bars"] for rm in item["regime_metrics"]) == len(x)
        assert sum(rm["share"] for rm in item["regime_metrics"]) == pytest.approx(1.0)
    assert out["redundancy_pairs"] == []


def test_feature_intelligence_persisted_and_read(tmp_path):
    service = ExperimentService(dataset_loader=lambda _: (demo_prices(700), "demo", True), url="sqlite:///" + (tmp_path / "feat.db").as_posix(), storage=tmp_path / "feat")
    service.start(); actor={"id":"tester","source":"REST"}
    try:
        experiment=service.create(make_spec("features", "none"),actor)
        analysis={"scope": "development_only", "window_count": 4,
            "features": [
                {"feature": "return_1", "ic": 0.02, "rolling_ic": [0.01, 0.02, 0.03, 0.02],
                 "sign_consistency": 1.0, "mutual_information": 0.001, "missingness": 0.0,
                 "regime_metrics": [{"regime": 0, "bars": 60, "share": 0.6, "ic": 0.03},
                                    {"regime": 1, "bars": 40, "share": 0.4, "ic": -0.01}]},
                {"feature": "rsi", "ic": -0.01, "rolling_ic": [0.0, -0.01, -0.02, -0.01],
                 "sign_consistency": 0.75, "mutual_information": 0.002, "missingness": 0.25,
                 "regime_metrics": [{"regime": 0, "bars": 60, "share": 0.6, "ic": 0.0},
                                    {"regime": 1, "bars": 40, "share": 0.4, "ic": -0.02}]},
            ],
            "redundancy_pairs": [{"a": "return_1", "b": "rsi", "correlation": 0.91}]}
        survival=[{"feature": "return_1", "selection_frequency": 0.8, "top_survival": 1.0,
                   "fitness_present": 1.5, "fitness_absent": 0.5},
                  {"feature": "rsi", "selection_frequency": 0.2, "top_survival": 0.0,
                   "fitness_present": 0.4, "fitness_absent": 1.2}]
        service.persist_feature_analysis(experiment["id"], analysis, ["return_1"], survival)
        rows={r["feature"]: r for r in service.feature_evaluations(experiment["id"])}
        assert rows["rsi"]["missingness"] == pytest.approx(0.25) and rows["rsi"]["selected"] == 0
        assert rows["return_1"]["selected"] == 1 and len(rows["return_1"]["stability_runs"]) == 4
        assert [rm["regime"] for rm in rows["return_1"]["regime_metrics"]] == [0, 1]
        assert rows["return_1"]["top_survival"] == pytest.approx(1.0)
        assert rows["rsi"]["selection_frequency"] == pytest.approx(0.2)
        bundle=service.feature_intelligence(experiment["id"])
        assert bundle["experiment_id"] == experiment["id"] and len(bundle["evaluations"]) == 2
        assert bundle["redundancy_pairs"][0]["a"] == "return_1"
        service.persist_feature_analysis(experiment["id"], analysis, ["return_1"], survival)
        assert len(service.feature_evaluations(experiment["id"])) == 2
        assert len(service.feature_intelligence(experiment["id"])["redundancy_pairs"]) == 1
    finally:
        service.close()


def test_optimization_constraints_are_validated():
    from pydantic import ValidationError
    base = make_spec("constraints", "none").model_dump()
    base["optimization"]["min_trades"] = -1
    with pytest.raises(ValidationError):
        ExperimentSpec.model_validate(base)
    base["optimization"]["min_trades"] = 0
    base["optimization"]["max_exposure"] = 1.5
    with pytest.raises(ValidationError):
        ExperimentSpec.model_validate(base)
    base["optimization"]["max_exposure"] = 0.0
    with pytest.raises(ValidationError):
        ExperimentSpec.model_validate(base)
    ok = ExperimentSpec.model_validate({**base, "optimization": {**base["optimization"], "max_exposure": 0.8, "min_trades": 5}})
    assert ok.optimization.min_trades == 5 and ok.optimization.max_exposure == 0.8
    defaults = make_spec("defaults", "none")
    assert defaults.optimization.min_trades == 0 and defaults.optimization.max_exposure is None


def test_optimize_enforces_trade_and_exposure_constraints():
    from backend.platform.research import optimize, merged_reality, OBJECTIVE_DIRECTIONS
    df = demo_prices(700)
    spec = make_spec("constraints", "genetic")
    x = feature_frame(df)
    target = (df.open.shift(-2) / df.open.shift(-1) - 1).reindex(x.index)
    x = x.loc[target.notna()]
    y = target.dropna().to_numpy()
    dev_end = int(len(x) * (spec.validation.train_ratio + .15)) - spec.validation.gap
    annual = 252 * 24 / (df.index.to_series().diff().median().total_seconds() / 3600)
    args = (x.iloc[:dev_end].copy(), y[:dev_end].copy())
    out = optimize(*args, spec, annual, lambda *_: None)
    assert out["candidates"]
    assert all(set(c["objectives"]) == set(OBJECTIVE_DIRECTIONS) for c in out["candidates"])
    assert all(c["constraint_violations"] == [] for c in out["candidates"] if c["feasible"])
    reality = merged_reality(spec)
    one_way = reality.spread_bps / 2 + reality.commission_bps + reality.slippage_bps
    first = out["candidates"][0]
    assert first["objectives"]["cost_bps_estimate"] == pytest.approx(first["metrics"]["turnover"] * one_way)
    assert first["objectives"]["sharpe"] == first["metrics"]["sharpe"]
    strict_trades = spec.model_copy(update={"optimization": spec.optimization.model_copy(update={"min_trades": 10 ** 6})})
    with pytest.raises(ValueError, match="sağlayan aday yok"):
        optimize(*args, strict_trades, annual, lambda *_: None)
    strict_exposure = spec.model_copy(update={"optimization": spec.optimization.model_copy(update={"max_exposure": 0.0001})})
    with pytest.raises(ValueError, match="sağlayan aday yok"):
        optimize(*args, strict_exposure, annual, lambda *_: None)
    mild = spec.model_copy(update={"optimization": spec.optimization.model_copy(update={"min_trades": 1})})
    mild_out = optimize(*args, mild, annual, lambda *_: None)
    assert all(c["metrics"]["position_changes"] >= 1 for c in mild_out["candidates"] if c["feasible"])
    assert all("min_trades" in c["constraint_violations"] for c in mild_out["candidates"]
               if not c["feasible"] and c["metrics"]["position_changes"] < 1)


def test_regime_router_reports_worst_drawdown_and_coverage():
    from backend.platform.research import RegimeRouter
    rng = np.random.default_rng(0)
    n = 100
    ret = rng.normal(0.0005, 0.002, n)
    sig = np.array([1] * 60 + [-1] * 40)
    states = np.array([0] * 50 + [1] * 50)
    report = RegimeRouter(states, 2).report(ret, sig, 252 * 6)
    assert [e["regime"] for e in report["regime_metrics"]] == [0, 1]
    assert all(e["qualified"] for e in report["regime_metrics"])
    assert report["regime_coverage"] == pytest.approx(1.0)
    assert report["worst_regime_drawdown"] == min(e["max_drawdown"] for e in report["regime_metrics"])
    sparse = RegimeRouter(np.zeros(10, dtype=int), 3).report(ret[:10], sig[:10], 252 * 6)
    assert sparse["worst_regime_drawdown"] is None and sparse["regime_coverage"] == pytest.approx(0.0)


def _dev_frame():
    from backend.platform.research import feature_frame
    df = demo_prices(700)
    spec = make_spec("regime gate", "genetic")
    x = feature_frame(df)
    target = (df.open.shift(-2) / df.open.shift(-1) - 1).reindex(x.index)
    x = x.loc[target.notna()]
    y = target.dropna().to_numpy()
    dev_end = int(len(x) * (spec.validation.train_ratio + .15)) - spec.validation.gap
    annual = 252 * 24 / (df.index.to_series().diff().median().total_seconds() / 3600)
    return spec, x.iloc[:dev_end].copy(), y[:dev_end].copy(), annual


def test_optimize_worst_regime_gate():
    from pydantic import ValidationError
    from backend.platform.research import optimize, RegimeRouter
    spec, x_dev, y_dev, annual = _dev_frame()
    states = np.zeros(len(x_dev), dtype=int)
    states[len(x_dev) // 2:] = 1
    router = RegimeRouter(states, 2)
    assert spec.optimization.max_worst_regime_drawdown is None
    out = optimize(x_dev, y_dev, spec, annual, lambda *_: None, None, router)
    assert out["candidates"]
    assert all("worst_regime_drawdown" not in c["constraint_violations"] for c in out["candidates"])
    assert all(len(c["regime_metrics"]) == 2 and c["regime_coverage"] == pytest.approx(1.0) for c in out["candidates"])
    bad = dict(spec.model_dump()["optimization"])
    bad["max_worst_regime_drawdown"] = 1.5
    with pytest.raises(ValidationError):
        ExperimentSpec.model_validate({**spec.model_dump(), "optimization": bad})
    impossible = spec.model_copy(update={"optimization": spec.optimization.model_copy(update={"max_worst_regime_drawdown": 0.0001})})
    with pytest.raises(ValueError, match="sağlayan aday yok"):
        optimize(x_dev, y_dev, impossible, annual, lambda *_: None, None, router)
    mild = spec.model_copy(update={"optimization": spec.optimization.model_copy(update={"max_worst_regime_drawdown": 0.03})})
    mild_out = optimize(x_dev, y_dev, mild, annual, lambda *_: None, None, router)
    assert all(c["worst_regime_drawdown"] is not None and c["worst_regime_drawdown"] >= -0.03
               for c in mild_out["candidates"] if c["feasible"])
    assert all("worst_regime_drawdown" in c["constraint_violations"] for c in mild_out["candidates"]
               if not c["feasible"] and (c["worst_regime_drawdown"] is None or c["worst_regime_drawdown"] < -0.03))


def test_execute_research_reports_candidate_regimes(tmp_path):
    from backend.platform.research import execute_research
    df = demo_prices(700)
    result = execute_research(df, make_spec("regime e2e", "none"), lambda *_: None, tmp_path)
    best = result["optimization"]["best"]
    assert len(best["regime_metrics"]) == 3
    assert best["worst_regime_drawdown"] is not None and best["regime_coverage"] == pytest.approx(1.0)


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
    finally:
        service.close()


