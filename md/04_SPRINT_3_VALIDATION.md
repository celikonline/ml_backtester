# SPRINT 3 — LEAKAGE-SAFE VALIDATION

## Sprint Hedefi

Walk-forward altyapısını koruyarak finansal zaman serileri için leakage riskini azaltmak.

---

# 1. Purged K-Fold

## Problem

Label horizon'ları train ve validation sample'ları arasında zaman olarak çakışabilir.

Normal K-Fold bu durumda geleceğe ait bilgi sızıntısı yaratabilir.

---

## 2. Sınıf

```python
class PurgedKFold:
    def __init__(
        self,
        n_splits: int = 5,
        purge_window: int = 0,
        embargo_pct: float = 0.01
    ):
        ...
```

---

## 3. Split Interface

```python
split(
    X,
    label_start_times=None,
    label_end_times=None
)
```

İlk sürümde timestamp metadata yoksa index tabanlı purge uygulanabilir.

---

## 4. Görsel Mantık

```text
TRAIN
████████████████

PURGE
                ░░

VALIDATION
                  ████

EMBARGO
                      ░░
```

---

# 5. Embargo

Config:

```yaml
validation:
  purged_kfold:
    enabled: true
    n_splits: 5
    purge_window: 5
    embargo_pct: 0.01
```

İlk sürümde `embargo_pct` yeterlidir.

---

# 6. Rolling Retraining

```yaml
retraining:
  mode: rolling
  train_window: 500
  test_window: 50
  step: 50
```

Mantık:

```text
Train Window → Test
      Train Window → Test
             Train Window → Test
```

---

# 7. Anchored Retraining

```yaml
retraining:
  mode: anchored
  initial_train_window: 500
  test_window: 50
  step: 50
```

Mantık:

```text
START ───────── Train → Test
START ─────────────── Train → Test
START ───────────────────── Train → Test
```

---

# 8. Leakage Kuralları

Aşağıdaki objeler yalnızca TRAIN üzerinde fit edilmeli:

```text
Scaler
PCA
PLS
Feature Selector
Clustering Decision
Calibration Model
Hyperparameter Search
```

Validation ve test sadece transform/predict için kullanılmalıdır.

---

# 9. Final Holdout

Final holdout:

```text
MODEL SELECTION TAMAMLANDIKTAN SONRA
SADECE BİR KEZ
```

kullanılmalıdır.

GA, HPO veya feature selection final holdout sonucunu görmemelidir.

---

# 10. Validation Artifact

Her fold için:

```json
{
  "fold": 1,
  "train_start": "...",
  "train_end": "...",
  "validation_start": "...",
  "validation_end": "...",
  "purged_samples": 20,
  "embargo_samples": 10,
  "metrics": {
    "sharpe": 1.4,
    "return": 0.12,
    "max_drawdown": 0.07
  }
}
```

---

# 11. Minimum Testler

```text
test_no_train_validation_overlap
test_purge_applied
test_embargo_applied
test_time_order_preserved
test_rolling_window_size
test_anchored_start_fixed
test_final_holdout_not_seen
```

---

# 12. Definition of Done

```text
[x] Purged K-Fold çalışıyor
[x] Embargo çalışıyor
[x] Walk-forward bozulmadı
[x] Rolling retraining çalışıyor
[x] Anchored retraining çalışıyor
[x] Fold artifact oluşuyor
[x] Leakage testleri geçiyor
[x] Final holdout izolasyonu doğrulandı
```

## Uygulama notları (2026-09)

- `PurgedKFold` + `rolling/anchored_splits` `backend/quant/validation.py` içindeydi;
  bu sprintte `backend/platform/research.py:splits()` üzerinden deney hattına bağlandı.
- Yöntem seçimi `ValidationSpec.method` ile yapılır:
  `holdout | walk_forward | purged_kfold | rolling | anchored`
  (+ `purge_window`, `embargo_pct`, `train_window`, `test_window`, `step`).
- Fold artifact her fold için `purged_samples` / `embargo_samples` taşır
  (`optimization_candidates.fold_metrics`).
- Leakage kuralı (madde 8) kodla zorlanır: her fold kendi train diliminde
  `ModelAdapter.fit` yapar; scaler pipeline içindedir, validasyon/teste fit yok.
- Final holdout izolasyonu: sealed test + `test_final_holdout_not_seen`.
- Bütçe muhasebesi gerçek fold sayısını kullanır (`count_splits`).
- Testler: `tests/test_validation_sprint3.py` (10 test).
