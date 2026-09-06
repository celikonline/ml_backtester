# SPRINT 1 — FEATURE STABILITY

## Sprint Hedefi

Yeni model eklemeden önce feature kalitesini ölçen ve gereksiz feature'ları eleyen bir katman oluşturmak.

---

# 1. Information Coefficient

## Amaç
Feature ile gelecekteki hedef arasındaki monoton ilişkiyi ölçmek.

İlk sürüm:

```python
Spearman Correlation
```

### Fonksiyon

```python
calculate_ic(
    feature: pd.Series,
    target: pd.Series
) -> float
```

### Çoklu Feature

```python
calculate_feature_ic(
    X: pd.DataFrame,
    y: pd.Series
) -> pd.DataFrame
```

### Output

```text
feature
ic
abs_ic
sample_count
```

### Acceptance Criteria
- NaN güvenli
- Constant feature hata üretmez
- Sonuç [-1, 1]
- Testleri var

---

# 2. IC Decay

## Amaç

Bir feature'ın tahmin gücünün kaç horizon boyunca devam ettiğini görmek.

Default:

```python
horizons = [1, 2, 3, 5, 10, 20]
```

### Output

```text
feature
horizon
ic
sample_count
```

---

# 3. Sign Consistency

## Amaç

Feature IC işaretinin farklı fold'larda tutarlı olup olmadığını görmek.

### Hesap

```text
dominant_sign_count / valid_fold_count
```

### Output

```text
feature
mean_ic
median_ic
ic_std
positive_ratio
negative_ratio
sign_consistency
```

---

# 4. Feature Quality Score

İlk sürüm:

```text
quality =
0.50 * normalized_abs_ic
+ 0.30 * sign_consistency
+ 0.20 * stability_score
```

Ağırlıklar config'ten okunmalıdır.

---

# 5. Feature Clustering

## Yaklaşım

```text
Spearman correlation
↓
distance = 1 - abs(correlation)
↓
hierarchical clustering
```

### Fonksiyon

```python
cluster_features(
    X: pd.DataFrame,
    threshold: float = 0.85
) -> dict[str, list[str]]
```

---

# 6. Redundancy Pruning

Cluster içindeki feature seçim önceliği:

1. Highest abs(IC)
2. Highest sign consistency
3. Lowest missing ratio

### Fonksiyon

```python
prune_redundant_features(
    X,
    feature_metrics,
    clusters
) -> list[str]
```

---

# 7. Experiment Artifact'ları

Sprint sonunda aşağıdaki artifact tipleri eklenmelidir:

```text
ic_report
ic_decay_report
feature_stability_report
feature_cluster_report
selected_feature_list
```

---

# 8. API

Mevcut API standardına uy.

Öneri:

```text
POST /api/features/ic
POST /api/features/ic-decay
POST /api/features/stability
POST /api/features/clustering
POST /api/features/prune
```

---

# 9. Minimum Testler

```text
test_positive_ic
test_negative_ic
test_nan_handling
test_constant_feature

test_ic_decay_horizons
test_ic_decay_no_future_leak

test_sign_consistency_positive
test_sign_consistency_mixed

test_correlated_features_same_cluster
test_independent_features_separate

test_redundancy_pruning
```

---

# 10. Definition of Done

```text
[ ] IC çalışıyor
[ ] IC Decay çalışıyor
[ ] Sign Consistency çalışıyor
[ ] Feature Quality Report oluşuyor
[ ] Clustering çalışıyor
[ ] Redundancy Pruning çalışıyor
[ ] Experiment artifact'ları kaydediliyor
[ ] API endpoint'leri çalışıyor
[ ] Unit testler geçiyor
[ ] Mevcut testlerde regresyon yok
```

---

# 11. Agent Çalışma Sırası

```text
Task 1 → IC
Task 2 → IC Decay
Task 3 → Sign Consistency
Task 4 → Quality Score
Task 5 → Clustering
Task 6 → Pruning
Task 7 → Registry
Task 8 → API
Task 9 → Tests
```

Bir task tamamlanmadan diğerine geçme.
