# Düşük Güçlü Yapay Zekâ İçin Quant Research Platform Uygulama Spesifikasyonu

## 1. Amaç

Bu doküman, düşük güçlü / küçük bir yapay zekâ modelinin ek soru sormadan adım adım geliştirebileceği şekilde hazırlanmış bir uygulama spesifikasyonudur.

Hedef, mevcut quant araştırma uygulamasını bozmadan aşağıdaki eksik ama kısa sürede uygulanabilir özellikleri eklemektir:

1. Information Coefficient (IC)
2. IC Decay
3. Feature Sign Consistency
4. Feature Clustering
5. Redundancy Pruning
6. Feature Ablation
7. SHAP Stability
8. Purged K-Fold
9. Embargo
10. Rolling Retraining
11. Anchored Retraining
12. Probability Calibration
13. Quantile Regression
14. Slippage / Latency Stress Test
15. Systematic Stress Testing
16. PCA
17. PLS
18. Nested Hyperparameter Optimization

Bu çalışma ilk aşamada yeni ücretli veri kaynağı gerektirmemelidir.

---

# 2. Ana Geliştirme Prensibi

Düşük güçlü yapay zekâ modeli aynı anda büyük değişiklikler yapmamalıdır.

Her görev şu sırayla yapılmalıdır:

```text
1. İlgili dosyaları bul
2. Mevcut kodu oku
3. Küçük değişiklik yap
4. Unit test yaz
5. Testleri çalıştır
6. Hata yoksa bir sonraki göreve geç
```

Kesinlikle:

- Tüm projeyi yeniden yazma.
- Çalışan modülleri gereksiz yere refactor etme.
- Mevcut API sözleşmelerini bozma.
- Mevcut model pipeline'ını değiştirmeden yeni modül eklemeyi tercih et.
- Aynı anda en fazla bir feature geliştir.
- Büyük dosyalar oluşturma.
- Bir dosya mümkünse 300-400 satırı geçmesin.
- Ortak yardımcı fonksiyonları `utils` altında tut.
- Her yeni özelliğe test ekle.
- Hata oluşursa önce mevcut görevi düzelt, başka göreve geçme.

---

# 3. Mevcut Sistem Varsayımı

Uygulamada aşağıdaki ana katmanların bulunduğu varsayılacaktır:

```text
Data Ingestion
      ↓
Data Cleaning
      ↓
Feature Engineering
      ↓
Feature Selection
      ↓
Regime Detection
      ↓
Model Training
      ↓
Validation
      ↓
Optimization
      ↓
Backtest
      ↓
Final Holdout
      ↓
Experiment Registry
```

Mevcut durumda sistemde aşağıdaki yetenekler bulunmaktadır veya kısmen bulunmaktadır:

- CSV veri yükleme
- OHLC veri desteği
- Makro / FX / rates / cross-asset kolon aileleri
- Point-in-time veri yaklaşımı
- Snapshot ve SHA-256 hash
- Lag / delta / return feature'ları
- Rolling istatistikler
- Gaussian HMM
- Ridge
- Random Forest
- Histogram Gradient Boosting
- XGBoost
- LightGBM
- Kısmi stacking / blending
- Walk-forward validation
- Kısmi nested time-series CV
- Transaction cost desteği
- Kısmi slippage / latency desteği
- Final holdout
- Genetic Algorithm
- Kısmi Hyperparameter Optimization
- Kısmi stress testing
- Kısmi SHAP / permutation importance
- Experiment registry
- Workspace izolasyonu

---

# 4. Önerilen Teknoloji Yapısı

Backend:

```text
Python 3.11+
FastAPI
Pandas
NumPy
SciPy
scikit-learn
XGBoost
LightGBM
SHAP
SQLAlchemy
Pydantic
pytest
```

Opsiyonel:

```text
Optuna
joblib
SQLite veya PostgreSQL
```

Frontend mevcut React uygulaması ise yeni ekranlar mevcut yapıya eklenmelidir.

Yeni framework eklenmemelidir.

---

# 5. Önerilen Klasör Yapısı

