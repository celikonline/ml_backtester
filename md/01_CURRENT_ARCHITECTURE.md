# CURRENT ARCHITECTURE

> Güncelleme: 2026-09-06 — gerçek repository taraması yapıldı (T001-T008).
> Entry: `backend/app.py` (FastAPI) + `api/index.py` (Vercel). Test: 115 passed / 3 failed (bilinen ledger hatası).

---

## 1. Beklenen Ana Katmanlar

```text
Data
Features
Models
Validation
Optimization
Backtest
Experiments
API
UI
```

---

## 2. Gerçek Modül Envanteri (2026-09-06 taraması)

### Data Layer — MEVCUT
- `backend/engine.py:read_prices()`, `demo_prices()`, `describe()`, `audit_calendar()` — CSV yükleme, OHLC doğrulama, UTC normalize, takvim audit
- `backend/app.py:dataset()`, `upload_dataset()` — `data/dataset-*.csv|json` persistence
- `backend/platform/families.py:family_for_column()` — makro/FX/faiz/cross-asset aileleri
- `backend/platform/service.py:snapshot()`, `load_snapshot()` — SHA-256 + point-in-time (`__available_at`) kontrolü

### Feature Layer — MEVCUT
- `backend/engine.py:features()` — return_lag, momentum/sma/volatility, rsi/macd/range/body, hour_sin/cos
- `backend/platform/research.py:feature_frame()`, `registry()` — lag__/delta__/return__ external + statistical ekler
- `backend/quant/ic.py` — `calculate_ic`, `calculate_feature_ic`, `calculate_ic_decay`, `sign_consistency_report`, `feature_quality_score/report` (Spearman, NaN-güvenli)
- `backend/quant/clustering.py` — `cluster_features` (Spearman + hierarchical, distance=1-|corr|), `prune_redundant_features`
- `backend/quant/dimensionality.py` — `apply_pca`, `apply_pls`, `apply_transformations` (train-only fit)
- `backend/quant/ablation.py` — `ablation_report`, `shap_stability_report`
- Eksik: orthogonalization / residualization / CPCV / conformal / online learning (faz dışı)

### Regime Layer — MEVCUT
- `backend/engine.py:causal_probabilities()`, `_run_experiment()` — `GaussianHMM` (hmmlearn), forward-filtering only, scaler train-only

### Model Layer — MEVCUT
- `backend/platform/models.py:MODEL_REGISTRY`, `ModelAdapter` — ridge, random_forest, hist_gradient_boosting, xgboost, lightgbm
- `backend/engine.py:_run_experiment()` — 3 uzman (Ridge / RF / HGB) + HMM ağırlıklı ensemble + eşik seçimi (validation)
- `backend/quant/calibration.py` — `calibrate_probabilities` (Platt/isotonic), `calibration_metrics` (Brier), `QuantilePredictor` (P10/P50/P90)
- Kısmi: stacking/blending (ensemble var, tam stacking yok)

### Validation Layer — MEVCUT
- `backend/engine.py:_run_experiment()` — train/validation/test split + 2 bar purge (walk-forward benzeri)
- `backend/quant/validation.py` — `PurgedKFold` (purge_window + embargo_pct/bars), `rolling_splits`, `anchored_splits`, `nested_search`
- `backend/platform/research.py` — `TimeSeriesSplit` kullanımı

### Optimization Layer — MEVCUT
- `backend/platform/research.py:298-333` — GA: population/selection/crossover/mutation (`ExperimentSpec.optimization`: genetic, population 4-32, mutation/crossover_rate)
- `backend/platform/schema.py:ExperimentSpec` — GA config + policy (`POLICY`)
- `backend/quant/fitness.py:QuantFitnessCalculator` — multi-objective adapter (sharpe/feature_quality/drawdown/turnover), config `backend/quant/config.py:genetic_algorithm.fitness`
- `backend/quant/validation.py:nested_search` — nested HPO (kaba grid)

### Backtest Layer — MEVCUT
- `backend/engine.py:backtest()`, `fx_backtest()`, `metrics()` — cost-aware, spread/commission/slippage, rollover, margin guard, seal'li final holdout
- `backend/quant/stress.py` — `slippage_stress`, `latency_stress` (shift), `cost_stress_matrix`, `systematic_stress` (7 senaryo) — motor kopyalanmaz, `fx_backtest` üzerinden
- `backend/platform/service.py:_open_seal_for_final_test()` — final holdout izolasyonu (seal/epoch)

### Explainability — MEVCUT (kısmi)
- `backend/quant/ablation.py`, `backend/platform/research.py` (spearman, mutual_info, permutation izleri)

### Experiment Management — MEVCUT
- `backend/platform/service.py:ExperimentService` — registry, snapshot, seal, budget, ledger, workspace
- `backend/platform/db.py`, `models.py`, `schema.py` — SQLAlchemy + Alembic (`backend/migrations/`)
- `backend/quant/config.py:QUANT_ARTIFACT_TYPES` — 9 artifact tipi (ic_report, stress_test_report vb.)
- Workspace izolasyonu: `backend/platform/scope.py:workspace_scope`, `service.py` workspace CRUD

---

## 3. Repository Analiz Sonucu (T001-T008 tamamlandı)

