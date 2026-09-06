"""Quant API: spec bolum 31 endpointleri.

Mevcut API sozlesmesi bozulmaz; bu router ek olarak monte edilir.
Tum response'lar {success, experiment_id, data, error} zarfindadir.
Hesaplama stateless'tir; buyuk DataFrame dondurulmez (ozet + ilk N satir).
"""
from __future__ import annotations

import uuid
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.quant.ablation import ablation_report, shap_stability_report
from backend.quant.calibration import calibrate_probabilities, calibration_metrics, QuantilePredictor
from backend.quant.clustering import cluster_features, prune_redundant_features
from backend.quant.config import DEFAULT_QUANT_CONFIG, QUANT_ARTIFACT_TYPES
from backend.quant.fitness import QuantFitnessCalculator
from backend.quant.ic import (
    DEFAULT_IC_DECAY_HORIZONS,
    calculate_feature_ic,
    calculate_ic_decay,
    feature_quality_report,
    sign_consistency_report,
)
from backend.quant.stress import (
    DEFAULT_LATENCY_BARS,
    DEFAULT_SLIPPAGE_BPS,
    cost_stress_matrix,
    latency_stress,
    robustness_score,
    slippage_stress,
    systematic_stress,
)
from backend.quant.validation import PurgedKFold, anchored_splits, rolling_splits

router = APIRouter(prefix="/api", tags=["quant"])


def envelope(data: Any = None, experiment_id: str | None = None) -> dict:
    return {"success": True, "experiment_id": experiment_id, "data": data, "error": None}


def fail(message: str) -> dict:
    return {"success": False, "experiment_id": None, "data": None, "error": message}


def _frame(columns: dict[str, list[float]], limit: int = 5000) -> pd.DataFrame:
    df = pd.DataFrame({k: np.asarray(v, dtype=float)[:limit] for k, v in columns.items()})
    if df.empty:
        raise ValueError("Ozellik verisi bos.")
    return df


class ICRequest(BaseModel):
    features: dict[str, list[float]]
    target: list[float]
    experiment_id: str | None = None


class ICDecayRequest(BaseModel):
    feature: list[float]
    feature_name: str = "feature"
    target: list[float]
    horizons: list[int] = Field(default_factory=lambda: list(DEFAULT_IC_DECAY_HORIZONS))
    experiment_id: str | None = None


class StabilityRequest(BaseModel):
    fold_ic_by_feature: dict[str, list[float]]
    experiment_id: str | None = None


class ClusteringRequest(BaseModel):
    features: dict[str, list[float]]
    target: list[float] | None = None
    threshold: float = 0.85
    experiment_id: str | None = None


class PruneRequest(BaseModel):
    features: dict[str, list[float]]
    feature_metrics: list[dict]
    clusters: dict[str, list[str]]
    experiment_id: str | None = None


class AblationRequest(BaseModel):
    base_metrics: dict[str, float]
    ablation_metrics_by_feature: dict[str, dict[str, float]]
    experiment_id: str | None = None


class ShapStabilityRequest(BaseModel):
    shap_by_fold: dict[str, list[float]]
    experiment_id: str | None = None


class PurgedKFoldRequest(BaseModel):
    n_samples: int = Field(ge=3, le=200000)
    n_splits: int = 5
    purge_window: int = 0
    embargo_pct: float = 0.01
    embargo_bars: int | None = None
    experiment_id: str | None = None


class RetrainingRequest(BaseModel):
    n_samples: int = Field(ge=3, le=200000)
    mode: str = "rolling"
    train_window: int = 500
    test_window: int = 50
    step: int = 50
    initial_train_window: int = 500
    experiment_id: str | None = None


class CalibrationRequest(BaseModel):
    y_true: list[int]
    y_prob: list[float]
    method: str = "isotonic"
    experiment_id: str | None = None


class StressRequest(BaseModel):
    predictions: list[float]
    actuals: list[float]
    slippage_bps: list[float] | None = None
    latency_bars: list[int] | None = None
    commission_bps: float = 0.0
    base_slippage_bps: float = 0.0
    experiment_id: str | None = None


class FitnessRequest(BaseModel):
    sharpe: float
    feature_quality: float
    max_drawdown: float
    turnover: float
    weights: dict[str, float] | None = None
    n_features: int | None = None
    count_penalty: dict | None = None


class QuantileRequest(BaseModel):
    X: list[list[float]]
    y: list[float]
    quantiles: list[float] = Field(default_factory=lambda: [0.1, 0.5, 0.9])
    experiment_id: str | None = None


@router.post("/features/ic")
def api_ic(body: ICRequest):
    try:
        X = _frame(body.features)
        y = pd.Series(body.target[: len(X)], dtype=float)
        return envelope(calculate_feature_ic(X, y).to_dict("records"), body.experiment_id)
    except ValueError as exc:
        return fail(str(exc))


