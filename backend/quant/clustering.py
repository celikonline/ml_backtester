"""Faz 1: Feature Clustering + Redundancy Pruning (spec bolum 10-11).

Spearman korelasyon + hierarchical clustering.
Distance = 1 - |correlation|. scipy yoksa greedy fallback kullanilir.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _spearman_corr(X: pd.DataFrame) -> pd.DataFrame:
    return X.corr(method="spearman").fillna(0.0)


def cluster_features(X: pd.DataFrame, threshold: float = 0.85) -> dict[str, list[str]]:
    """Korelasyonu yuksek feature'lari gruplar.

    threshold: ayni cluster icin minimum |correlation| (0..1).
    Donus: {cluster_id: [feature, ...]}.
    """
    if X.empty or len(X.columns) == 0:
        return {}
    if not 0 < threshold <= 1.0:
        raise ValueError("threshold (0, 1] araliginda olmali.")
    cols = list(X.columns)
    if len(cols) == 1:
        return {"cluster_0": cols}
    corr = _spearman_corr(X).values
    distance = 1.0 - np.abs(corr)
    try:
        from scipy.cluster.hierarchy import fcluster, linkage
        from scipy.spatial.distance import squareform
        condensed = squareform(distance, checks=False)
        # threshold korelasyon -> mesafe esigi
        linkage_mat = linkage(condensed, method="average")
        labels = fcluster(linkage_mat, t=1.0 - threshold, criterion="distance")
    except Exception:
        # Greedy fallback: baglantili bilesenler
        labels = _greedy_labels(np.abs(corr), threshold, len(cols))
    clusters: dict[str, list[str]] = {}
    for col, lab in zip(cols, labels):
        clusters.setdefault(f"cluster_{int(lab)}", []).append(col)
    return clusters


def _greedy_labels(abs_corr: np.ndarray, threshold: float, n: int) -> list[int]:
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if abs_corr[i, j] >= threshold:
                union(i, j)
    mapping: dict[int, int] = {}
    out = []
    for i in range(n):
        r = find(i)
        mapping.setdefault(r, len(mapping) + 1)
        out.append(mapping[r])
    return out


def prune_redundant_features(
    X: pd.DataFrame,
    feature_metrics: pd.DataFrame,
    clusters: dict[str, list[str]],
) -> list[str]:
    """Her cluster'dan en iyi feature'u sec.

    Oncelik: 1) en yuksek abs(IC) 2) en yuksek sign_consistency 3) en dusuk missing ratio.
    ``feature_metrics`` kolonlari: feature, abs_ic (zorunlu); sign_consistency,
    missing_ratio opsiyonel. Donus yalnizca secilen isimlerdir.
    """
    if "feature" not in feature_metrics.columns or "abs_ic" not in feature_metrics.columns:
        raise ValueError("feature_metrics 'feature' ve 'abs_ic' kolonu icermeli.")
    table = feature_metrics.set_index("feature")
    selected: list[str] = []
    for _, members in sorted(clusters.items()):
        best, best_key = None, None
        for feat in members:
            if feat not in table.index:
                key = (0.0, 0.0, 0.0)
            else:
                row = table.loc[feat]
                key = (float(row.get("abs_ic", 0.0)),
                       float(row.get("sign_consistency", 0.0)),
                       -float(row.get("missing_ratio", row.get("missingness", 0.0))))
            if best_key is None or key > best_key:
                best, best_key = feat, key
        if best is not None:
            selected.append(best)
    # Cluster disi kalan kolonlar korunur (bilgi kaybi olmasin).
    clustered = {f for members in clusters.values() for f in members}
    for col in X.columns:
        if col not in clustered:
            selected.append(col)
    return selected
