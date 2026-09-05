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
- [x] Timezone, DST, hafta sonu ve tatil takvimini doğrula. (`audit_calendar`: weekend/midweek gap ayrımı + kaynak timezone tespiti snapshot'a yazılır; reject yok, resmi tatil takvimi yok)
- [x] Signal timestamp ile executable price ayrımını engine seviyesinde koru. (`fx_backtest` imzası + curve `timestamp`/`signal_timestamp` ayrımı; golden testte sıralama doğrulanır)
- [ ] Pozisyon büyüklüğü, kaldıraç ve margin için MVP sınırlarını tanımla.

### 4. Backtest regression suite

- [x] Golden dataset/case altyapısı oluştur. (`tests/test_backtest_golden.py`: el hesabı beklentiler; determinizm dahil)
- [x] Sabit spread, gap, DST, weekend rollover, missing/duplicate bar ve threshold edge-case testlerini ekle. (gap: weekend financing; DST: kaynak-tz tespiti; price-gap jump ve resmi tatil eksik)
- [ ] Her engine değişikliğinde bu testleri CI test setine dahil et. (`.github/` workflow'u yok)

Kabul ölçütü: EURUSD 4H akışında maliyet ve zaman kuralları deterministik olarak test edilir; regression testleri beklenen equity/işlem sonuçlarını doğrular.

## P1 — Search space ve Candidate Registry

### 5. SearchSpaceDefinition

- [ ] `search_space_definitions` tablosu, Pydantic contract ve API uçlarını ekle.
- [ ] Feature groups, individual features, feature-count bounds, model candidates ve hiperparametre aralıklarını taşı.
- [ ] Signal threshold, lookback, regime, risk ve execution parametrelerini search-space'e dahil et.
- [ ] Wizard, REST ve MCP'nin aynı contract'ı kullanmasını sağla.

Kabul ölçütü: Bir deneyin optimizasyon alanı `OptimizationSpec` içine gömülü ayarlar yerine sürümlenebilir, doğrulanabilir bağımsız bir domain objesi olur.

### 6. Kalıcı Candidate Registry

- [ ] `optimization_candidates` ve `candidate_parents` tablolarını ekle.
- [ ] Generation, parent candidate, genome/spec, validation/robustness metrics, Pareto rank, dominance count, seçilme/red nedeni ve artifact referanslarını sakla.
- [ ] Worker aday değerlendirmelerini anlık ve kalıcı olarak yazsın.
- [ ] `GET /experiments/{id}/candidates` kaynaktan değil DB'den okusun.
- [ ] `GET /candidates/{id}` ve Candidate Lab UI'ını ekle.

Kabul ölçütü: Bir adayın neden seçildiği, hangi adaylardan türediği ve hangi validation sonuçlarıyla elendiği deney sonucu silinse dahi denetlenebilir.

## P1 — Lineage ve feature intelligence

### 7. Experiment lineage graph

- [ ] `experiment_edges` tablosunu ekle.
- [ ] `CLONED_FROM`, `AUTO_REFINED_FROM`, `FEATURE_REDUCED_FROM`, `REGULARIZED_FROM`, `VALIDATION_CHANGED_FROM`, `REGIME_SPECIALIZED_FROM`, `POST_TEST_ITERATION_FROM` relation type'larını tanımla.
- [ ] Her edge için reason code, actor type ve change summary sakla.
- [ ] Lineage API ve graf tabanlı UI'ı ekle.

Kabul ölçütü: Her node üzerinde Sharpe, return, max drawdown ve validation→test degradation görünür; kullanıcı bir deneyin kökenine geri gidebilir.

### 8. Feature Intelligence Layer

- [ ] `feature_evaluations`, `feature_stability_runs`, `feature_regime_metrics` ve `feature_selection_events` tablolarını ekle.
- [ ] IC/IC decay, rolling IC, sign consistency, missingness, drift, redundancy, selection frequency ve fitness contribution hesaplarını kalıcı hale getir.
- [ ] Regime bazlı feature metriklerini ekle.
- [ ] Feature Lab ekranını ve ilgili API'leri ekle.

Kabul ölçütü: Feature analizi yalnızca tek `result.json` içindeki bir çıktı değil, deneyler boyunca karşılaştırılabilen tarihsel bir araştırma varlığıdır.

## P2 — Gelişmiş optimizasyon ve regime-aware araştırma

### 9. Gerçek multi-objective optimizer

- [ ] Objective vector: Sharpe, Return, Sortino, MaxDrawdown, Turnover, Cost.
- [ ] Constraint: min trades, max exposure, max drawdown.
- [ ] Pareto rank ve domination count hesapla ve kaydet.
- [ ] Pareto frontier UI/API'da objective seçimini destekle.

### 10. RegimeRouter

- [ ] Candidate için overall/regime metrics, regime stability, worst-regime drawdown ve regime coverage hesapla.
- [ ] `RegimeRouter` adapter'ını tanımla.
- [ ] Regimeye göre model/strateji/flat exposure yönlendirmesini search space'e ekle.

Kabul ölçütü: HMM yalnızca açıklayıcı rapor olmaktan çıkar; model değerlendirme ve seçiminde ölçülebilir bir domain girdisi olur.

## P2 — Agent, MCP ve approval policy

### 11. DSL ve prompt-to-spec akışı

- [ ] Experiment Specification DSL tanımla ve validate endpoint'i ekle.
- [ ] Prompt → hypothesis → draft ExperimentSpecification dönüşümünü approval öncesinde göster.
- [ ] LLM sağlayıcısını domain katmanından ayrı adapter olarak tasarla.

### 12. MCP V2 araçları ve onay kuralları

- [ ] `validate_experiment_spec`, `estimate_experiment_cost`, `estimate_research_risk` araçlarını ekle.
- [ ] Search space, candidates, lineage, budget, seal, robustness ve feature stability araçlarını ekle.
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
