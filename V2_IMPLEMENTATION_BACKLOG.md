# RegimeLab V2 Uygulama Backlog'u

Bu backlog, `REGIMELAB_ASTRA_IMPLEMENTATION_SPEC_V2_QUANTCONNECT_DIFFERENTIATION.md` ile mevcut kod tabanının karşılaştırılmasından üretilmiştir. Sıralama, mevcut çalışan deney akışını koruyarak ürün farkını en kısa yoldan artıracak şekildedir.

## Mevcut temel

- Immutable experiment taslağı, snapshot hash'i, kayıt defteri, async tek worker, SSE ve audit log var.
- Holdout/walk-forward, aday dondurma ve deney başına tek final test uygulanıyor.
- GA; özellik, model, sınırlı hiperparametre ve sinyal eşiği arıyor.
- Pareto görünümü, feature survival, klonlama, karşılaştırma, REST ve MCP adapter'ı var.
- Eksik olan ana katmanlar: global sealed-test yönetişimi, research budget, gerçekçi FX backtest, first-class search space/candidate kayıtları ve lineage grafiği.

## P0 — Research governance ve sealed test

### 1. Global sealed-test servisi

- [x] `test_seals` tablosu ve migration ekle.
- [x] Sealed test için `test_dataset_id`, `seal_id`, `access_count`, `first_opened_at`, `invalidated_at`, `invalidation_reason` alanlarını tanımla.
- [x] Test açma/okuma olaylarını `test_access_events` tablosunda kaydet.
- [x] Optimizer'ın test verisine erişemediğini servis seviyesinde enforce et.
- [x] Aynı sealed dönemde test görüldükten sonra oluşturulan child deneyleri `POST_TEST_ITERATION_FROM` ilişkisiyle işaretle.
- [x] Yeni final doğrulama için yeni temporal holdout / yeni seal epoch oluşturma akışı ekle (`POST .../seal/invalidate`, `POST .../seal/rotate`, `GET .../seal/history`; epoch'lar `uq_test_seals_dataset_epoch` ile tutulur, eski epoch'lar denetlenebilir kalır).

Kabul ölçütü: Bir aday test edilmeden önce seal kapalı kalır; test erişimi ve tekrar denemeleri kalıcı olarak izlenir; agent veya REST çağrısı bu politikayı atlayamaz.

### 2. Research budget ve multiple-testing guard

- [x] `research_budgets` ve `research_trial_events` tablolarını ekle.
- [x] Hipotez, deney, aday, optimizasyon denemesi, backtest ve sealed test erişim sayaçlarını tut (hipotez/optimizasyon denemesi için ayrı sayaç yok; `seal_invalidated`/`seal_rotated` olayları deftere yazılır).
- [x] Deney oluşturma ve çalıştırma öncesi budget/risk tahmini üret.
- [x] Politika limitini aşan denemeleri `policy_rejected` ile reddet.
- [x] Research Overfitting Risk kartı ve ledger ekranını ekle (Bütçe sekmesi: limit çubukları + baskı skoru + `GET /research/ledger` tablosu).

Kabul ölçütü: Her deney, aday ve test erişimi araştırma defterine yazılır; UI ve API güncel risk/bütçe durumunu gösterir.

## P0 — FX Backtest Reality Layer

### 3. Backtest reality contract ve engine

