"""Faz 4: Probability Calibration + Quantile Regression (spec bolum 19-20).

Yeni agir dependency yok: sklearn CalibratedClassifierCV + GradientBoosting
quantile kullanilir; LightGBM quantile objective varsa tercih edilir.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def calibrate_probabilities(y_true, y_prob, method: str = "isotonic", cv: int = 3):
    """Platt (sigmoid) veya isotonic kalibrasyon, capraz-fit (out-of-fold).

    CalibratedClassifierCV bir siniflandirici istedigi icin burada dogrudan
    IsotonicRegression / LogisticRegression (Platt) kullanilir; her fold
    diger fold'larda fit edilip kendi uzerinde tahmin uretir (sızıntı yok).
    """
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold

    if method not in ("sigmoid", "isotonic"):
        raise ValueError("method 'sigmoid' veya 'isotonic' olmali.")
    y_true = np.asarray(y_true)
    y_prob = np.clip(np.asarray(y_prob, dtype=float), 1e-6, 1 - 1e-6)
    if len(y_true) != len(y_prob):
        raise ValueError("Uzunluklar uyusmuyor.")
    if len(np.unique(y_true)) < 2:
        raise ValueError("Kalibrasyon icin iki sinif gerekli.")
    n = len(y_true)
    cv = max(2, min(int(cv), n))
    skf = StratifiedKFold(n_splits=cv, shuffle=False)
    out = np.empty(n, dtype=float)
    for tr, va in skf.split(y_prob.reshape(-1, 1), y_true):
        if method == "isotonic":
            iso = IsotonicRegression(out_of_bounds="clip").fit(y_prob[tr], y_true[tr])
            out[va] = iso.predict(y_prob[va])
        else:  # Platt scaling
            lr = LogisticRegression().fit(y_prob[tr].reshape(-1, 1), y_true[tr])
            out[va] = lr.predict_proba(y_prob[va].reshape(-1, 1))[:, 1]
    return np.clip(out, 0.0, 1.0)


def calibration_metrics(y_true, y_prob, calibrated=None, n_bins: int = 10) -> dict:
    """Brier, log-loss ve calibration curve dondurur."""
    from sklearn.metrics import brier_score_loss, log_loss
    from sklearn.calibration import calibration_curve

    y_true = np.asarray(y_true)
    y_prob = np.clip(np.asarray(y_prob, dtype=float), 1e-9, 1 - 1e-9)
    out = {"brier_raw": float(brier_score_loss(y_true, y_prob)),
           "log_loss_raw": float(log_loss(y_true, y_prob))}
    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins)
    out["curve_raw"] = {"prob_true": prob_true.tolist(), "prob_pred": prob_pred.tolist()}
    if calibrated is not None:
        cal = np.clip(np.asarray(calibrated, dtype=float), 1e-9, 1 - 1e-9)
        out["brier_calibrated"] = float(brier_score_loss(y_true, cal))
        out["log_loss_calibrated"] = float(log_loss(y_true, cal))
        pt, pp = calibration_curve(y_true, cal, n_bins=n_bins)
        out["curve_calibrated"] = {"prob_true": pt.tolist(), "prob_pred": pp.tolist()}
    return out


class QuantilePredictor:
    """P10/P50/P90 belirsizlik araligi. Tercih: LightGBM quantile, yoksa sklearn GBR."""

    def __init__(self, quantiles: tuple[float, ...] = (0.1, 0.5, 0.9), seed: int = 42):
        if not quantiles or any(not 0 < q < 1 for q in quantiles):
            raise ValueError("quantiles (0,1) araliginda olmali.")
        self.quantiles = tuple(sorted(quantiles))
        self.seed = seed
        self.models: dict[float, object] = {}

    def _make(self, q: float):
        try:
            from lightgbm import LGBMRegressor
            return LGBMRegressor(objective="quantile", alpha=q, n_estimators=100,
                                 random_state=self.seed, verbosity=-1)
        except Exception:
            from sklearn.ensemble import GradientBoostingRegressor
            return GradientBoostingRegressor(loss="quantile", alpha=q, random_state=self.seed)

    def fit(self, X, y):
        Xa = np.asarray(X)
        ya = np.asarray(y, dtype=float)
        for q in self.quantiles:
            self.models[q] = self._make(q).fit(Xa, ya)
        return self

    def predict(self, X) -> pd.DataFrame:
        Xa = np.asarray(X)
        data = {f"p{int(q * 100)}": np.asarray(self.models[q].predict(Xa), dtype=float)
                for q in self.quantiles}
        return pd.DataFrame(data)