@router.post("/features/ic-decay")
def api_ic_decay(body: ICDecayRequest):
    try:
        feat = pd.Series(body.feature, name=body.feature_name, dtype=float)
        tgt = pd.Series(body.target, dtype=float)
        return envelope(calculate_ic_decay(feat, tgt, body.horizons).to_dict("records"),
                        body.experiment_id)
    except ValueError as exc:
        return fail(str(exc))


@router.post("/features/stability")
def api_stability(body: StabilityRequest):
    try:
        return envelope(sign_consistency_report(body.fold_ic_by_feature).to_dict("records"),
                        body.experiment_id)
    except ValueError as exc:
        return fail(str(exc))


@router.post("/features/quality")
def api_quality(body: ClusteringRequest):
    """IC + stability + cluster + pruning tek raporda (Feature Quality ekrani)."""
    try:
        X = _frame(body.features)
        ic_df = calculate_feature_ic(X, pd.Series((body.target or [0] * len(X))[: len(X)],
                                                  dtype=float))
        # Her feature icin 4 pencerede IC -> sign consistency yaklasimi.
        folds = {}
        n = len(X)
        for col in X.columns:
            parts = np.array_split(np.arange(n), 4)
            vals = []
            tgt = pd.Series((body.target or [0] * len(X))[:n], dtype=float)
            for idx in parts:
                s = X[col].iloc[idx]
                t = tgt.iloc[idx]
                paired = pd.DataFrame({"f": s, "t": t}).dropna()
                if len(paired) >= 3 and paired["f"].nunique() > 1:
                    from scipy.stats import spearmanr
                    v = spearmanr(paired["f"], paired["t"]).statistic
                    vals.append(float(v) if np.isfinite(v) else 0.0)
                else:
                    vals.append(0.0)
            folds[col] = vals
        cons = sign_consistency_report(folds)
        quality = feature_quality_report(ic_df, cons)
        clusters = cluster_features(X, body.threshold)
        selected = prune_redundant_features(X, quality.assign(missing_ratio=0.0), clusters)
        quality["cluster"] = quality["feature"].map(
            {f: cid for cid, members in clusters.items() for f in members})
        quality["selected"] = quality["feature"].isin(selected)
        return envelope({"quality": quality.to_dict("records"), "clusters": clusters,
                         "selected": selected}, body.experiment_id)
    except ValueError as exc:
        return fail(str(exc))


@router.post("/features/clustering")
def api_clustering(body: ClusteringRequest):
    try:
        X = _frame(body.features)
        clusters = cluster_features(X, body.threshold)
        return envelope({"clusters": clusters}, body.experiment_id)
    except ValueError as exc:
        return fail(str(exc))


@router.post("/features/prune")
def api_prune(body: PruneRequest):
    """Sprint1 §6: cluster başına en iyi feature'u seç (stateless)."""
    try:
        X = _frame(body.features)
        metrics_df = pd.DataFrame(body.feature_metrics)
        selected = prune_redundant_features(X, metrics_df, body.clusters)
        return envelope({"selected": selected, "clusters": body.clusters},
                        body.experiment_id)
    except ValueError as exc:
        return fail(str(exc))


@router.post("/features/ablation")
def api_ablation(body: AblationRequest):
    try:
        return envelope(ablation_report(body.base_metrics,
                                        body.ablation_metrics_by_feature).to_dict("records"),
                        body.experiment_id)
    except ValueError as exc:
        return fail(str(exc))


@router.post("/features/shap-stability")
def api_shap_stability(body: ShapStabilityRequest):
    try:
        return envelope(shap_stability_report(body.shap_by_fold).to_dict("records"),
                        body.experiment_id)
    except ValueError as exc:
        return fail(str(exc))


@router.post("/validation/purged-kfold")
def api_purged(body: PurgedKFoldRequest):
    try:
        cv = PurgedKFold(body.n_splits, body.purge_window, body.embargo_pct, body.embargo_bars)
        folds = [{"train": t.tolist(), "validation": v.tolist()}
                 for t, v in cv.split(np.zeros(body.n_samples))]
        return envelope({"folds": folds, "n_splits": body.n_splits}, body.experiment_id)
    except ValueError as exc:
        return fail(str(exc))


@router.post("/validation/retraining")
def api_retraining(body: RetrainingRequest):
    try:
        if body.mode == "anchored":
            gen = anchored_splits(body.n_samples, body.initial_train_window,
                                  body.test_window, body.step)
        elif body.mode == "rolling":
            gen = rolling_splits(body.n_samples, body.train_window,
                                 body.test_window, body.step)
        else:
            return fail("mode 'rolling' veya 'anchored' olmali.")
        folds = [{"train": t.tolist(), "validation": v.tolist()} for t, v in gen]
        return envelope({"mode": body.mode, "folds": folds}, body.experiment_id)
    except ValueError as exc:
        return fail(str(exc))