- [x] `BacktestRealityConfig` şemasını ekle. (fixed/ohlc_range spread, komisyon, slippage, flat+long/short rollover, Wed triple; fill/latency/stop modelleri yok)
- [x] Sabit/değişken bid-ask spread, komisyon ve slippage modellerini uygula. (validasyon ve final test aynı `merged_reality` yolunu kullanır; `tests/test_backtest_golden.py`)
- [x] FX swap/rollover/financing maliyetlerini uygula. (long/short ayrımı + opsiyonel Çarşamba triple; tatil-gününe duyarlı tahakkuk yok)
- [x] Timezone, DST, hafta sonu ve tatil takvimini doğrula. (`audit_calendar`: weekend/midweek/holiday gap ayrımı + kaynak timezone tespiti snapshot'a yazılır; FX tatil seti: 1 Oca, Good Friday, Easter Monday, 25/26 Ara + gözlenen gün; reject yok)
- [x] Signal timestamp ile executable price ayrımını engine seviyesinde koru. (`fx_backtest` imzası + curve `timestamp`/`signal_timestamp` ayrımı; golden testte sıralama doğrulanır)
- [x] Pozisyon büyüklüğü, kaldıraç ve margin için MVP sınırlarını tanımla. (`exposure = max_leverage * max_position_fraction`, tek-bar -%100 floor + likidasyon sonrası flat; `fx_backtest` + golden testler)

### 4. Backtest regression suite

- [x] Golden dataset/case altyapısı oluştur. (`tests/test_backtest_golden.py`: el hesabı beklentiler; determinizm dahil)
- [x] Sabit spread, gap, DST, weekend rollover, missing/duplicate bar ve threshold edge-case testlerini ekle. (gap: weekend financing; DST: kaynak-tz tespiti; price-gap jump ve resmi tatil eksik)
- [x] Her engine değişikliğinde bu testleri CI test setine dahil et. (`.github/workflows/ci.yml`: `pytest tests -q` + `npm --prefix frontend run build`)

Kabul ölçütü: EURUSD 4H akışında maliyet ve zaman kuralları deterministik olarak test edilir; regression testleri beklenen equity/işlem sonuçlarını doğrular.

## P1 — Search space ve Candidate Registry

### 5. SearchSpaceDefinition

- [x] `search_space_definitions` tablosu, Pydantic contract ve API uçlarını ekle.
- [x] Feature groups, individual features, feature-count bounds, model candidates ve hiperparametre aralıklarını taşı.
- [x] Signal threshold, lookback, regime, risk ve execution parametrelerini search-space'e dahil et. (thresholds/regime/max_drawdown var; lookback yok)
- [x] Wizard, REST ve MCP'nin aynı contract'ı kullanmasını sağla. (wizard space seçici + `search_space_id` bağı)

Kabul ölçütü: Bir deneyin optimizasyon alanı `OptimizationSpec` içine gömülü ayarlar yerine sürümlenebilir, doğrulanabilir bağımsız bir domain objesi olur.

### 6. Kalıcı Candidate Registry

- [x] `optimization_candidates` ve `candidate_parents` tablolarını ekle. (migration 0008)
- [x] Generation, parent candidate, genome/spec, validation/robustness metrics, Pareto rank, dominance count, seçilme/red nedeni ve artifact referanslarını sakla. (fold-detay `result.json`'da; satır `metrics` toplu validasyon skoru)
- [x] Worker aday değerlendirmelerini anlık ve kalıcı olarak yazsın. (generation/parents/rank ile `persist_candidates`)
- [x] `GET /experiments/{id}/candidates` kaynaktan değil DB'den okusun. (`parents` ile birlikte)
- [x] `GET /candidates/{id}` ve Candidate Lab UI'ını ekle. (Optimization Lab sekmesinde DB-backed aday tablosu)

Kabul ölçütü: Bir adayın neden seçildiği, hangi adaylardan türediği ve hangi validation sonuçlarıyla elendiği deney sonucu silinse dahi denetlenebilir.

## P1 — Lineage ve feature intelligence

### 7. Experiment lineage graph

- [x] `experiment_edges` tablosunu ekle.
- [x] `CLONED_FROM`, `AUTO_REFINED_FROM`, `FEATURE_REDUCED_FROM`, `REGULARIZED_FROM`, `VALIDATION_CHANGED_FROM`, `REGIME_SPECIALIZED_FROM`, `POST_TEST_ITERATION_FROM` relation type'larını tanımla. (klon-sırası spec-diff sınıflandırması yazar; seal-kirliliği öncelikli)
- [x] Her edge için reason code, actor type ve change summary sakla.
- [x] Lineage API ve graf tabanlı UI'ı ekle. (Köken sekmesi: ata/torun zinciri + düğüm metrikleri)

Kabul ölçütü: Her node üzerinde Sharpe, return, max drawdown ve validation→test degradation görünür; kullanıcı bir deneyin kökenine geri gidebilir.

### 8. Feature Intelligence Layer

- [x] `feature_evaluations`, `feature_stability_runs`, `feature_regime_metrics` ve `feature_selection_events` tablolarını ekle. (migration 0009 + `feature_redundancy_pairs`)
- [x] IC/IC decay, rolling IC, sign consistency, missingness, drift, redundancy, selection frequency ve fitness contribution hesaplarını kalıcı hale getir. (ölçülen missingness; drift ayrı metrik olarak yok, rolling-IC + rejim-IC ile izlenir)
- [x] Regime bazlı feature metriklerini ekle. (geliştirme-verisi rejim IC'leri)
- [x] Feature Lab ekranını ve ilgili API'leri ekle. (`GET .../feature-intelligence`, Features sekmesi DB görünümü)

Kabul ölçütü: Feature analizi yalnızca tek `result.json` içindeki bir çıktı değil, deneyler boyunca karşılaştırılabilen tarihsel bir araştırma varlığıdır.

## P2 — Gelişmiş optimizasyon ve regime-aware araştırma

### 9. Gerçek multi-objective optimizer

- [x] Objective vector: Sharpe, Return, Sortino, MaxDrawdown, Turnover, Cost. (aday başına `objectives` + yön haritası; cost = turnover × tek-yön tahmini)
- [x] Constraint: min trades, max exposure, max drawdown. (`min_trades`/`max_exposure` spec'te, ihlal listesi adayda)
- [x] Pareto rank ve domination count hesapla ve kaydet.
- [x] Pareto frontier UI/API'da objective seçimini destekle. (scatter X/Y eksen seçimi: 6 objective; API zaten aday başına metrics+objectives döndürür)

### 10. RegimeRouter

- [x] Candidate için overall/regime metrics, regime stability, worst-regime drawdown ve regime coverage hesapla. (validasyon-dilim rejim metrikleri + kapsam; stability ayrı skor değil, rejim Sharpe/DD dağılımıyla izlenir)
- [x] `RegimeRouter` adapter'ını tanımla. (dev-fit/causal rapor + worst-regime gate; teste dokunmaz)
- [ ] Regimeye göre model/strateji/flat exposure yönlendirmesini search space'e ekle.

Kabul ölçütü: HMM yalnızca açıklayıcı rapor olmaktan çıkar; model değerlendirme ve seçiminde ölçülebilir bir domain girdisi olur.

## P2 — Agent, MCP ve approval policy

### 11. DSL ve prompt-to-spec akışı

- [ ] Experiment Specification DSL tanımla ve validate endpoint'i ekle.
- [ ] Prompt → hypothesis → draft ExperimentSpecification dönüşümünü approval öncesinde göster.
- [ ] LLM sağlayıcısını domain katmanından ayrı adapter olarak tasarla.

### 12. MCP V2 araçları ve onay kuralları

- [x] `validate_experiment_spec`, `estimate_experiment_cost`, `estimate_research_risk` araçlarını ekle. (`validate_experiment_spec` → `POST /research/estimate` politika+maliyet+risk döndürür; ayrı cost/risk aracı yok, tek endpoint ikisini de verir)
- [x] Search space, candidates, lineage, budget, seal, robustness ve feature stability araçlarını ekle. (hepsi MCP'de; robustness ayrı rapor endpoint'i yok, cost-sensitivity + candidate metrikleriyle izlenir)
- [ ] `request_test_unseal` doğrudan erişim vermesin; approval request oluştursun.
- [ ] AUTO_READ, AUTO_CREATE_DRAFT, APPROVAL_REQUIRED_TO_RUN, AUTO_RUN_WITHIN_BUDGET ve human-required seviyelerini uygula.

Kabul ölçütü: Agent yalnızca domain araçlarını kullanır; test açma, champion ve deployment işlemlerini policy/approval olmadan yapamaz.

## P3 — Sonraki fazlar

- [ ] DataProviderAdapter ve provider/revision/license provenance alanları.
- [ ] ALFRED/vintage, gerçek macro/cross-asset ve FX market-data entegrasyonları.
- [ ] PSR, Deflated Sharpe, PBO, parameter sensitivity ve robustness report.
- [ ] Optuna/Bayesian search, stacking, genetic ensemble, ensemble weights.
- [ ] TFT/LSTM ve ileri model havuzu.
- [ ] Champion/Challenger, RBAC/OAuth, distributed workers ve deployment bridge.

## Önerilen teslim sırası

1. Sealed test + research budget migration/service/API/testleri.
2. FX reality config + backtest regression suite.
3. SearchSpaceDefinition + Candidate Registry.
4. Lineage graph + Feature Intelligence Layer.
5. Multi-objective + RegimeRouter.
6. Prompt/DSL + MCP approval policy.

## İlgili mevcut modüller

- `backend/platform/schema.py`: specification ve policy contract'ları.
- `backend/platform/db.py`: tablo tanımları; yeni migration'larla birlikte güncellenmeli.
- `backend/platform/service.py`: snapshot, lifecycle, audit ve orchestration.
- `backend/platform/research.py`: GA, test izolasyonu, feature ve regime hesapları.
- `backend/platform/api.py`: REST surface.
- `backend/mcp/server.py`: domain-level MCP adapter.
- `frontend/src/ResearchPlatform.tsx`: wizard, registry, detail, compare ve yeni lab ekranları.