```text
app/
├── api/
│   ├── feature_analysis.py
│   ├── validation.py
│   ├── calibration.py
│   └── stress_test.py
│
├── core/
│   ├── config.py
│   └── logging.py
│
├── data/
│   ├── loader.py
│   ├── snapshot.py
│   └── point_in_time.py
│
├── features/
│   ├── engineering.py
│   ├── ic.py
│   ├── stability.py
│   ├── clustering.py
│   ├── ablation.py
│   ├── dimensionality.py
│   └── transformations.py
│
├── models/
│   ├── trainer.py
│   ├── registry.py
│   ├── calibration.py
│   ├── quantile.py
│   └── ensemble.py
│
├── validation/
│   ├── walk_forward.py
│   ├── purged_kfold.py
│   ├── embargo.py
│   ├── rolling.py
│   └── nested_cv.py
│
├── backtest/
│   ├── engine.py
│   ├── costs.py
│   ├── slippage.py
│   └── stress.py
│
├── optimization/
│   ├── genetic.py
│   └── hyperparameter.py
│
├── experiments/
│   ├── registry.py
│   └── artifacts.py
│
└── tests/
```

Mevcut proje yapısı farklıysa klasörler zorla değiştirilmemelidir. Bu yapı yalnızca referanstır.

---

# 6. Sprint 1 — Feature Quality ve Leakage Kontrolü

## 6.1 Information Coefficient

### Amaç

Bir feature ile gelecekteki hedef getiri arasındaki tahmin gücünü ölçmek.

### İlk versiyon

Spearman correlation kullanılmalıdır.

```python
IC = spearmanr(feature, target)
```

### Fonksiyon

```python
calculate_ic(
    feature: pd.Series,
    target: pd.Series
) -> float
```

### Çoklu feature

```python
calculate_feature_ic(
    X: pd.DataFrame,
    y: pd.Series
) -> pd.DataFrame
```

### Çıktı

```text
feature
ic
abs_ic
sample_count
```

### Acceptance Criteria

- NaN değerler güvenli şekilde temizlenmeli.
- Sabit kolon hata vermemeli.
- Sonuç -1 ile +1 arasında olmalı.
- Unit test bulunmalı.

---

# 7. IC Decay

## Amaç

Feature'ın gelecekte kaç periyot boyunca tahmin gücü taşıdığını görmek.

Örnek:

```text
momentum_20

T+1   IC = 0.081
T+2   IC = 0.064
T+3   IC = 0.041
T+5   IC = 0.018
T+10  IC = 0.002
```

### Fonksiyon

```python
calculate_ic_decay(
    feature: pd.Series,
    target: pd.Series,
    horizons: list[int]
) -> pd.DataFrame
```

### Default horizons

```python
[1, 2, 3, 5, 10, 20]
```

### Çıktı

```text
feature
horizon
ic
sample_count
```

---

# 8. Feature Sign Consistency

## Amaç

Bir feature'ın farklı zaman pencerelerinde aynı yönde çalışıp çalışmadığını ölçmek.

Örneğin:

```text
Fold 1 IC = +0.07
Fold 2 IC = +0.05
Fold 3 IC = +0.09
Fold 4 IC = +0.02
```

Sign consistency:

```text
100%
```

### Formül

```python
dominant_sign_count / valid_fold_count
```

### Fonksiyon

```python
calculate_sign_consistency(
    fold_ic_values: list[float]
) -> float
```

### Çıktı

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

# 9. Feature Quality Score

Genetic Algorithm yalnızca Sharpe ile optimize edilmemelidir.

İlk versiyonda aşağıdaki normalize edilmiş skor kullanılabilir:

```text
feature_quality_score =
    0.50 * abs(IC)
  + 0.30 * sign_consistency
  + 0.20 * stability_score
```

Daha sonra GA fitness fonksiyonu şu yapıya genişletilebilir:

```text
fitness =
    w1 * sharpe
  + w2 * feature_quality
  - w3 * max_drawdown
  - w4 * turnover
```

Default:

```text
w1 = 0.50
w2 = 0.20
w3 = 0.20
w4 = 0.10
```

Weight değerleri config üzerinden değiştirilebilir olmalıdır.

---

# 10. Feature Clustering

## Amaç

Birbirine çok benzeyen feature'ları gruplamak.

İlk versiyonda:

```text
Spearman correlation
+
Hierarchical clustering
```

kullanılmalıdır.

### İşlem

```text
Feature Matrix
      ↓
Correlation Matrix
      ↓
Distance = 1 - abs(correlation)
      ↓
Hierarchical Clustering
      ↓
Feature Groups
```

### Fonksiyon

```python
cluster_features(
    X: pd.DataFrame,
    threshold: float = 0.85
) -> dict[str, list[str]]
```

---

# 11. Redundancy Pruning

Her cluster içinden en iyi feature seçilmelidir.

Öncelik:

```text
1. Highest abs(IC)
2. Highest sign consistency
3. Lowest missing ratio
```

### Fonksiyon

```python
prune_redundant_features(
    X,
    feature_metrics,
    clusters
) -> list[str]
```

Çıktı yalnızca seçilen feature isimleri olmalıdır.

---

# 12. Feature Ablation

## Amaç

Bir feature veya feature grubunun model performansına gerçek katkısını ölçmek.

### İşlem

```text
Full Model
   ↓
Base Metrics
   ↓
Remove Feature A
   ↓
Retrain
   ↓
Backtest
   ↓
Metric Difference
```

### Ölçümler

```text
Sharpe delta
Return delta
Max Drawdown delta
Accuracy delta
```

### Çıktı

```text
feature
base_sharpe
ablation_sharpe
sharpe_delta
return_delta
drawdown_delta
```

### Performans

Ablation paralel çalıştırılabilir ama ilk sürümde basit sequential implementation yeterlidir.

---

# 13. SHAP Stability

SHAP zaten kısmen varsa sıfırdan sistem oluşturma.

Mevcut SHAP çıktıları fold bazlı kaydedilmelidir.

### Amaç

Feature importance değerlerinin zaman içinde tutarlı olup olmadığını ölçmek.

### Hesap

Her fold için:

```text
mean(abs(SHAP))
```

Sonra:

```text
mean
std
coefficient of variation
rank stability
```

### Çıktı

```text
feature
mean_shap
std_shap
cv_shap
mean_rank
rank_std
```

---

# 14. Purged K-Fold

Bu modül öncelikli geliştirilmelidir.

## Problem

Finansal zaman serilerinde label horizon'ları çakışabilir.

Normal KFold bilgi sızıntısına neden olabilir.

## Çözüm

Validation aralığıyla zaman olarak çakışan training sample'ları kaldır.

### Sınıf

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

### Method

```python
split(
    X,
    label_start_times=None,
    label_end_times=None
)
```

### İlk sürüm

Eğer label timestamps yoksa index tabanlı purge kullanılabilir.

### Kural

```text
TRAIN
████████████

PURGE
            ░░

VALIDATION
              ████

EMBARGO
                  ░░
```

### Testler

- Train ve validation index'leri overlap etmemeli.
- Purge bölgesindeki kayıtlar train'e girmemeli.
- Embargo kayıtları train'e girmemeli.
- Chronological order korunmalı.

---

# 15. Embargo

Config:

```yaml
validation:
  embargo_pct: 0.01
```

Alternatif:

```yaml
validation:
  embargo_bars: 5
```

İlk sürümde yalnızca biri aktif olmalıdır.

Tercih:

```text
embargo_pct
```

---

# 16. Rolling Retraining

## Amaç

Modeli sabit uzunlukta kayan pencere üzerinde tekrar eğitmek.

Örnek:

```text
Train: 2020-2022
Test : 2023-Q1

Train: 2020-Q2 - 2023-Q1
Test : 2023-Q2
```

### Config

```yaml
retraining:
  mode: rolling
  train_window: 500
  test_window: 50
  step: 50
```

---

# 17. Anchored Retraining

Başlangıç sabit kalır.

```text
Train: 2020 → 2022
Test : Q1

Train: 2020 → Q1
Test : Q2

Train: 2020 → Q2
Test : Q3
```

### Config

```yaml
retraining:
  mode: anchored
  initial_train_window: 500
  test_window: 50
  step: 50
```

Rolling ve anchored aynı engine üzerinden çalışmalıdır.

---

# 18. Sprint 2 — Prediction ve Risk

# 19. Probability Calibration

