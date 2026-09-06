# TASKS

> Bu dosya çalışma kuyruğudur.
> AI agent yalnızca ilk tamamlanmamış görevi ele almalıdır.

---

# PHASE 0 — Repository Discovery

- [x] T001 Repository klasör yapısını çıkar
- [x] T002 Backend entry point'i bul
- [x] T003 Feature engineering modülünü bul
- [x] T004 Model training modülünü bul
- [x] T005 Walk-forward / validation modülünü bul
- [x] T006 Genetic Algorithm kodunu bul
- [x] T007 Backtest engine'i bul
- [x] T008 Experiment registry'yi bul
- [ ] T009 Mevcut testleri çalıştır (115 passed / 3 failed — ledger dict-vs-list, bilinen)
- [x] T010 Baseline metriklerini kaydet (01_CURRENT_ARCHITECTURE.md §6'ya işlendi)
- [x] T011 `01_CURRENT_ARCHITECTURE.md` dosyasını gerçek yollarla güncelle

---

# PHASE 1 — Feature Stability

- [x] T101 `calculate_ic` implement et (backend/quant/ic.py — mevcut, doğrulandı)
- [x] T102 IC unit testlerini yaz (test_quant_ic.py — positive/negative/nan/constant mevcut)
- [x] T103 Multi-feature IC report oluştur (calculate_feature_ic — mevcut)
- [x] T104 IC Decay implement et (calculate_ic_decay — mevcut)
- [x] T105 IC Decay testlerini yaz (default_horizons mevcut + no_future_leak eklendi)
- [x] T106 Sign Consistency implement et (calculate_sign_consistency + report — mevcut)
- [x] T107 Feature Quality Score implement et (feature_quality_score/report + config weights — mevcut)
- [x] T108 Feature Clustering implement et (cluster_features — mevcut)
- [x] T109 Clustering testlerini yaz (test_quant_clustering.py — mevcut)
- [x] T110 Redundancy Pruning implement et (prune_redundant_features — mevcut)
- [x] T111 Feature artifact kayıtlarını ekle (QUANT_ARTIFACT_TYPES + selected_feature_list eklendi)
- [x] T112 Feature API endpoint'lerini ekle (POST /api/features/prune eklendi; ic, ic-decay, stability, clustering mevcut)
- [x] T113 Tüm testleri çalıştır (34 passed — quant ic/clustering/api/validation/stress/calibration)

---

# PHASE 2 — Leakage-Safe Validation

- [ ] T201 PurgedKFold sınıfını implement et
- [ ] T202 Purge testlerini yaz
- [ ] T203 Embargo implement et
- [ ] T204 Embargo testlerini yaz
- [ ] T205 Walk-forward ile entegrasyon yap
- [ ] T206 Rolling retraining ekle
- [ ] T207 Anchored retraining ekle
- [ ] T208 Validation artifact oluştur
- [ ] T209 Final holdout izolasyon testi yaz
- [ ] T210 Tüm testleri çalıştır

---

# PHASE 3 — Genetic Optimization

- [x] T301 Mevcut GA fitness akışını analiz et (research.py:281 eski `m[objective]`, optimize() dev-only)
- [x] T302 QuantFitnessCalculator ekle (backend/quant/fitness.py — mevcut, penalty ile genişletildi)
- [x] T303 Sharpe normalization ekle (-3..+3 -> 0..1, mevcut, testli)
- [x] T304 Feature quality entegrasyonu ekle (dev mean abs IC, opt-in ranking + her adayda fq kaydı)
- [x] T305 Drawdown penalty ekle (mevcut, testli)
- [x] T306 Turnover penalty ekle (mevcut, testli)
- [x] T307 Fitness weight config ekle (config.py + OptimizationSpec.fitness_weights + use_quant_fitness opt-in)
- [x] T308 Fitness breakdown artifact ekle (candidate.fitness_breakdown §6 şemalı + reproducibility)
- [x] T309 Final holdout kullanılmadığını test et (optimize imzası + freeze-before-test sırası)
- [x] T310 Reproducibility seed testini yaz (same_seed + reproducibility dict)
- [x] T311 Tüm testleri çalıştır (48 passed — quant suite; platformda yeni regresyon yok)

---

# PHASE 4 — Explainability

- [ ] T401 Feature Ablation implement et
- [ ] T402 Ablation metric delta'larını ekle
- [ ] T403 SHAP fold artifact'larını bul / ekle
- [ ] T404 SHAP Stability hesapla
- [ ] T405 Rank Stability hesapla
- [ ] T406 Explainability artifact'larını registry'ye bağla
- [ ] T407 Testleri çalıştır

---

# PHASE 5 — Prediction Quality

- [ ] T501 Probability Calibration ekle
- [ ] T502 Platt Scaling ekle
- [ ] T503 Isotonic Regression ekle
- [ ] T504 Brier Score ekle
- [ ] T505 Calibration Curve datası üret
- [ ] T506 Quantile Regression P10/P50/P90 ekle
- [ ] T507 Prediction artifact oluştur
- [ ] T508 Testleri çalıştır

---

# PHASE 6 — Stress Testing

- [ ] T601 Slippage stress implement et
- [ ] T602 Latency stress implement et
- [ ] T603 Commission stress implement et
- [ ] T604 Cost matrix oluştur
- [ ] T605 Worst-case summary oluştur
- [ ] T606 Stress artifact'larını kaydet
- [ ] T607 Stress API endpoint'lerini ekle
- [ ] T608 Testleri çalıştır

---

# PHASE 7 — UI

- [ ] T701 Main navigation
- [ ] T702 Overview KPI cards
- [ ] T703 Feature Quality table
- [ ] T704 IC chart
- [ ] T705 IC Decay chart
- [ ] T706 Validation timeline
- [ ] T707 GA generation chart
- [ ] T708 Backtest KPI cards
- [ ] T709 Stress heatmap
- [ ] T710 Experiment list
- [ ] T711 Responsive desktop kontrolü
- [ ] T712 API error state'leri
- [ ] T713 Loading state'leri

---

# TASK ÇALIŞMA KURALI

Her task için:

```text
1. Dosyaları incele
2. Minimum değişikliği planla
3. Implement et
4. Unit test yaz
5. Testleri çalıştır
6. CHANGELOG ekle
7. Task checkbox'ını işaretle
8. Sonraki task'a geç
```

Bir task başarısızsa sonraki task'a geçme.
