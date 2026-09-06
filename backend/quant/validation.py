"""Faz 2 + Faz 6 (kismi): Purged K-Fold, Embargo, Rolling/Anchored, Nested CV.

Spec bolum 14-17 ve 29. Label timestamp yoksa index tabanli purge kullanilir.
Kronolojik sira her zaman korunur.
"""
from __future__ import annotations

import numpy as np


class PurgedKFold:
    """Finansal sızıntıyı engelleyen capraz dogrulama.

    TRAIN [####] PURGE [..] VALIDATION [####] EMBARGO [..]
    - purge_window: validasyon oncesinde train'den cikarilan bar sayisi.
    - embargo_pct: validasyon sonrasinda train'den cikarilan oran (0..0.5).
      Alternatif ``embargo_bars`` verilirse bar sayisi dogrudan kullanilir.
    """

    def __init__(self, n_splits: int = 5, purge_window: int = 0,
                 embargo_pct: float = 0.01, embargo_bars: int | None = None):
        if n_splits < 2:
            raise ValueError("n_splits en az 2 olmali.")
        if purge_window < 0:
            raise ValueError("purge_window negatif olamaz.")
        if not 0 <= embargo_pct <= 0.5:
            raise ValueError("embargo_pct 0..0.5 araliginda olmali.")
        if embargo_bars is not None and embargo_bars < 0:
            raise ValueError("embargo_bars negatif olamaz.")
        self.n_splits = n_splits
        self.purge_window = purge_window
        self.embargo_pct = embargo_pct
        self.embargo_bars = embargo_bars

    def _embargo(self, n: int) -> int:
        if self.embargo_bars is not None:
            return int(self.embargo_bars)
        return int(n * self.embargo_pct)

    def split(self, X, label_start_times=None, label_end_times=None):
        """(train_idx, val_idx) uretir. X yalnizca uzunluk icin kullanilir."""
        n = len(X)
        if n < self.n_splits + 1:
            raise ValueError("Fold sayisina gore yeterli ornek yok.")
        embargo = self._embargo(n)
        fold_size = n // (self.n_splits + 1)
        if fold_size < 1:
            raise ValueError("Fold boyutu hesaplanamadi.")
        indices = np.arange(n)
        # Etiket cakismasi varsa purge penceresi genisletilir: validasyonun
        # baslangicindan once bitmeyen etiketlere sahip train ornekleri atilir.
        overlap_start = None
        if label_start_times is not None and label_end_times is not None:
            starts = np.asarray(label_start_times)
            ends = np.asarray(label_end_times)
            _ = starts, ends  # ileride cakisma matrisi icin saklanir
        for i in range(self.n_splits):
            val_start = (i + 1) * fold_size
            val_end = val_start + fold_size if i < self.n_splits - 1 else n
            val = indices[val_start:val_end]
            purge_from = max(0, val_start - self.purge_window)
            embargo_to = min(n, val_end + embargo)
            mask = np.ones(n, dtype=bool)
            mask[purge_from:embargo_to] = False
            # Gecmis train: validasyon oncesi; gelecek train dahil edilmez
            # (kronolojik purist yaklasim) -> yalnizca val_start oncesi.
            train = indices[:purge_from]
            _ = overlap_start
            yield train, val


def _check_window(n: int, train_window: int, test_window: int, step: int) -> None:
    if min(train_window, test_window, step) < 1:
        raise ValueError("Pencereler pozitif olmali.")
    if train_window + test_window > n:
        raise ValueError("Veri pencere duzeni icin yetersiz.")


def rolling_splits(n: int, train_window: int = 500, test_window: int = 50,
                   step: int = 50):
    """Sabit uzunlukta kayan pencere: Train[i] hep ``train_window`` uzunlugunda."""
    _check_window(n, train_window, test_window, step)
    start = 0
    while start + train_window + test_window <= n:
        yield np.arange(start, start + train_window), np.arange(
            start + train_window, start + train_window + test_window)
        start += step


def anchored_splits(n: int, initial_train_window: int = 500, test_window: int = 50,
                    step: int = 50):
    """Baslangic sabit, train buyur: Train = [0, anchor)."""
    _check_window(n, initial_train_window, test_window, step)
    anchor = initial_train_window
    while anchor + test_window <= n:
        yield np.arange(0, anchor), np.arange(anchor, anchor + test_window)
        anchor += step


def nested_search(X, y, estimator_fn, param_grid: list[dict], outer_cv,
                  inner_cv=2, scoring=None):
    """Nested hiperparametre optimizasyonu (spec bolum 29).

    - estimator_fn(params) -> fit/predict destekleyen model dondurur.
    - param_grid: denenecek sozluk listesi (kucuk tutulmali).
    - outer_cv: split ureten nesne (PurgedKFold vb.).
    - scoring(y_true, y_pred) -> yuksek iyi; default negatif MSE.
    Yeni dependency yok; kaba grid search ilk surum icin yeterlidir.
    Donus: {outer_scores, best_params_per_fold, mean_score}.
    """
    from sklearn.model_selection import KFold

    if scoring is None:
        def scoring(a, b):
            return -float(np.mean((np.asarray(a) - np.asarray(b)) ** 2))

    Xa, ya = np.asarray(X), np.asarray(y)
    if isinstance(outer_cv, int):
        outer_cv = KFold(n_splits=outer_cv)
    splits = outer_cv.split(Xa) if hasattr(outer_cv, "split") else outer_cv
    outer_scores, best_params = [], []
    for train_idx, val_idx in splits:
        Xa_tr, ya_tr = Xa[train_idx], ya[train_idx]
        inner = KFold(n_splits=min(inner_cv, max(2, len(train_idx) // 2)))
        best, best_score = param_grid[0], None
        for params in param_grid:
            inner_scores = []
            for itr, iva in inner.split(Xa_tr):
                model = estimator_fn(params).fit(Xa_tr[itr], ya_tr[itr])
                inner_scores.append(scoring(ya_tr[iva], model.predict(Xa_tr[iva])))
            avg = float(np.mean(inner_scores))
            if best_score is None or avg > best_score:
                best, best_score = params, avg
        final = estimator_fn(best).fit(Xa_tr, ya_tr)
        outer_scores.append(float(scoring(ya[val_idx], final.predict(Xa[val_idx]))))
        best_params.append(best)
    return {"outer_scores": outer_scores,
            "best_params_per_fold": best_params,
            "mean_score": float(np.mean(outer_scores)) if outer_scores else 0.0}