@router.post("/calibration/run")
def api_calibration(body: CalibrationRequest):
    try:
        calibrated = calibrate_probabilities(body.y_true, body.y_prob, body.method)
        metrics = calibration_metrics(body.y_true, body.y_prob, calibrated)
        return envelope({"calibrated_probability": calibrated.tolist(), **metrics},
                        body.experiment_id or f"CAL-{uuid.uuid4().hex[:8].upper()}")
    except ValueError as exc:
        return fail(str(exc))


@router.post("/backtest/slippage-stress")
def api_slippage(body: StressRequest):
    try:
        from backend.engine import fx_backtest
        stamps = pd.date_range("2024-01-01", periods=len(body.predictions), freq="h", tz="UTC")
        reality = {"spread_bps": 0.5, "commission_bps": body.commission_bps,
                   "slippage_bps": body.base_slippage_bps}
        df = slippage_stress(np.asarray(body.predictions), np.asarray(body.actuals),
                             stamps, reality, fx_backtest, body.slippage_bps or DEFAULT_SLIPPAGE_BPS)
        return envelope(df.to_dict("records"), body.experiment_id)
    except ValueError as exc:
        return fail(str(exc))


@router.post("/backtest/latency-stress")
def api_latency(body: StressRequest):
    try:
        from backend.engine import fx_backtest
        stamps = pd.date_range("2024-01-01", periods=len(body.predictions), freq="h", tz="UTC")
        reality = {"spread_bps": 0.5, "commission_bps": body.commission_bps,
                   "slippage_bps": body.base_slippage_bps}
        df = latency_stress(np.asarray(body.predictions), np.asarray(body.actuals),
                            stamps, reality, fx_backtest, body.latency_bars or DEFAULT_LATENCY_BARS)
        return envelope(df.to_dict("records"), body.experiment_id)
    except ValueError as exc:
        return fail(str(exc))


@router.post("/backtest/stress")
def api_stress(body: StressRequest):
    try:
        from backend.engine import fx_backtest
        stamps = pd.date_range("2024-01-01", periods=len(body.predictions), freq="h", tz="UTC")
        reality = {"spread_bps": 0.5, "commission_bps": body.commission_bps,
                   "slippage_bps": body.base_slippage_bps}
        df = systematic_stress(np.asarray(body.predictions), np.asarray(body.actuals),
                               stamps, reality, fx_backtest)
        matrix = cost_stress_matrix(np.asarray(body.predictions), np.asarray(body.actuals),
                                    stamps, reality, fx_backtest)
        worst = df.sort_values("sharpe").iloc[0].to_dict() if len(df) else {}
        base = df[df["scenario"] == "Normal"].iloc[0].to_dict() if len(df) else {}
        worst_dd = float(df["max_drawdown"].min()) if len(df) else 0.0
        return envelope({"scenarios": df.to_dict("records"),
                         "sharpe_matrix": matrix["sharpe_matrix"].to_dict(),
                         "base": base, "worst": worst,
                         "robustness_score": robustness_score(float(base.get("sharpe", 0.0)),
                                                              float(worst.get("sharpe", 0.0)), worst_dd),
                         "report_only": True}, body.experiment_id)
    except ValueError as exc:
        return fail(str(exc))


@router.post("/optimization/fitness")
def api_fitness(body: FitnessRequest):
    calc = QuantFitnessCalculator(body.weights, body.count_penalty)
    return envelope({"fitness": calc.calculate(body.sharpe, body.feature_quality,
                                               body.max_drawdown, body.turnover,
                                               body.n_features),
                     "breakdown": calc.breakdown(body.sharpe, body.feature_quality,
                                                 body.max_drawdown, body.turnover,
                                                 body.n_features)})


@router.post("/quantile/predict")
def api_quantile(body: QuantileRequest):
    try:
        if not body.X or not body.y or len(body.X) != len(body.y):
            return fail("X ve y ayni uzunlukta ve bos olmamali.")
        if len(body.X) > 2000 or len(body.X[0]) > 50:
            return fail("En fazla 2000 satir ve 50 kolon gonderin.")
        predictor = QuantilePredictor(tuple(body.quantiles)).fit(body.X, body.y)
        frame = predictor.predict(body.X)
        return envelope({"quantiles": list(predictor.quantiles),
                         "predictions": frame.to_dict("records")}, body.experiment_id)
    except ValueError as exc:
        return fail(str(exc))


@router.get("/quant/config")
def api_quant_config():
    return envelope({"config": DEFAULT_QUANT_CONFIG, "artifacts": QUANT_ARTIFACT_TYPES})


@router.get("/experiments/{identifier}/quant-artifacts")
def api_quant_artifact_types(identifier: str):
    return envelope({"experiment_id": identifier, "artifact_types": QUANT_ARTIFACT_TYPES},
                    identifier)