```text
[x] main backend entry point -> backend/app.py (FastAPI app), api/index.py (Vercel re-export)
[x] API framework -> FastAPI; backend/app.py + backend/platform/api.py + backend/platform/quant_api.py
[x] model training service -> backend/engine.py:_run_experiment + backend/platform/models.py:ModelAdapter + backend/platform/research.py
[x] feature engineering service -> backend/engine.py:features + backend/platform/research.py:feature_frame + backend/quant/ic.py|clustering.py|dimensionality.py
[x] genetic algorithm implementation -> backend/platform/research.py:298-333 + backend/platform/schema.py:ExperimentSpec.optimization + backend/quant/fitness.py
[x] backtest engine -> backend/engine.py:backtest|fx_backtest|metrics (tek motor, kopyalanmaz)
[x] validation implementation -> backend/quant/validation.py:PurgedKFold|rolling_splits|anchored_splits|nested_search + engine split
[x] experiment registry -> backend/platform/service.py:ExperimentService + backend/platform/db.py
[x] persistence layer -> SQLAlchemy + Alembic (backend/migrations/, alembic.ini), data/*.csv|json, test.db
[x] configuration files -> requirements.txt, backend/quant/config.py:DEFAULT_QUANT_CONFIG, backend/platform/schema.py:POLICY, opencode.json, vercel.json
[x] test folders -> tests/ (test_quant_*.py 7 dosya + test_engine.py, test_platform.py, test_api.py vb.)
[x] frontend framework -> React+Vite+TS (frontend/src/: App.tsx, ResearchPlatform.tsx, QuantLab.tsx, QuantLabRisk.tsx, platform-api.ts)
```

---

## 4. Analiz Sonrası Bu Dosyaya Eklenecekler

Agent aşağıdaki tabloyu gerçek dosya yollarıyla doldurmalıdır:

| Alan | Dosya / Klasör | Sorumluluk | Durum |
|---|---|---|---|
| Data ingestion | `backend/engine.py:read_prices`, `backend/app.py:dataset`, `backend/platform/service.py:snapshot` | CSV yükleme, OHLC doğrulama, snapshot+SHA256, PIT | Mevcut |
| Feature engineering | `backend/engine.py:features`, `backend/platform/research.py:feature_frame`, `backend/quant/ic.py`, `clustering.py`, `dimensionality.py` | Lag/delta/return, IC/decay/quality, clustering/pruning | Mevcut |
| Regime detection | `backend/engine.py:causal_probabilities`, `_run_experiment` | Gaussian HMM, causal çıkarım | Mevcut |
| Model training | `backend/platform/models.py:ModelAdapter`, `backend/engine.py:_run_experiment`, `backend/quant/calibration.py` | Ridge/RF/HGB/XGB/LGBM, ensemble, calibration/quantile | Mevcut |
| Validation | `backend/quant/validation.py:PurgedKFold`, `rolling_splits`, `anchored_splits`, `nested_search` | Purge+embargo, rolling/anchored, nested HPO | Mevcut |
| Genetic Algorithm | `backend/platform/research.py:298-333`, `backend/platform/schema.py`, `backend/quant/fitness.py:QuantFitnessCalculator` | Population/select/crossover/mutate + multi-objective fitness | Mevcut |
| Backtest | `backend/engine.py:backtest`, `fx_backtest`, `metrics` | Cost/slippage/rollover/margin, tek motor | Mevcut |
| Stress test | `backend/quant/stress.py` | Slippage/latency/cost-matrix/systematic (motoru reuse eder) | Mevcut |
| Experiment registry | `backend/platform/service.py:ExperimentService`, `backend/platform/db.py`, `backend/migrations/` | Registry, seal/holdout, budget/ledger, workspace | Mevcut |
| API | `backend/app.py`, `backend/platform/api.py`, `backend/platform/quant_api.py`, `api/index.py` | REST + `{success,experiment_id,data,error}` quant zarfı | Mevcut |
| UI | `frontend/src/QuantLab.tsx`, `QuantLabRisk.tsx`, `ResearchPlatform.tsx`, `platform-api.ts` | Feature Quality, Validation, GA fitness, Stress ekranları | Mevcut (kısmi) |
| Config | `backend/quant/config.py`, `requirements.txt`, `alembic.ini` | Feature/validation/GA/stress ağırlıkları | Mevcut |
| Tests | `tests/test_quant_*.py` (7 dosya), `test_engine.py`, `test_platform.py` | IC/clustering/validation/stress/API + platform | 115 passed / 3 failed |

---

## 5. Değişiklik Politikası

Repository keşfinden sonra:

- Mevcut dosya yapısı korunmalı.
- Yeni klasör yalnızca gerçekten gerekliyse oluşturulmalı.
- Aynı sorumluluğu yapan ikinci bir service yazılmamalı.
- Backtest engine kopyalanmamalı.
- Validation logic tek noktadan yönetilmeli.
- Experiment ID tüm pipeline boyunca taşınmalı.

---

## 6. İlk Baseline (2026-09-06, T009-T010)

```text
dataset: demo_prices (sentetik EUR/USD 4h, engine.py)
feature_count: 25 (engine.features) / 34 (research.feature_frame + statistical)
model_name: HMM Ensemble (Ridge + RF + HGB, validation'da ağırlık+eşik seçimi)
validation_method: train_ratio split + 2 bar purge + PurgedKFold/rolling/anchored hazır (quant/validation.py)
test_count: 118
test_pass_count: 115
test_fail_count: 3 (bilinen: test_platform.py ledger dict-vs-list — seal/budget/migration)
quant_tests: 20 passed (ic/clustering/validation/stress) + diğer quant dosyaları dahil toplam 115 içinde
api_contract: mevcut endpoint'ler korunuyor; quant router /api prefix + envelope'lı
```

Bu baseline, sonraki değişikliklerin regresyon yaratıp yaratmadığını anlamak için kullanılacaktır.
Not: `service.ledger()` paginated dict dönüyor (`{page,items...}`), 3 failing test list bekliyor. Fix test tarafında `["items"]` ile yapılmalı (T009).