İlk sürümde:

```text
Platt Scaling
Isotonic Regression
```

desteklenmelidir.

scikit-learn:

```python
CalibratedClassifierCV
```

### Metrikler

```text
Brier Score
Log Loss
Calibration Curve
```

### Çıktı

```text
raw_probability
calibrated_probability
```

### API

```text
POST /api/calibration/run
GET  /api/calibration/{experiment_id}
```

---

# 20. Quantile Regression

İlk sürümde üç quantile yeterlidir:

```text
P10
P50
P90
```

### Amaç

Tek tahmin yerine belirsizlik aralığı üretmek.

Örnek:

```text
Expected Return

P10  -0.8%
P50  +1.7%
P90  +4.4%
```

Model desteği mevcut kütüphaneye göre seçilmelidir.

Tercih sırası:

```text
1. LightGBM quantile objective
2. sklearn GradientBoostingRegressor(loss="quantile")
```

Yeni ağır dependency eklenmemelidir.

---

# 21. Slippage Stress Test

Base backtest üzerine senaryo matrisi kurulmalıdır.

Örnek:

```text
0 bps
1 bps
2 bps
5 bps
10 bps
20 bps
```

### Çıktı

```text
slippage_bps
total_return
sharpe
max_drawdown
trade_count
```

---

# 22. Latency Stress Test

Latency zaman bazlı değilse ilk sürümde bar gecikmesi olarak simüle edilebilir.

```text
0 bar
1 bar
2 bar
3 bar
5 bar
```

Signal:

```python
executed_signal = signal.shift(latency_bars)
```

### Çıktı

```text
latency_bars
total_return
sharpe
max_drawdown
```

---

# 23. Cost Stress Matrix

İki boyutlu test:

```text
              Slippage
              0   2   5   10
Commission 0
           2
           5
           10
```

Her hücrede:

```text
Sharpe
```

saklanmalıdır.

Ayrıca:

```text
Return
Max Drawdown
```

çıktıları da JSON artifact olarak tutulmalıdır.

---

# 24. Systematic Stress Testing

İlk sürümde senaryolar:

```text
Normal
High Transaction Cost
High Slippage
1-Bar Delay
3-Bar Delay
High Volatility Period
Low Liquidity Proxy
```

Her senaryoda aynı backtest engine kullanılmalıdır.

Backtest engine kopyalanmamalıdır.

---

# 25. Sprint 3 — Dimensionality ve Optimization

# 26. PCA

scikit-learn kullanılmalıdır.

### Pipeline

```text
Train Data
   ↓
StandardScaler
   ↓
PCA
```

Scaler ve PCA yalnızca training sample üzerinde fit edilmelidir.

Validation / test üzerinde yeniden fit edilmemelidir.

### Config

```yaml
pca:
  enabled: false
  variance_threshold: 0.95
```

---

# 27. PLS

`PLSRegression` kullanılabilir.

İlk sürüm:

```yaml
pls:
  enabled: false
  n_components: 5
```

Feature leakage'e dikkat edilmelidir.

---

# 28. Nonlinear Transformations

İlk sürümde:

```text
tanh
sigmoid
threshold
winsorization
```

yeterlidir.

Her transformation config üzerinden açılıp kapanmalıdır.

Örnek:

```yaml
transformations:
  tanh: false
  sigmoid: false
  winsorize:
    enabled: true
    lower: 0.01
    upper: 0.99
```

---

# 29. Nested Hyperparameter Optimization

Amaç:

Hyperparameter seçiminin validation sonucunu yapay şekilde yükseltmesini engellemek.

Yapı:

```text
Outer Fold
   ↓
Train
   ↓
Inner CV
   ↓
Hyperparameter Search
   ↓
Best Parameters
   ↓
Outer Validation
```

İlk sürümde Optuna varsa kullanılabilir.

Yoksa:

```text
RandomizedSearchCV
```

kullan.

Yeni dependency yalnızca gerçekten gerekiyorsa eklenmelidir.

---

# 30. Experiment Registry Genişletmesi

Her çalışma aşağıdaki metadata'yı saklamalıdır.

