# CHANGELOG

## 2026-09-06 — Sprint 2 GA fitness entegrasyonu (T301-T311)

- `backend/quant/fitness.py`: `DEFAULT_FEATURE_COUNT_PENALTY` + `count_penalty_value()` eklendi (default kapalı); `breakdown`/`calculate` geriye uyumlu `n_features` aldı.
- `backend/quant/config.py`: `genetic_algorithm.feature_count_penalty` defaults eklendi.
- `backend/platform/schema.py`: `OptimizationSpec.use_quant_fitness=False` + `fitness_weights` opt-in eklendi (eski ranking default korunur).
- `backend/platform/research.py`: `optimize()` dev-only mean-abs-IC ile `feature_quality` hesaplar, her adaya `fitness_breakdown` (§6) + `quant_fitness` yazar; `reproducibility` (seed/population/generations/rates/weights/universe) döner.
- `backend/platform/quant_api.py`: `POST /optimization/fitness` artık `n_features` + `count_penalty` destekler.
- `tests/test_quant_advanced.py`: 10 yeni test (sharpe+/drawdown-/turnover-/fq etkisi, weight config, penalty, holdout yok, same-seed, breakdown/repro, eski davranış).
- Sonuç: 48 passed (quant suite); platform/engine 29 passed + 3 bilinen ledger hatası (değişmedi).

## 2026-09-06 — Sprint 1 kapanış (T111-T112 gap fix)

- `backend/platform/quant_api.py`: `POST /api/features/prune` eklendi (`PruneRequest`, stateless, mevcut `prune_redundant_features` reuse).
- `backend/quant/config.py`: `QUANT_ARTIFACT_TYPES` içine `selected_feature_list` eklendi (sprint §7 DoD).
- `tests/test_quant_ic.py`: `test_ic_decay_no_future_leak` eklendi (tail-drop ile gelecek sızıntısı yok).
- `tests/test_quant_api.py`: `test_api_prune` + `test_api_quant_config_has_selected_list` eklendi.
- Sonuç: 34 passed (ic/clustering/api/validation/stress/calibration), regresyon yok.

## 2026-09-06 — T001-T008/T011 discovery + 01_CURRENT_ARCHITECTURE güncellemesi

- `md/01_CURRENT_ARCHITECTURE.md`: TBD tablosu gerçek yollarla dolduruldu (app.py, engine.py, quant/*, platform/service.py, research.py, quant_api.py, QuantLab.tsx).
- `md/TASKS.md`: T001-T008, T010-T011 işaretlendi; T009 açık (115 passed / 3 failed, ledger `dict` vs `list`).
- Baseline §6'ya işlendi: feature_count 25/34, HMM Ensemble, test 115/118.
- Kod değişikliği yok, API sözleşmesi korunuyor.

## 2026-09-06 — Dusuk_Guclu AI Quant plani (Faz 1–6, backend)

Mevcut pipeline ve API sozlesmeleri bozulmadan eklendi:

- `backend/quant/ic.py`: Spearman IC, IC decay (default [1,2,3,5,10,20]),
  sign consistency, feature quality score/raporu.
- `backend/quant/clustering.py`: Spearman + hierarchical clustering,
  redundancy pruning (abs(IC) > sign consistency > missing ratio).
- `backend/quant/validation.py`: PurgedKFold (purge + embargo), rolling /
  anchored retraining split ureticileri, gridsiz nested hiperparametre aramasi.
- `backend/quant/ablation.py`: sequential feature ablation raporu,
  fold bazli SHAP stabilite raporu (SHAP bagimliligi yok).
- `backend/quant/fitness.py`: GA `QuantFitnessCalculator`
  (sharpe / feature quality / drawdown / turnover agirlikli).
- `backend/quant/calibration.py`: out-of-fold Platt (sigmoid) + isotonic
  kalibrasyon, Brier/log-loss/egri metrikleri, P10/P50/P90 quantile regresyon
  (LightGBM quantile, yoksa sklearn GBR).
- `backend/quant/stress.py`: slippage / latency / commission×slippage matriz /
  7 senaryolu sistematik stres — hepsi mevcut `fx_backtest` motoru uzerinden.
- `backend/quant/dimensionality.py`: train-only fit PCA / PLS, tanh / sigmoid /
  threshold / winsorize donusumleri.
- `backend/quant/config.py`: tum ozellikler icin ac/kapa varsayilan konfigurasyonu
  ve 9 yeni registry artifact tipi.
- `backend/platform/quant_api.py`: spec §31 endpointleri
  (`/api/features/*`, `/api/validation/*`, `/api/calibration/run`,
  `/api/backtest/*`, `/api/optimization/fitness`, `/api/quant/config`);
  `{success, experiment_id, data, error}` zarfi. `backend/app.py`'a monte edildi.
- Testler: `tests/test_quant_*.py` (7 dosya, 33 test) — IC, purge/embargo,
  clustering, ablation, kalibrasyon, stres, API zarfi.

Duzeltme: `calibrate_probabilities` icindeki sklearn `clone` hatasi
(`CalibratedClassifierCV` + ozel model) giderildi; IsotonicRegression /
LogisticRegression ile capraz-fit kalibrasyona gecildi.

Bilinen, degisiklik oncesi de var olan hatalar (dokunulmadi):
`tests/test_platform.py` icindeki 3 `service.ledger()` tuketim hatasi
(`test_seal_invalidate_rotate_and_epoch`, `test_budget_isolated_per_workspace`,
`test_budget_migration_reassigns_legacy_global`).

Kapsam disi (plan §47 + dashboard tasarimi §32–36): yeni veri kaynaklari
(IV surface, OIS, order flow vb.) ve frontend ekranlari eklenmedi.

## 2026-09-06 — Quant Lab UI (plan §31–36)

- `frontend/src/platform-api.ts`: `requestQuant()` (`/api` prefix) + quant tipleri
  (IC, quality, fold, stress, calibration, fitness, quantile).
- `frontend/src/quant-demo.ts`: sekmeler icin sinirli, seed'li demo veri ureticileri.
- `frontend/src/QuantLab.tsx`: Feature Quality (§33: IC bar, filtreler, quality/
  cluster/selected tablosu, IC decay egrisi, korelasyon heatmap) + Validation
  (§34: purged/rolling/anchored, TRAIN/PURGE/VALIDATION/EMBARGO zaman cizgisi,
  fold tablosu).
- `frontend/src/QuantLabRisk.tsx`: GA fitness breakdown (§35), kalibrasyon egrisi
  + Brier kartlari, P10/P50/P90 quantile tablo+band, Stress (§36: baz/en-kotu
  kartlari, commission×slippage heatmap, latency→Sharpe, 7 senaryo; tamamlanmis
  deney egrisi veya demo verisiyle).
- `ResearchPlatform` toolbar'a "Quant Lab" sekmesi eklendi; `App.tsx` roadmap
  durumlari guncellendi. `npm run build` (tsc + vite) temiz.
- Backend ek: `POST /api/quantile/predict` (+ test).
