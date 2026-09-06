"""Faz 1: IC, IC Decay, Sign Consistency, Feature Quality Score.

Spec bolum 6-9. Spearman IC kullanilir; NaN guvenli, sabit kolon hatasiz.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

DEFAULT_IC_DECAY_HORIZONS = [1, 2, 3, 5, 10, 20]

DEFAULT_QUALITY_WEIGHTS = {"ic": 0.50, "sign_consistency": 0.30, "stability": 0.20}


def _safe_spearman(a: pd.Series, b: pd.Series) -> tuple[float, int]:
    paired = pd.DataFrame({"f": a, "t": b}).dropna()
    n = len(paired)
    if n < 3 or paired["f"].nunique() < 2 or paired["t"].nunique() < 2:
        return 0.0, n
    try:
        stat = spearmanr(paired["f"], paired["t"]).statistic
    except Exception:
        return 0.0, n
    if stat is None or not np.isfinite(stat):
        return 0.0, n
    return float(np.clip(stat, -1.0, 1.0)), n


def calculate_ic(feature: pd.Series, target: pd.Series) -> float:
    """Tek feature icin Spearman IC (-1..+1). NaN temizlenir, sabit kolon 0 doner."""
    ic, _ = _safe_spearman(feature, target)
    return ic


def calculate_feature_ic(X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    """Tum kolonlar icin IC tablosu: feature | ic | abs_ic | sample_count."""
    rows = []
    for col in X.columns:
        ic, n = _safe_spearman(X[col], y)
        rows.append({"feature": col, "ic": ic, "abs_ic": abs(ic), "sample_count": n})
    out = pd.DataFrame(rows, columns=["feature", "ic", "abs_ic", "sample_count"])
    return out.sort_values("abs_ic", ascending=False).reset_index(drop=True)


def calculate_ic_decay(
    feature: pd.Series,
    target: pd.Series,
    horizons: list[int] | None = None,
) -> pd.DataFrame:
    """Feature'in ileri horizonlardaki IC'si.

    ``target`` T+1 hedefidir; horizon h icin hedef ``target.shift(-(h-1))``
    ile hizalanir (T+h getirisi yaklasiklanir). Negatif/sifir horizon hata verir.
    """
    horizons = list(horizons) if horizons else list(DEFAULT_IC_DECAY_HORIZONS)
    if any(not isinstance(h, int) or h < 1 for h in horizons):
        raise ValueError("horizons pozitif tam sayi olmali.")
    name = feature.name if feature.name else "feature"
    rows = []
    for h in horizons:
        shifted = target.shift(-(h - 1))
        ic, n = _safe_spearman(feature, shifted)
        rows.append({"feature": name, "horizon": h, "ic": ic, "sample_count": n})
    return pd.DataFrame(rows, columns=["feature", "horizon", "ic", "sample_count"])


def calculate_sign_consistency(fold_ic_values: list[float]) -> float:
    """Baskin isaret orani: dominant_sign_count / valid_fold_count."""
    vals = [v for v in fold_ic_values if v is not None and np.isfinite(v) and v != 0]
    if not vals:
        return 0.0
    pos = sum(1 for v in vals if v > 0)
    neg = len(vals) - pos
    return max(pos, neg) / len(vals)


def sign_consistency_report(fold_ic_by_feature: dict[str, list[float]]) -> pd.DataFrame:
    """Cikti: feature | mean_ic | median_ic | ic_std | positive_ratio |
    negative_ratio | sign_consistency."""
    rows = []
    for feat, vals in fold_ic_by_feature.items():
        clean = [float(v) for v in vals if v is not None and np.isfinite(v)]
        if not clean:
            rows.append({"feature": feat, "mean_ic": 0.0, "median_ic": 0.0,
                         "ic_std": 0.0, "positive_ratio": 0.0,
                         "negative_ratio": 0.0, "sign_consistency": 0.0})
            continue
        arr = np.asarray(clean, dtype=float)
        rows.append({
            "feature": feat,
            "mean_ic": float(arr.mean()),
            "median_ic": float(np.median(arr)),
            "ic_std": float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
            "positive_ratio": float((arr > 0).mean()),
            "negative_ratio": float((arr < 0).mean()),
            "sign_consistency": calculate_sign_consistency(clean),
        })
    return pd.DataFrame(rows, columns=["feature", "mean_ic", "median_ic", "ic_std",
                                       "positive_ratio", "negative_ratio", "sign_consistency"])


def feature_quality_score(abs_ic: float, sign_consistency: float,
                           stability_score: float,
                           weights: dict | None = None) -> float:
    """Spec bolum 9: 0.50*|IC| + 0.30*sign_consistency + 0.20*stability."""
    w = weights or DEFAULT_QUALITY_WEIGHTS
    return (w.get("ic", 0.5) * min(1.0, max(0.0, abs_ic))
            + w.get("sign_consistency", 0.3) * min(1.0, max(0.0, sign_consistency))
            + w.get("stability", 0.2) * min(1.0, max(0.0, stability_score)))


def feature_quality_report(ic_df: pd.DataFrame,
                            consistency_df: pd.DataFrame,
                            stability_by_feature: dict[str, float] | None = None,
                            weights: dict | None = None) -> pd.DataFrame:
    """IC + sign consistency + stability'yi tek tabloda birlestirir."""
    stability_by_feature = stability_by_feature or {}
    cons = consistency_df.set_index("feature") if len(consistency_df) else pd.DataFrame()
    rows = []
    for _, r in ic_df.iterrows():
        feat = r["feature"]
        sc = float(cons.loc[feat, "sign_consistency"]) if feat in cons.index else 0.0
        stab = float(stability_by_feature.get(feat, 0.0))
        rows.append({"feature": feat, "ic": float(r["ic"]), "abs_ic": float(r["abs_ic"]),
                     "sign_consistency": sc, "stability_score": stab,
                     "quality_score": feature_quality_score(float(r["abs_ic"]), sc, stab, weights)})
    out = pd.DataFrame(rows)
    if len(out):
        out = out.sort_values("quality_score", ascending=False).reset_index(drop=True)
    return out