```json
{
  "experiment_id": "...",
  "dataset_hash": "...",
  "created_at": "...",
  "feature_set": [],
  "validation_method": "...",
  "model": "...",
  "hyperparameters": {},
  "metrics": {},
  "artifacts": {}
}
```

Yeni artifact tipleri:

```text
ic_report
ic_decay_report
feature_stability_report
feature_cluster_report
ablation_report
shap_stability_report
purged_cv_report
calibration_report
stress_test_report
```

---

# 31. API Tasarımı

Mevcut API standardı varsa ona uy.

Yeni endpoint önerileri:

```text
POST /api/features/ic
POST /api/features/ic-decay
POST /api/features/stability
POST /api/features/clustering
POST /api/features/ablation

POST /api/validation/purged-kfold
POST /api/validation/retraining

POST /api/calibration/run

POST /api/backtest/stress
POST /api/backtest/slippage-stress
POST /api/backtest/latency-stress

GET /api/experiments/{id}/artifacts
```

Her response:

```json
{
  "success": true,
  "experiment_id": "...",
  "data": {},
  "error": null
}
```

Hata halinde:

```json
{
  "success": false,
  "experiment_id": null,
  "data": null,
  "error": "..."
}
```

---

# 32. Dashboard Tasarımı

AlgoSense benzeri koyu renkli quant dashboard mantığı kullanılabilir.

Ana menü:

```text
Overview
Data
Features
Models
Validation
Optimization
Backtest
Stress Tests
Experiments
```

---

# 33. Feature Quality Ekranı

Gösterilecek tablo:

```text
Feature
IC
IC IR
IC Stability
Sign Consistency
SHAP Stability
Cluster
Selected
```

Filtre:

```text
Minimum IC
Minimum Stability
Selected Only
Cluster
```

Grafikler:

```text
IC Bar Chart
IC Decay Curve
Feature Correlation Heatmap
```

---

# 34. Validation Ekranı

Göster:

```text
Walk Forward
Purged K-Fold
Embargo
Rolling
Anchored
```

Fold zaman çizgisi:

```text
TRAIN    PURGE    VALIDATION    EMBARGO
██████   ░░       ████          ░
```

---

# 35. Optimization Ekranı

Genetic Algorithm bölümünde:

```text
Generation
Best Fitness
Sharpe
Return
Drawdown
Feature Count
```

Fitness breakdown:

```text
Sharpe Contribution
Feature Quality Contribution
Drawdown Penalty
Turnover Penalty
```

---

# 36. Stress Test Ekranı

Kartlar:

```text
Base Sharpe
Worst Sharpe
Base Return
Worst Return
Base Drawdown
Worst Drawdown
```

Heatmap:

```text
Commission × Slippage
```

Latency graph:

```text
Latency Bars → Sharpe
```

---

# 37. Backend Performans Kuralları

Düşük kaynak tüketimi önemlidir.

Kurallar:

- Gereksiz DataFrame copy yapma.
- Büyük dataset'i API response olarak döndürme.
- Grafik verilerini downsample et.
- Joblib kullanımı opsiyonel olsun.
- Cache yalnızca pahalı hesaplamalarda kullan.
- Büyük SHAP hesaplarını sample üzerinden yapabil.
- Default SHAP sample size: 5000.
- Büyük ablation çalışmasında feature sayısını config ile sınırla.
- Aynı dataset için hash değişmediyse tekrar preprocessing yapılmaması tercih edilir.

---

# 38. Güvenli Data Split Kuralı

En kritik kural:

```text
TRAIN
VALIDATION
TEST
FINAL HOLDOUT
```

birbirine karıştırılmamalıdır.

Aşağıdakiler yalnızca train üzerinde fit edilmelidir:

```text
Scaler
PCA
PLS
Feature selector
Feature clustering kararları
Calibration training
Hyperparameter optimization
```

Final holdout:

```text
SADECE EN SON
```

çalıştırılmalıdır.

Genetic Algorithm final holdout sonucunu fitness olarak kullanmamalıdır.

---

# 39. Genetic Algorithm Entegrasyonu

Mevcut GA bozulmamalıdır.

Yeni fitness adapter oluştur.

Örnek:

```python
class QuantFitnessCalculator:

    def calculate(
        self,
        sharpe,
        feature_quality,
        max_drawdown,
        turnover
    ):
        ...
```

