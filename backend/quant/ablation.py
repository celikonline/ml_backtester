"""Faz 3: Feature Ablation + SHAP Stability (spec bolum 12-13).

Ablation sequential ilk surum; paralel calisma disi.
SHAP bagimliligi yok: fold bazli importance matrisleri uzerinden stabilite.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ablation_report(base_metrics: dict, ablation_metrics_by_feature: dict[str, dict]) -> pd.DataFrame:
    """Cikti: feature | base_sharpe | ablation_sharpe | sharpe_delta |
    return_delta | drawdown_delta."""
    rows = []
    for feat, m in ablation_metrics_by_feature.items():
        rows.append({
            "feature": feat,
            "base_sharpe": float(base_metrics.get("sharpe", 0.0)),
            "ablation_sharpe": float(m.get("sharpe", 0.0)),
            "sharpe_delta": float(m.get("sharpe", 0.0) - base_metrics.get("sharpe", 0.0)),
            "return_delta": float(m.get("return", m.get("total_return", 0.0))
                                  - base_metrics.get("return", base_metrics.get("total_return", 0.0))),
            "drawdown_delta": float(m.get("max_drawdown", 0.0) - base_metrics.get("max_drawdown", 0.0)),
        })
    out = pd.DataFrame(rows, columns=["feature", "base_sharpe", "ablation_sharpe",
                                      "sharpe_delta", "return_delta", "drawdown_delta"])
    if len(out):
        out = out.sort_values("sharpe_delta").reset_index(drop=True)
    return out


def run_ablation(train_fn, metric_fn, feature_groups: dict[str, list[str]],
                 base_features: list[str]) -> pd.DataFrame:
    """train_fn(features)->model, metric_fn(model)->metrics sozlesmesiyle calisir.

    Her grup (veya tek feature) cikarilip yeniden egitilir; fark raporlanir.
    """
    base_model = train_fn(list(base_features))
    base_metrics = metric_fn(base_model)
    ablated = {}
    for name, group in feature_groups.items():
        remaining = [f for f in base_features if f not in group]
        if not remaining:
            continue
        ablated[name] = metric_fn(train_fn(remaining))
    return ablation_report(base_metrics, ablated)


def shap_stability_report(shap_by_fold: dict[str, list[float]]) -> pd.DataFrame:
    """Fold bazli mean(|SHAP|) degerlerinden stabilite.

    Cikti: feature | mean_shap | std_shap | cv_shap | mean_rank | rank_std.
    """
    feats = list(shap_by_fold.keys())
    if not feats:
        return pd.DataFrame(columns=["feature", "mean_shap", "std_shap",
                                     "cv_shap", "mean_rank", "rank_std"])
    n_folds = max(len(v) for v in shap_by_fold.values())
    ranks_per_fold: list[dict[str, float]] = []
    for f in range(n_folds):
        vals = {feat: abs(shap_by_fold[feat][f]) if f < len(shap_by_fold[feat]) else 0.0
                for feat in feats}
        ordered = sorted(vals, key=lambda k: vals[k], reverse=True)
        ranks_per_fold.append({feat: float(rank + 1) for rank, feat in enumerate(ordered)})
    rows = []
    for feat in feats:
        arr = np.asarray([abs(v) for v in shap_by_fold[feat]], dtype=float)
        ranks = np.asarray([r[feat] for r in ranks_per_fold], dtype=float)
        mean = float(arr.mean()) if len(arr) else 0.0
        std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
        rows.append({"feature": feat, "mean_shap": mean, "std_shap": std,
                     "cv_shap": float(std / mean) if mean > 1e-12 else 0.0,
                     "mean_rank": float(ranks.mean()),
                     "rank_std": float(ranks.std(ddof=1)) if len(ranks) > 1 else 0.0})
    out = pd.DataFrame(rows)
    return out.sort_values("mean_shap", ascending=False).reset_index(drop=True)
