"""Faz 6: PCA / PLS / Nonlinear Transformations (spec bolum 26-28).

Kural: scaler/PCA/PLS yalnizca train uzerinde fit edilir; valid/test transform.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def apply_pca(X_train: pd.DataFrame, X_other: pd.DataFrame | None = None,
              variance_threshold: float = 0.95, enabled: bool = False):
    """StandardScaler + PCA. Kapaliysa girdiyi aynen dondurur."""
    if not enabled:
        return {"X_train": X_train, "X_other": X_other, "n_components": X_train.shape[1],
                "explained_variance": [], "enabled": False}
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    if not 0 < variance_threshold <= 1.0:
        raise ValueError("variance_threshold (0,1] olmali.")
    scaler = StandardScaler().fit(X_train)
    Z_train = scaler.transform(X_train)
    pca = PCA(n_components=variance_threshold, random_state=42).fit(Z_train)
    out = {"X_train": pd.DataFrame(pca.transform(Z_train), index=X_train.index),
           "n_components": int(pca.n_components_),
           "explained_variance": [float(v) for v in pca.explained_variance_ratio_],
           "enabled": True, "scaler": scaler, "pca": pca}
    if X_other is not None:
        out["X_other"] = pd.DataFrame(pca.transform(scaler.transform(X_other)),
                                      index=X_other.index)
    else:
        out["X_other"] = None
    return out


def apply_pls(X_train, y_train, X_other=None, n_components: int = 5,
              enabled: bool = False):
    """PLSRegression; leakage'e karsi yalnizca train'de fit."""
    if not enabled:
        return {"X_train": X_train, "X_other": X_other, "enabled": False}
    from sklearn.cross_decomposition import PLSRegression
    from sklearn.preprocessing import StandardScaler

    n_components = max(1, min(int(n_components), min(np.asarray(X_train).shape) - 1 or 1))
    scaler = StandardScaler().fit(X_train)
    pls = PLSRegression(n_components=n_components).fit(scaler.transform(X_train), y_train)
    out = {"X_train": pd.DataFrame(pls.transform(scaler.transform(X_train)),
                                   index=pd.Index(range(len(np.asarray(X_train))))),
           "enabled": True, "n_components": n_components, "scaler": scaler, "pls": pls}
    out["X_other"] = (pd.DataFrame(pls.transform(scaler.transform(X_other)))
                      if X_other is not None else None)
    return out


def apply_transformations(X: pd.DataFrame, config: dict | None = None) -> pd.DataFrame:
    """tanh / sigmoid / threshold / winsorize. Hepsi config ile acilir-kapanir."""
    cfg = config or {}
    out = X.copy()
    if cfg.get("tanh"):
        out = np.tanh(out)
        out = pd.DataFrame(out, index=X.index, columns=X.columns)
    if cfg.get("sigmoid"):
        out = pd.DataFrame(1 / (1 + np.exp(-X.values)), index=X.index, columns=X.columns)
    if "threshold" in cfg and cfg["threshold"] is not None:
        thr = float(cfg["threshold"])
        out = out.clip(-thr, thr)
    wins = cfg.get("winsorize") or {}
    if isinstance(wins, dict) and wins.get("enabled"):
        lo, hi = float(wins.get("lower", 0.01)), float(wins.get("upper", 0.99))
        q_lo = out.quantile(lo)
        q_hi = out.quantile(hi)
        out = out.clip(q_lo, q_hi, axis=1)
    return out