Config:

```yaml
genetic_algorithm:
  fitness:
    sharpe_weight: 0.50
    feature_quality_weight: 0.20
    drawdown_weight: 0.20
    turnover_weight: 0.10
```

Her metric normalize edilmelidir.

İlk sürümde basit min-max veya bounded normalization kullanılabilir.

---

# 40. Minimum Test Listesi

Her modül için test yazılmalıdır.

## IC

```text
test_positive_ic
test_negative_ic
test_nan_handling
test_constant_feature
```

## Purged K-Fold

```text
test_no_overlap
test_purge_applied
test_embargo_applied
test_time_order
```

## Clustering

```text
test_highly_correlated_features_same_cluster
test_independent_features_separate
```

## Ablation

```text
test_feature_removed
test_metrics_generated
```

## Calibration

```text
test_probability_range
test_brier_score
```

## Stress

```text
test_higher_cost_reduces_or_preserves_return
test_latency_shift
test_scenario_output
```

---

# 41. Logging

Her uzun işlem için log oluştur:

```text
experiment_id
module
start_time
end_time
duration
status
error
```

Örnek:

```text
[INFO] experiment=EXP123 module=ic status=started
[INFO] experiment=EXP123 module=ic duration=2.31s status=completed
```

---

# 42. Error Handling

Kullanıcıya Python stack trace gönderme.

API:

```text
400 → yanlış input
404 → experiment bulunamadı
422 → validation problemi
500 → beklenmeyen hata
```

Stack trace yalnızca server logunda olmalıdır.

---

# 43. Configuration

Yeni feature'ların tamamı config üzerinden açılıp kapatılmalıdır.

Örnek:

```yaml
feature_analysis:
  ic:
    enabled: true

  ic_decay:
    enabled: true
    horizons: [1, 2, 3, 5, 10, 20]

  clustering:
    enabled: true
    correlation_threshold: 0.85

validation:
  purged_kfold:
    enabled: true
    n_splits: 5
    purge_window: 5
    embargo_pct: 0.01

retraining:
  mode: rolling
  train_window: 500
  test_window: 50

stress_test:
  slippage_bps: [0, 1, 2, 5, 10, 20]
  latency_bars: [0, 1, 2, 3, 5]
```

---

# 44. Geliştirme Sırası

Düşük güçlü AI bu sırayı değiştirmemelidir.

## Faz 1

```text
1. IC
2. IC Decay
3. Sign Consistency
4. Feature Quality Report
5. Feature Clustering
6. Redundancy Pruning
```

## Faz 2

```text
7. Purged K-Fold
8. Embargo
9. Rolling Retraining
10. Anchored Retraining
```

## Faz 3

```text
11. Feature Ablation
12. SHAP Stability
13. GA Fitness Adapter
```

## Faz 4

```text
14. Probability Calibration
15. Quantile Regression
```

## Faz 5

```text
16. Slippage Stress
17. Latency Stress
18. Systematic Stress Testing
```

## Faz 6

```text
19. PCA
20. PLS
21. Nonlinear Transformations
22. Nested HPO
```

---

# 45. İlk Sprint Definition of Done

İlk sprint şu özellikler tamamlanmadan bitmiş sayılmamalıdır:

```text
✓ IC hesaplanıyor
✓ IC Decay hesaplanıyor
✓ Sign Consistency hesaplanıyor
✓ Feature Quality Report oluşuyor
✓ Feature Clustering çalışıyor
✓ Redundant feature listesi oluşuyor
✓ Purged K-Fold çalışıyor
✓ Embargo uygulanıyor
✓ Unit testler geçiyor
✓ Experiment Registry sonuçları kaydediyor
✓ API endpoint'leri çalışıyor
```

---

# 46. İkinci Sprint Definition of Done

```text
✓ Rolling retraining
✓ Anchored retraining
✓ Feature ablation
✓ SHAP stability
✓ GA multi-objective fitness
✓ Probability calibration
✓ Quantile prediction
✓ Stress matrix
✓ Slippage test
✓ Latency test
```

---

# 47. Yapılmaması Gerekenler

İlk geliştirme aşamasında aşağıdakileri yapma:

```text
FX Option IV Surface
Forward Points
FX Swaps
OIS Curve
Cross Currency Basis
CFTC Positioning
Dealer Positioning
Order Flow
Tick Data
Full Order Book
Complex Microstructure Models
Online Learning
Distributional Deep Learning
```

Bu özellikler yeni veri kaynağı ve daha kapsamlı altyapı gerektirir.

---

# 48. AI Agent İçin Çalışma Talimatı

Aşağıdaki talimat doğrudan coding agent'a verilebilir:

```text
Bu repository üzerinde mevcut çalışan sistemi bozmadan geliştirme yap.

Önce proje yapısını incele.

Bu dokümandaki "Geliştirme Sırası" bölümünü takip et.

Aynı anda yalnızca bir feature geliştir.

Her feature için:

1. Mevcut ilgili kodu incele.
2. Minimum değişiklik planını oluştur.
3. Backend implementation yap.
4. Pydantic/API contract gerekiyorsa ekle.
5. Unit test yaz.
6. Testleri çalıştır.
7. Mevcut testlerin tamamının geçtiğini doğrula.
8. Feature tamamlandıktan sonra kısa CHANGELOG kaydı oluştur.
9. Sonraki feature'a geç.

Çalışan fonksiyonları yeniden yazma.

Yeni dependency eklemeden önce mevcut dependency'leri kontrol et.

Final holdout verisini feature selection, model selection, hyperparameter optimization veya genetic algorithm fitness içinde kullanma.

Tüm scaler, PCA, PLS, clustering ve feature selection işlemlerini yalnızca training datasında fit et.

Time-series leakage oluşturma.

Purged K-Fold ve embargo implementasyonu tamamlanmadan gelişmiş model optimization işlerine geçme.

Bir görev başarısız olursa sonraki göreve geçme; önce hatayı düzelt.
```

---

# 49. Beklenen Nihai Pipeline

```text
DATA
 │
 ▼
Point-in-Time Validation
 │
 ▼
Feature Engineering
 │
 ▼
Feature Quality
 ├── IC
 ├── IC Decay
 ├── Sign Consistency
 ├── SHAP Stability
 └── Clustering
 │
 ▼
Redundancy Pruning
 │
 ▼
Genetic Algorithm
 │
 ▼
Model Training
 │
 ├── Ridge
 ├── Random Forest
 ├── HGB
 ├── XGBoost
 └── LightGBM
 │
 ▼
Purged Validation
 ├── Purged K-Fold
 ├── Embargo
 └── Walk Forward
 │
 ▼
Hyperparameter Optimization
 │
 ▼
Rolling / Anchored Retraining
 │
 ▼
Calibration / Quantile Prediction
 │
 ▼
Backtest
 │
 ▼
Stress Testing
 ├── Commission
 ├── Slippage
 ├── Latency
 └── Market Stress
 │
 ▼
FINAL HOLDOUT
 │
 ▼
Experiment Registry
```

---

# 50. Ana Başarı Metrikleri

Sistem yalnızca prediction accuracy ile değerlendirilmemelidir.

Ana sonuçlar:

```text
Sharpe Ratio
Total Return
Annualized Return
Max Drawdown
Calmar Ratio
Sortino Ratio
Turnover
Trade Count
Hit Ratio
Profit Factor
```

Araştırma kalitesi:

```text
IC
IC IR
IC Decay
Sign Consistency
SHAP Stability
Feature Redundancy
Fold Stability
```

Risk:

```text
Worst Stress Sharpe
Worst Stress Drawdown
Cost Sensitivity
Latency Sensitivity
```

---

# 51. Nihai Hedef

Bu geliştirmelerin sonunda uygulama yalnızca:

```text
Model Train
→ Backtest
```

yapan bir sistem olmamalıdır.

Hedef:

```text
Data
→ Feature Research
→ Feature Stability
→ Leakage-Safe Validation
→ Genetic Optimization
→ Model Selection
→ Calibration
→ Walk Forward
→ Stress Testing
→ Final Holdout
→ Experiment Registry
```

şeklinde uçtan uca, tekrar üretilebilir bir Quant Research & Strategy Validation Platform oluşturmaktır.
