# RegimeLab V2 — QuantConnect Karşısında Ürün Farklılaştırma ve Uygulama Override'ı

> **Astra için öncelik kuralı:** Bu V2 bölümü, aşağıdaki orijinal spesifikasyonla çeliştiği yerde **önceliklidir**. Orijinal spesifikasyonun experiment-centric, API-first, locked-test, GA, MCP ve audit prensipleri korunur; ancak ürün konumlandırması ve geliştirme sırası aşağıdaki rekabet stratejisine göre güncellenir.

## 0. Neden V2 gerekli?

QuantConnect 2026 itibarıyla sadece backtest/optimization ürünü değildir. Cloud research, Jupyter, geniş veri ekosistemi, backtest, parameter optimization, paper/live trading, çok sayıda brokerage entegrasyonu, Research Pipeline, AI Assistants ve MCP Server sunmaktadır. Bu nedenle RegimeLab'ın **"AI + backtest + API + MCP"** şeklinde konumlandırılması tek başına farklılaştırıcı değildir.

RegimeLab'ın ana konumlandırması aşağıdaki şekilde değiştirilmelidir:

> **RegimeLab = Agent-First, Experiment-Centric, Regime-Aware Quant Research Optimization OS**
>
> Kod/proje merkezli genel trading platformu olmak yerine; feature/model/ensemble arama uzayını otomatik keşfeden, genetik ve multi-objective optimizasyon yapan, test setini platform seviyesinde mühürleyen, bütün denemeleri lineage ile saklayan ve AI agent'ların kontrollü şekilde tekrar tekrar araştırma yapabildiği bir research operating system olmalıdır.

## 1. QuantConnect ile doğrudan rekabet etmeyeceğimiz alanlar

İlk sürümlerde aşağıdaki alanlarda QuantConnect'i kopyalamaya çalışma:

- Büyük brokerage entegrasyon kataloğu
- Full live-trading execution platformu
- Kapsamlı cloud IDE / notebook ürünü
- Çok geniş dataset marketplace
- Genel amaçlı algoritma geliştirme ortamı
- Her asset class için exchange/broker reality model kapsamı

Bunlar uzun vadeli entegrasyon alanlarıdır. V1-V2 ürün odağı **automated research discovery + experiment governance** olmalıdır.

## 2. RegimeLab'ın zorunlu farklılaştırıcıları

### 2.1 Schema/Experiment-first; code/project-first değil

Ana obje `Project` veya kullanıcı kodu değil, versioned `ExperimentSpecification` olmalıdır. Kullanıcı ya UI wizard ile ya da doğal dil ile aynı schema'yı üretir. AI agent da sadece bu schema ve domain-level tools üzerinden çalışır.

Her experiment specification immutable version almalı:

```text
SPEC-000184-v3
```

Değişiklik yeni version veya child experiment üretmelidir. Çalışmış bir run'ın config'i sessizce mutate edilmemelidir.

### 2.2 Search Space birinci sınıf domain objesi

Mevcut `Genome` yaklaşımı genişletilerek `SearchSpaceDefinition` eklenmelidir.

```text
SearchSpaceDefinition
├── feature_groups
├── individual_features
├── feature_count_bounds
├── model_candidates
├── model_hyperparameters
├── ensemble_structure
├── ensemble_weights
├── signal_thresholds
├── lookback_windows
├── regime_parameters
├── risk_parameters
└── execution_parameters
```

Bu obje REST, MCP, UI ve optimizer'lar arasında ortak contract olmalıdır.

### 2.3 Genetic Algorithm sadece feature selector olmamalı

GA için iki seviye tanımla:

**MVP:**
- Feature selection
- Model hyperparameters

**V2:**
- Model selection
- Ensemble membership
- Ensemble weights
- Thresholds
- Lookback
- Regime parameters
- Risk parameters

Böylece ürün sıradan parameter optimizer'dan ayrılır.

### 2.4 Multi-objective optimization gerçek anlamda first-class olmalı

Tek skor yanında Pareto optimizasyonu desteklenmelidir.

```text
maximize: Sharpe, Return, Sortino
minimize: MaxDrawdown, Turnover, Cost
constraints: min_trades, max_exposure, max_drawdown
```

`OptimizationCandidate` entity'sinde Pareto rank, domination count ve objective vector saklanmalıdır.

### 2.5 Sealed / Locked Test Governance

Mevcut `locked test` kuralı güçlendirilmeli. Test seti sadece optimizer'dan gizli olmayacak; **platform tarafından sealed** olacaktır.

Yeni alanlar:

```text
test_dataset_id
test_seal_id
test_access_count
test_first_opened_at
test_invalidated_at
test_invalidation_reason
```

Kurallar:
1. Optimizer test dataset'ine erişemez.
2. Agent test sonucuna göre otomatik optimization loop başlatamaz.
3. Test sonucu görüldükten sonra aynı holdout üzerinde sınırsız tekrar "final test" yapılamaz.
4. Test sonucundan etkilenerek yeni child experiment oluşturulursa sistem bunu `POST_TEST_ITERATION` olarak işaretler.
5. Gerçek yeni final doğrulama için yeni temporal holdout / yeni sealed test epoch desteklenmelidir.

### 2.6 Research Budget / Multiple Testing Guard

Compute budget'tan ayrı bir **research budget** ekle.

Takip:

```text
hypothesis_count
experiment_count
candidate_count
backtest_count
optimization_trial_count
sealed_test_access_count
```

UI'da `Research Overfitting Risk` kartı göster.

İleri metrikler:
- Probabilistic Sharpe Ratio
- Deflated Sharpe Ratio
- Probability of Backtest Overfitting (PBO) — opsiyonel ileri sürüm
- Parameter sensitivity
- Selection stability

### 2.7 Feature Intelligence Layer

Feature Lab, sadece feature listesi olmamalı. Aşağıdakiler aynı feature için zaman içinde saklanmalı:

- IC / IC decay
- rolling IC
- sign consistency
- stability
- regime-specific IC
- missingness
- drift
- redundancy cluster
- selection frequency
- GA survival rate
- fitness contribution when present/absent

Yeni entity önerisi:

```text
feature_evaluations
feature_stability_runs
feature_regime_metrics
feature_selection_events
```

### 2.8 Regime-aware research, UI süsü değil domain mantığı olmalı

Regime engine çıktıları model değerlendirmesine doğrudan girmelidir.

Her candidate için:

```text
overall_metrics
regime_metrics[]
regime_stability_score
worst_regime_drawdown
regime_coverage
```

V2'de `RegimeRouter` adapter ekle:

```python
class RegimeRouter:
    def select_strategy(self, regime, candidate_pool, context): ...
```

Agent şu tip experiment üretebilmeli:

```text
Trend -> XGBoost
Range -> Mean Reversion
HighVol -> TFT
RiskOff -> Flat / reduced exposure
```

### 2.9 Experiment Lineage'i ürünün ana ekranlarından biri yap

Lineage sadece `parent_experiment_id` olmamalı.

Yeni `experiment_edges` entity:

```text
parent_id
child_id
relation_type
reason_code
actor_type
change_summary
created_at
```

Relation örnekleri:

```text
CLONED_FROM
AUTO_REFINED_FROM
FEATURE_REDUCED_FROM
REGULARIZED_FROM
VALIDATION_CHANGED_FROM
REGIME_SPECIALIZED_FROM
POST_TEST_ITERATION_FROM
```

UI'da graph üzerinde her node için Sharpe / Return / DD ve validation-test gap göster.

### 2.10 Agent farkı: kod yazan agent değil, kontrollü araştırma yapan agent

QuantConnect benzeri sistemlerde agent'lar proje kodu/notebook üzerinde çalışabilir. RegimeLab'ın agent davranışı farklı olmalı:

```text
Prompt
  ↓
Hypothesis
  ↓
ExperimentSpecification
  ↓
SearchSpaceDefinition
  ↓
Policy + Research Budget Check
  ↓
Cost Estimate
  ↓
Run
  ↓
Validation Review
  ↓
Robustness Gate
  ↓
Optional Child Experiment
  ↓
Comparison
  ↓
Research Report
```

Agent'ın default tool setinde `execute_python`, `execute_shell`, `execute_sql` bulunmaması kuralı korunur.

### 2.11 Agent approval seviyeleri

Yeni policy:

```text
AUTO_READ
AUTO_CREATE_DRAFT
APPROVAL_REQUIRED_TO_RUN
AUTO_RUN_WITHIN_BUDGET
HUMAN_REQUIRED_FOR_TEST_UNSEAL
HUMAN_REQUIRED_FOR_CHAMPION
HUMAN_REQUIRED_FOR_DEPLOYMENT
```

Bu seviyeler tenant/user bazlı configure edilebilmelidir.

### 2.12 Candidate Registry ekle

Sadece experiment sonucu değil, optimizer'ın önemli adayları kalıcı olmalıdır.

```text
candidate_id
experiment_id
optimization_run_id
generation
parent_candidate_ids
genome/spec
validation_metrics
robustness_metrics
pareto_rank
selected_for_test
rejection_reason
artifact_refs
```

Bu sayede agent "neden bu model seçildi?" sorusuna audit edilebilir cevap verir.

## 3. QuantConnect karşısındaki en büyük teknik açığımız: Backtest Reality Model

Mevcut dokümanda cost ve slippage var ancak bu bölüm yeterince güçlü değil. QuantConnect'in en büyük avantajlarından biri olgun event-driven backtest/live execution gerçeklik modelidir. RegimeLab özellikle FX için şu katmanı eklemelidir:

### 3.1 BacktestRealityConfig

```text
spread_model
commission_model
slippage_model
fill_model
bid_ask_mode
market_hours_calendar
holiday_calendar
timezone
DST_policy
latency_model
position_sizing
leverage
margin_model
financing_cost
FX_swap_rollover
stop_fill_policy
gap_policy
partial_fill_policy (later)
```

### 3.2 FX için zorunlu doğruluk

EURUSD odaklı MVP'de en az:

- Bid/ask spread
- Variable spread seçeneği
- Commission
- Slippage
- Swap / rollover / financing
- Timezone + DST
- Weekend/holiday handling
- Signal time vs executable price separation
- Bar close bilgisinin aynı bar içinde kullanılmasıyla oluşan look-ahead hatasını engelleme

olmalıdır.

### 3.3 Backtest validation suite

Golden test datasetleri oluştur:

- sabit spread senaryosu
- gap senaryosu
- DST geçişi
- hafta sonu rollover
- missing bar
- duplicate timestamp
- stop/threshold edge case

Her engine değişikliğinde regression test çalışmalıdır.

## 4. Data katmanı güçlendirilmeli

QuantConnect veri erişiminde çok güçlüdür. RegimeLab bu alanı ilk etapta marketplace ile değil **Data Adapter + Provenance + PIT correctness** ile çözmelidir.

Yeni interface:

```python
class DataProviderAdapter:
    def discover(...): ...
    def fetch(...): ...
    def snapshot(...): ...
    def provenance(...): ...
```

`dataset_snapshot` alanlarına ekle:

```text
provider
provider_dataset_id
raw_hash
normalized_hash
schema_hash
release_timestamp_policy
revision_policy
normalization_policy
timezone_policy
license_metadata
```

Data quality report experiment başlamadan üretilebilmelidir.

## 5. RegimeLab'ın QuantConnect'e göre hedef fark tablosu

| Alan | QuantConnect yönü | RegimeLab hedefi |
|---|---|---|
| Ana paradigma | Project / algorithm / code centric | Experiment / search-space centric |
| AI/MCP | Güçlü, zaten mevcut | Parite özelliği; tek başına USP değil |
| Agent | Kod, notebook, backtest, deploy | Guardrail'li autonomous research loop |
| Optimization | Cloud parameter optimization ağırlıklı | GA + Optuna + full search-space + Pareto |
| Feature selection | Kullanıcının/model kodunun sorumluluğu ağırlıklı | First-class feature discovery/evolution |
| Model selection | Kod/proje içinde tanımlanır | Search-space içinde model seçimi |
| Ensemble search | Genel amaçlı kodla yapılabilir | First-class genetic ensemble search |
| Test governance | OOS/walk-forward pratikleri mevcut | Platform-enforced sealed test protocol |
| Experiment history | Project/backtest/optimization history | ML-style registry + immutable spec + lineage |
| Feature analytics | Araştırma kodu ile yapılabilir | IC/stability/survival/drift first-class UI |
| Regime | Strateji kodunda yapılabilir | Core regime evaluation + routing layer |
| Multiple testing | Research guidance/overfit uyarıları | Research budget + trial/test-access ledger |
| Data/brokerages | Çok güçlü | İlk sürümde sınırlı adapter tabanlı |
| Live trading | Çok güçlü | V1/V2 out of scope; adapter-ready |

## 6. Mevcut faz planı nasıl değişmeli?

Aşağıdaki plan, orijinal `Phase 1..6` planını override eder.

### Phase 1 — Experiment Foundation
- Immutable ExperimentSpecification versioning
- Experiment Registry
- Experiment Run
- Dataset snapshot + hash/provenance
- API-first backend
- Async jobs
- Live status/logs
- Experiment detail
- Reproducibility bundle

### Phase 2 — Financial Validation + Reality Layer
- Walk-forward validation
- Sealed test service
- Test access audit
- Cost/slippage/spread
- FX swap/rollover
- Timezone/DST
- Look-ahead guards
- Backtest regression suite

### Phase 3 — Search Space + GA Differentiation
- Feature Registry
- SearchSpaceDefinition
- Model Adapter
- Genetic feature selection
- GA hyperparameter search
- Candidate Registry
- Optimization progress
- Feature survival

### Phase 4 — Comparison + Research Governance
- Experiment compare
- Lineage graph
- Config/feature/model diffs
- Validation-test degradation
- Research budget
- Multiple-testing ledger
- PSR / Deflated Sharpe
- Robustness gates

### Phase 5 — Advanced AutoML
- Optuna / Bayesian
- Multi-objective
- Pareto frontier
- Model selection in search-space
- Genetic ensemble
- Ensemble weights
- Threshold/risk optimization
- Regime-aware metrics
- RegimeRouter

### Phase 6 — Agent / MCP
- Experiment DSL
- AI prompt -> hypothesis -> spec
- MCP adapter
- Domain-level MCP tools
- Agent approval policy
- Cost + research-budget preview
- Agent activity/audit
- Auto child experiment (validation-only feedback)
- Reviewer agent

### Phase 7 — Deployment Bridge (sonra)
- Paper trading adapter
- Broker abstraction
- Champion -> paper candidate promotion
- Live-vs-backtest reconciliation
- Deployment approval gate
- Gerçek para deployment default olarak kapalı

## 7. Definition of Done V2

İlk ciddi farklılaştırılmış release aşağıdakiler tamamlandığında oluşur:

- ExperimentSpecification immutable ve versioned.
- Dataset snapshot provenance/hash kaydediliyor.
- Walk-forward ve sealed test gerçekten enforce ediliyor.
- Test erişimi audit ediliyor.
- EURUSD backtest reality katmanı spread/slippage/swap/timezone/DST içeriyor.
- GA feature selection + hyperparameter search çalışıyor.
- SearchSpaceDefinition API/UI/MCP ortak contract.
- Candidate Registry mevcut.
- En az XGBoost ve LightGBM aynı experiment içinde aranabiliyor.
- Sharpe, Return, MaxDD, Sortino ve PSR raporlanıyor.
- Feature survival + stability ekranı var.
- 2-5 experiment karşılaştırılıyor.
- Experiment lineage graph görülebiliyor.
- Validation -> test degradation görünür.
- Research budget ve optimization trial ledger mevcut.
- REST API tüm akışı kapsıyor.
- MCP aynı domain servislerini kullanıyor.
- Agent doğal dil promptundan draft spec üretip kullanıcıya gösterebiliyor.
- Agent approval/policy katmanını bypass edemiyor.
- Agent test sonucuna göre sessizce yeniden optimize edemiyor.
- Backtest regression suite CI içinde çalışıyor.

## 8. UI değişiklikleri

Sol menü V2:

```text
Genel Bakış

Araştırma
  Yeni Deney
  Deneyler
  Karşılaştırma
  Lineage
  Optimization Lab

Veri Merkezi
Feature Lab
Model Lab
Regime Lab
Candidate Lab
Research Risk
Champion / Challenger

AI Research Agent
MCP / API
Metodoloji
Ayarlar
```

Experiment Detail'e yeni sekmeler:

```text
Overview
Equity
Trades
Features
Models
Optimization
Candidates
Regimes
Validation
Robustness
Lineage
Artifacts
Audit
```

Ana kartlara ekle:

```text
Validation Sharpe
Sealed Test Sharpe
Validation -> Test Degradation
Deflated Sharpe / PSR
Research Trial Count
Test Access Count
```

## 9. MCP Tool Set V2

Mevcut tool setine ekle:

```text
validate_experiment_spec
estimate_experiment_cost
estimate_research_risk
get_search_space
get_candidates
get_candidate
get_candidate_lineage
get_research_budget
get_test_seal_status
request_test_unseal
get_robustness_report
get_feature_stability
get_feature_regime_metrics
get_lineage
```

`request_test_unseal` tool'u doğrudan unseal yapmamalı; approval workflow başlatmalıdır.

## 10. API ekleri

```http
POST /api/v1/experiment-specs/validate
POST /api/v1/experiments/{id}/estimate
GET  /api/v1/experiments/{id}/candidates
GET  /api/v1/candidates/{candidate_id}
GET  /api/v1/experiments/{id}/lineage
GET  /api/v1/experiments/{id}/robustness
GET  /api/v1/experiments/{id}/research-budget
GET  /api/v1/experiments/{id}/test-seal
POST /api/v1/experiments/{id}/test-unseal-requests
GET  /api/v1/features/{id}/stability
GET  /api/v1/features/{id}/regime-metrics
```

## 11. DB ekleri

Yeni tablolar / entity'ler:

```text
experiment_spec_versions
experiment_edges
search_space_definitions
optimization_candidates
candidate_parents
research_budgets
research_trial_events
test_seals
test_access_events
robustness_reports
feature_evaluations
feature_stability_runs
feature_regime_metrics
backtest_reality_configs
backtest_regression_cases
```

## 12. Astra için yeni kısa talimat

> Mevcut RegimeLab'i QuantConnect'in daha küçük bir kopyasına dönüştürme. AI/MCP/backtest tek başına ürün farkı değildir. Ana farkı experiment-centric automated research yap: immutable ExperimentSpecification, first-class SearchSpaceDefinition, GA ile feature/model/hyperparameter/ensemble araması, multi-objective Pareto, sealed test governance, research-budget/multiple-testing guard, Candidate Registry, feature stability/survival, regime-aware evaluation/routing ve experiment lineage. İlk etapta geniş brokerage/live-trading/IDE/data-marketplace kapsamına girme. Önce EURUSD 4H üzerinde backtest reality ve research correctness'i production-quality hale getir. Agent'lar domain-level MCP tools kullanmalı ve test/compute/research policy'lerini bypass edememeli.

## 13. QuantConnect referans baseline — 5 Eylül 2026

Astra rekabet analizi yaparken aşağıdaki QuantConnect yeteneklerini "bizde yok" diye yanlış varsaymamalı:

- Cloud Research + Jupyter notebooks
- Backtesting + rich result charts
- Cloud parameter optimization
- Research Pipeline (idea -> research -> backtest -> paper -> live)
- AI Assistants / assistant teams
- MCP Server
- REST API
- Object Store / model artifact storage
- Paper + live trading
- Çok sayıda brokerage entegrasyonu
- Dataset Market

Özellikle QuantConnect Cloud optimizer'ın güncel dokümantasyonda Grid Search ağırlıklı olduğu, cloud tarafında en fazla üç parameter optimize ettiği; buna karşın RegimeLab'ın GA/full search-space/Pareto yaklaşımını first-class ürün özelliği yapması hedeflenir.

Referanslar:
- https://www.quantconnect.com/docs/v2/ai-assistance
- https://www.quantconnect.com/docs/v2/ai-assistance/mcp-server
- https://www.quantconnect.com/docs/v2/ai-assistance/assistants
- https://www.quantconnect.com/docs/v2/cloud-platform/research-pipeline
- https://www.quantconnect.com/docs/v2/cloud-platform/optimization/strategies
- https://www.quantconnect.com/docs/v2/cloud-platform/optimization/parameters
- https://www.quantconnect.com/docs/v2/cloud-platform/optimization/objectives
- https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/results
- https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/brokerages

---

# ORİJİNAL SPESİFİKASYON — V2 override'larıyla birlikte geçerlidir

# RegimeLab — AI-Native Quant Research Platform
## Astra Uygulama / Geliştirme Spesifikasyonu

**Doküman amacı:** Mevcut RegimeLab projesini, tek bir backtest dashboard'undan; deneylerin kalıcı olarak tutulduğu, karşılaştırılabildiği, genetik algoritma ile feature/model/parametre optimizasyonu yapılabildiği, çoklu model ve stacked model desteği olan, REST API ve MCP üzerinden AI agent'ların kullanabildiği bir **AI-native Quant Research Platform** haline getirmek.

> **Astra için temel talimat:** Mevcut çalışan ekranları ve mevcut proje yapısını mümkün olduğunca koru. Aşağıdaki özellikleri mevcut projeye modüler biçimde ekle. Var olan stack ile uyumlu ilerle; eksik bir teknoloji tercihi gerekiyorsa aşağıdaki önerilen varsayılanları kullan. İş kurallarını UI içine gömme. Tüm research/experiment işlemlerini API-first tasarla. Web UI ve AI agent'lar aynı backend servislerini kullanmalı.

---

# 1. Ürün Vizyonu

RegimeLab yalnızca grafik gösteren veya tek seferlik backtest çalıştıran bir uygulama olmayacak.

Hedef ürün:

**AI-Native Quant Research & Experimentation Platform**

Sistem aşağıdaki ana iş akışını uçtan uca yönetmeli:

```text
Data Acquisition
    ↓
Data Cleaning / Transformation
    ↓
Feature Engineering
    ↓
Feature Selection
    ↓
Model Training
    ↓
Model / Hyperparameter Optimization
    ↓
Validation
    ↓
Locked Test
    ↓
Backtest
    ↓
Risk / Regime Analysis
    ↓
Experiment Registry
    ↓
Experiment Comparison
    ↓
Champion / Challenger
```

Kullanıcı sadece bir model çalıştırmak yerine bir **Experiment** tanımlar. Sistem aynı deney altında birden fazla model, feature seti, optimizer ve strateji kombinasyonunu çalıştırabilir.

---

# 2. Ana Tasarım Prensibi

## 2.1 API-first

Web sitesi ana ürün değildir. Ana ürün **Quant Research Engine + Experiment Platform** olmalıdır.

İstemciler:

```text
React / Web UI
AI Agent
MCP Client
External REST Client
CLI (ileride)
```

hepsi aynı backend servislerini kullanmalıdır.

UI doğrudan Python fonksiyonu, notebook veya model kodu çağırmamalıdır.

Örnek:

```text
Web UI ───────────┐
                  │
AI Agent ─────── REST/MCP ── API Gateway ── Experiment Orchestrator
                  │
External Client ──┘
```

---

# 3. Önerilen Teknik Mimari

Mevcut projede eşdeğer teknolojiler varsa korunabilir.

## 3.1 Default teknoloji önerisi

### Frontend
- React / Next.js
- TypeScript
- Mevcut dark theme korunmalı
- Charting: mevcut chart library korunabilir; yoksa Lightweight Charts / ECharts / Plotly
- SSE veya WebSocket ile canlı job progress

### Backend
- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

### Database
- PostgreSQL

### Cache / Job State
- Redis

### Long-running jobs
Tercihlerden biri:
- Celery + Redis
- Dramatiq + Redis
- RQ

Mevcut projede job altyapısı varsa onu koru.

### Artifact Storage
- Local filesystem dev ortamında
- Production için S3-compatible object storage
  - MinIO
  - AWS S3
  - Azure Blob adapter (ileride)

### ML / Optimization
- scikit-learn
- XGBoost
- LightGBM
- PyTorch
- PyTorch Forecasting / Lightning gerekirse
- Optuna
- Custom Genetic Algorithm veya DEAP

### MCP
- Resmi / güncel MCP SDK ile ayrı adapter katmanı
- MCP domain logic içermemeli
- REST/domain service'leri çağırmalı

---

# 4. High-Level Architecture

```text
                          REGIMELAB

     ┌───────────────────────────────────────────────┐
     │                 CLIENT LAYER                  │
     │                                               │
     │   Web UI       AI Agent       MCP Client      │
     └───────────────┬───────────────┬───────────────┘
                     │               │
                     │ REST          │ MCP
                     ▼               ▼
              ┌────────────────────────────┐
              │       API / MCP LAYER      │
              │ Auth / RBAC / Validation   │
              └─────────────┬──────────────┘
                            │
                            ▼
              ┌────────────────────────────┐
              │   EXPERIMENT ORCHESTRATOR  │
              └─────────────┬──────────────┘
                            │
          ┌─────────────────┼────────────────────┐
          ▼                 ▼                    ▼
    DATA ENGINE       RESEARCH ENGINE      REGISTRY
    - ingestion       - features           - experiments
    - cleaning        - models             - runs
    - PIT checks      - GA                 - metrics
    - snapshots       - Optuna             - artifacts
                      - stacking
                      - validation
                      - backtest
          │                 │                    │
          └─────────────────┼────────────────────┘
                            ▼
                    JOB EXECUTION LAYER
                    CPU / GPU Workers
                            │
                  PostgreSQL / Redis / S3
```

---

# 5. Experiment Kavramı

Platformun ana domain objesi **Experiment** olmalıdır.

Her araştırma kalıcı bir ID almalı.

Örnek:

```text
EXP-2026-000184
```

Her experiment reproducible olmalıdır.

## 5.1 Experiment içerisinde tutulacak bilgiler

- Experiment ID
- Name
- Description
- Parent Experiment ID
- Tags
- Owner
- Market
- Symbol
- Timeframe
- Dataset snapshot
- Dataset hash/version
- Train period
- Validation period
- Test period
- Feature set/version
- Model list
- Model configuration
- Optimizer
- Optimizer parameters
- Genetic algorithm genome definition
- Random seed
- Transaction cost settings
- Slippage settings
- Validation method
- Backtest configuration
- Code version / git commit
- Runtime environment
- Job status
- Start time
- End time
- Duration
- CPU/GPU usage metadata
- Metrics
- Artifacts
- Logs

---

# 6. Experiment Lifecycle

Durum makinesi kullanılmalı.

```text
DRAFT
  ↓
QUEUED
  ↓
DATA_PREPARATION
  ↓
FEATURE_ENGINEERING
  ↓
TRAINING
  ↓
OPTIMIZING
  ↓
VALIDATING
  ↓
TESTING
  ↓
BACKTESTING
  ↓
ANALYZING
  ↓
COMPLETED
```

Hata durumları:

```text
FAILED
CANCELLED
TIMEOUT
POLICY_REJECTED
```

Her state transition loglanmalı.

---

# 7. Dataset Snapshot ve Reproducibility

Her deney güncel datayı direkt okumamalı.

Experiment başladığında dataset snapshot/version oluşturulmalı.

Örnek:

```text
EURUSD_4H_20260905_v32
```

Tutulacaklar:

- Dataset ID
- Source
- Symbol
- Timeframe
- Start/end timestamps
- Row count
- Column schema
- Missing data stats
- Hash
- Created timestamp
- Point-in-time metadata
- Revision information

Bir experiment daha sonra tekrar çalıştırıldığında aynı snapshot ile aynı sonucu üretmeye çalışmalıdır.

---

# 8. Data Pipeline

Pipeline şu şekilde modellenmeli:

```text
Raw Data
   ↓
Validation
   ↓
Cleaning
   ↓
Timestamp Alignment
   ↓
Transformation
   ↓
Derived Series
   ↓
Dataset Snapshot
```

Mümkün olan kontroller:

- Missing values
- Duplicate timestamps
- Outlier detection
- Timezone consistency
- DST audit
- Point-in-time correctness
- Look-ahead leakage kontrolü
- Survivorship kontrolü
- Macro release timestamp kontrolü
- Revision/vintage metadata

Bu kontroller modüler olmalı.

---

# 9. Feature Engineering

Feature'lar kategori bazlı tutulmalı.

Örnek kategoriler:

```text
Technical
Trend
Momentum
Volatility
Macro
Cross Asset
Rates
FX
Positioning
Microstructure
Regime
Derived Statistical
```

Örnek feature'lar:

- RSI
- ATR
- MACD
- Momentum 20
- Momentum 50
- Realized volatility
- DXY momentum
- US10Y spread
- Yield curve features
- VIX
- Cross asset correlation
- Rolling beta
- Z-score
- Cointegration residuals
- Fractional differentiation

Her feature için metadata tutulmalı:

```text
feature_id
name
category
version
parameters
lookback
source_columns
created_at
```

---

# 10. Feature Stability / Selection

Sistem sadece feature üretmemeli, feature kalitesini de ölçmelidir.

Desteklenecek analizler:

- Rolling feature stability
- Information Coefficient (IC)
- IC decay
- Feature sign consistency
- Mutual information
- Conditional mutual information
- Correlation clustering
- Redundancy pruning
- Stability selection
- PCA
- PLS
- Dynamic factor extraction
- Orthogonalization
- Residualization

UI'da feature seçimi şu modları içerebilir:

```text
Manual
Genetic Algorithm
Mutual Information
Stability Selection
Feature Importance based
```

---

# 11. Genetic Algorithm — Ana Özellik

Genetik algoritma platformun optimization engine'lerinden biri olacaktır.

Başlangıçta sadece feature selection ile başlayabilir ancak mimari aşağıdaki genome genişlemesine açık olmalı.

## 11.1 Genome

```text
Genome
├── Feature Selection
├── Model Selection
├── Hyperparameters
├── Ensemble Weights
├── Signal Thresholds
├── Lookback Window
├── Regime Parameters
└── Risk Parameters
```

Örnek chromosome:

```text
Chromosome #1842

Features:
  RSI              = 1
  ATR              = 1
  MACD             = 0
  DXY              = 1
  VIX              = 1
  YieldSpread      = 1
  Momentum20       = 1
  Momentum50       = 0

Model:
  xgboost

Hyperparameters:
  max_depth: 5
  learning_rate: 0.03
  n_estimators: 420

Trading:
  long_threshold: 0.61
  short_threshold: 0.37
  stop_loss_atr: 1.3
```

## 11.2 GA Config

```text
population_size
generations
mutation_rate
crossover_rate
elitism
selection_method
random_seed
max_features
min_features
```

## 11.3 GA Runtime Metrics

Her generation için kaydet:

- Best fitness
- Mean fitness
- Median fitness
- Worst fitness
- Population diversity
- Best Sharpe
- Best return
- Best max drawdown
- Candidate count
- Generation duration

UI canlı gösterecek.

---

# 12. Fitness / Optimization Metrics

En önemli final metrikleri:

- Sharpe Ratio
- Total Return
- Max Drawdown

Ek metrikler:

- Sortino Ratio
- Calmar Ratio
- Volatility
- Win Rate
- Profit Factor
- Turnover
- Transaction Cost
- Number of Trades
- Average Trade
- Exposure

## 12.1 Single Objective

Örnek:

```text
maximize Sharpe
```

## 12.2 Multi Objective

Tercih edilen yaklaşım:

```text
maximize:
  Sharpe
  Return

minimize:
  Max Drawdown
  Turnover
  Transaction Cost
```

Tek composite fitness desteklenebilir:

```text
fitness =
  sharpe_weight * normalized_sharpe
+ return_weight * normalized_return
- drawdown_weight * normalized_drawdown
- turnover_weight * normalized_turnover
```

Ancak mümkün olduğunda Pareto optimization desteklenmeli.

---

# 13. Pareto Frontier

Multi-objective optimization sonucunda tek winner yerine Pareto candidate listesi üretilebilmeli.

UI şu aday tiplerini gösterebilir:

- Conservative
- Balanced
- Aggressive
- Best Sharpe
- Best Drawdown
- Best Return

Kullanıcı veya AI agent final candidate seçebilmeli.

---

# 14. Train / Validation / Locked Test

**KRİTİK KURAL:** Test dataset optimizer tarafından görülemez.

Örnek:

```text
TRAIN          VALIDATION         LOCKED TEST
2020-2023      2024-2025          2026
```

Genetik algoritma ve model selection:

```text
TRAIN + VALIDATION
```

üzerinde karar verir.

En iyi candidate seçildikten sonra model/config freeze edilir.

Ardından sadece bir final ölçüm olarak:

```text
LOCKED TEST
```

çalıştırılır.

Test sonucuna göre optimizer tekrar çalıştırılmamalıdır.

UI'da açıkça göster:

```text
Test Set: LOCKED
Optimizer Access: DISABLED
```

---

# 15. Validation Yöntemleri

İlk sürüm:

- Holdout validation
- Walk-forward validation

Sonraki sürümler:

- Rolling window validation
- Expanding window
- Purged K-Fold
- Embargo

Financial time-series için random K-Fold default olmamalı.

---

# 16. Model Pool

Kullanıcı tek veya birden fazla model seçebilmeli.

İlk model havuzu:

```text
Logistic Regression
Random Forest
XGBoost
LightGBM
HMM
LSTM
TFT
Transformer-compatible model adapter
```

Model engine plugin mantığında olmalı.

Örnek interface:

```python
class ModelAdapter:
    fit(...)
    predict(...)
    predict_proba(...)
    get_params(...)
    save(...)
    load(...)
```

Yeni model eklemek core orchestration kodunu değiştirmemeli.

---

# 17. Ensemble / Stacking

Desteklenecek stratejiler:

```text
Best Individual Model
Weighted Ensemble
Stacked Model
Genetic Ensemble
```

Stacking örneği:

```text
XGBoost ──┐
TFT ──────┼── Meta Model ── Signal
HMM ──────┤
LSTM ─────┘
```

GA ileride ensemble weight'lerini de optimize edebilmeli.

---

# 18. Regime Analysis

Mevcut HMM regime analizi korunmalı ve daha fonksiyonel hale getirilmeli.

Her model/strateji için regime bazlı performans ölç:

```text
Trend
Range
High Volatility
Low Volatility
Risk On
Risk Off
```

Örnek karşılaştırma:

| Model | Trend | Range | High Vol | Low Vol |
|---|---:|---:|---:|---:|
| XGBoost | 2.10 | 0.40 | 1.30 | 1.50 |
| TFT | 1.70 | 1.20 | 1.90 | 1.10 |
| HMM Stack | 2.30 | 1.50 | 2.00 | 1.80 |

İleride regime-aware dynamic routing desteklenmeli:

```text
Trend → XGBoost
High Vol → TFT
Range → Mean Reversion Model
```

---

# 19. Experiment Lineage

Her experiment başka experiment'ten clone edilebilmeli.

```text
EXP-100 Baseline
│
├── EXP-101 + volatility features
├── EXP-102 + XGBoost
│   ├── EXP-104 + GA feature selection
│   └── EXP-105 + GA hyperparameter optimization
└── EXP-103 + TFT
```

Database:

```text
parent_experiment_id
```

Alanı bulunmalı.

UI'da graph/tree halinde gösterilebilir.

---

# 20. Clone Experiment

Kullanıcı bir experiment seçip:

```text
Clone Experiment
```

ile yeni deney oluşturabilmeli.

Yeni experiment mevcut config'i kopyalar.

UI değişiklikleri diff olarak göstermeli:

```text
EXP-117 cloned from EXP-104

Changed:
optimizer:
  genetic → bayesian

population:
  100 → 200
```

---

# 21. Experiment Registry

Kalıcı experiment ekranı.

Filtreler:

- Market
- Symbol
- Timeframe
- Date
- Status
- Model
- Optimizer
- Tag
- Owner
- Min Sharpe
- Max Drawdown

Liste kolonları:

```text
Experiment ID
Name
Market
Model
Optimizer
Sharpe
Return
Max DD
Created
Status
```

---

# 22. Experiment Comparison

Kullanıcı 2+ experiment seçip karşılaştırabilmeli.

Örnek tablo:

| Metric | EXP-184 | EXP-191 | EXP-207 |
|---|---:|---:|---:|
| Model | XGB | TFT | STACK |
| Feature Count | 18 | 31 | 24 |
| Sharpe | 1.42 | 1.67 | 1.91 |
| Return | 12.3% | 15.1% | 18.6% |
| Max Drawdown | -7.2% | -8.4% | -5.9% |
| Sortino | 1.76 | 1.94 | 2.32 |
| Trades | 341 | 287 | 319 |
| Win Rate | 54% | 56% | 59% |

Aynı ekranda:

- Equity curves overlay
- Drawdown curves
- Rolling Sharpe
- Regime performance
- Feature differences
- Model parameter differences
- Validation vs test degradation

---

# 23. Champion / Challenger

Her market/timeframe için bir champion tanımlanabilir.

```text
EUR/USD 4H

CHAMPION
EXP-207
Sharpe: 1.91
Return: 18.6%
Max DD: -5.9%
```

Challenger listesi tutulmalı.

Yeni deney otomatik production champion yapılmamalı.

İki aşama:

```text
Candidate
   ↓
Promote Proposal
   ↓
Human Approval
   ↓
Champion
```

---

# 24. Feature Survival Rate

GA için özel analiz ekranı.

Başarılı chromosome'larda feature'ın yaşama oranı hesaplanmalı.

Örnek:

```text
DXY Momentum       92%
US10Y Spread       84%
ATR 20             76%
VIX                63%
RSI                48%
MACD               19%
```

Ek metrikler:

- Average fitness when present
- Average fitness when absent
- Selection frequency
- Top-generation survival

---

# 25. Optimization Lab UI

Yeni ana ekranlardan biri:

**Optimization Lab**

Canlı görüntülenecek:

```text
Optimizer: Genetic Algorithm
Generation: 37 / 100
Population: 100
Evaluated Candidates: 3700
Best Validation Sharpe: 2.17
Average Sharpe: 1.23
Population Diversity: 73%
Elapsed: 18m 42s
ETA: 31m
```

Grafikler:

- Best fitness by generation
- Mean fitness by generation
- Sharpe by generation
- Population diversity
- Pareto frontier
- Feature survival

Sağ panel:

```text
Current Best Chromosome
Model
Feature count
Hyperparameters
Sharpe
Return
Drawdown
```

---

# 26. Yeni Deney Wizard

Mevcut "Yeni deney" butonu wizard açmalı.

Adımlar:

```text
1. Data
2. Features
3. Models
4. Optimization
5. Validation
6. Backtest / Risk
7. Review
8. Run
```

## 26.1 Data

- Market
- Symbol
- Timeframe
- Dataset snapshot
- Date range
- Additional datasets

## 26.2 Features

- Feature groups
- Manual features
- Auto selection mode

## 26.3 Models

Multi-select.

## 26.4 Optimization

```text
None
Grid Search
Random Search
Optuna / Bayesian
Genetic Algorithm
```

## 26.5 Validation

- Walk forward
- Holdout
- Windows

## 26.6 Risk / Backtest

- Transaction cost
- Slippage
- Stop rules
- Position sizing
- Max exposure

---

# 27. Experiment Detail UI

Ana experiment ekranında tabs:

```text
Overview
Equity
Trades
Features
Models
Optimization
Regimes
Validation
Explainability
Artifacts
Logs
```

Overview üst metric kartları:

```text
Return
Sharpe
Max Drawdown
Sortino
```

Ayrıca:

```text
Validation Sharpe
Test Sharpe
Validation → Test Degradation
```

---

# 28. Run Log / Timeline

Mevcut "Çalıştırma günlüğü" geliştirilmeli.

Örnek:

```text
17:42:01 Dataset snapshot loaded
17:42:05 184 candidate features found
17:42:11 27 unstable features removed
17:42:13 Genetic optimization started
17:43:07 Generation 10/100 - Best Sharpe 1.42
17:44:31 Generation 25/100 - Best Sharpe 1.61
17:47:54 Generation 61/100 - Best Sharpe 1.89
17:51:22 Genetic search completed
17:51:26 Top 5 candidates selected
17:51:31 Locked test started
17:52:05 Test completed
17:52:07 Robustness analysis completed
```

Canlı update SSE/WebSocket ile yapılmalı.

---

# 29. AI-Native Kullanım

Sisteme AI agent entegrasyonu first-class feature olmalı.

Kullanıcı natural language yazabilmeli:

> EURUSD 4H için macro + technical feature'larla XGBoost, LightGBM ve TFT dene. Genetic algorithm ile feature selection yap. Validation Sharpe'ı maksimum yap ama drawdown %10'u geçmesin.

AI doğrudan Python kodu üretip çalıştırmamalı.

AI önce **Experiment Specification** üretmeli.

---

# 30. Experiment Specification DSL

Tüm experiment tanımları tek standardize schema ile temsil edilmeli.

Örnek YAML:

```yaml
experiment:
  name: EURUSD GA Research
  market: FX
  symbol: EURUSD
  timeframe: 4H

dataset:
  version: latest

features:
  groups:
    - technical
    - macro
    - cross_asset

models:
  - xgboost
  - lightgbm
  - tft

optimization:
  algorithm: genetic
  population: 150
  generations: 100
  genome:
    feature_selection: true
    hyperparameters: true
    ensemble_weights: false

objective:
  type: multi_objective
  maximize:
    - sharpe
    - return
  minimize:
    - max_drawdown
    - turnover

constraints:
  max_drawdown: 0.10

validation:
  method: walk_forward

test:
  locked: true

backtest:
  transaction_cost_enabled: true
  slippage_enabled: true
```

Bu schema:

- API
- UI
- MCP
- AI agent
- DB

arasında ortak contract olarak kullanılmalıdır.

---

# 31. AI Agent Workflow

```text
User Prompt
    ↓
AI Agent
    ↓
Generate Experiment Specification
    ↓
Schema Validation
    ↓
Policy Validation
    ↓
Cost Estimation
    ↓
User Approval (gerekiyorsa)
    ↓
Create Experiment
    ↓
Run Experiment
    ↓
Monitor Job
    ↓
Analyze Results
    ↓
Create Child Experiment if needed
    ↓
Compare Experiments
    ↓
Final Research Summary
```

---

# 32. Agent Güvenlik Prensibi

AI agent'a doğrudan aşağıdaki gibi tool verilmemeli:

```text
execute_python
execute_shell
execute_sql
```

Ana kullanımda domain-level tools verilmeli:

```text
create_experiment
run_experiment
get_experiment
compare_experiments
```

Bu sayede:

- Güvenlik
- Reproducibility
- Auditability
- Cost control

sağlanır.

---

# 33. REST API

Versioned API:

```text
/api/v1/
```

## 33.1 Experiment endpoints

```http
POST   /api/v1/experiments
GET    /api/v1/experiments
GET    /api/v1/experiments/{id}
PATCH  /api/v1/experiments/{id}
POST   /api/v1/experiments/{id}/clone
POST   /api/v1/experiments/{id}/run
POST   /api/v1/experiments/{id}/cancel
GET    /api/v1/experiments/{id}/status
GET    /api/v1/experiments/{id}/metrics
GET    /api/v1/experiments/{id}/logs
GET    /api/v1/experiments/{id}/artifacts
```

## 33.2 Comparison

```http
POST /api/v1/experiments/compare
```

## 33.3 Dataset

```http
GET  /api/v1/datasets
GET  /api/v1/datasets/{id}
POST /api/v1/datasets/snapshots
```

## 33.4 Features

```http
GET /api/v1/features
GET /api/v1/feature-sets
GET /api/v1/experiments/{id}/feature-analysis
```

## 33.5 Optimization

```http
GET /api/v1/experiments/{id}/optimization
GET /api/v1/experiments/{id}/candidates
GET /api/v1/experiments/{id}/pareto
```

## 33.6 Backtest

```http
GET /api/v1/experiments/{id}/backtest
GET /api/v1/experiments/{id}/trades
GET /api/v1/experiments/{id}/equity
```

## 33.7 Champion

```http
GET  /api/v1/champions
POST /api/v1/champions/propose
POST /api/v1/champions/{id}/approve
```

---

# 34. REST Create Experiment Örneği

```json
{
  "name": "EURUSD GA Research 001",
  "market": "FX",
  "symbol": "EURUSD",
  "timeframe": "4H",
  "dataset": {
    "from": "2020-01-01",
    "to": "2026-08-31"
  },
  "features": {
    "groups": [
      "technical",
      "macro",
      "cross_asset",
      "volatility"
    ]
  },
  "models": [
    "xgboost",
    "lightgbm",
    "tft"
  ],
  "optimization": {
    "algorithm": "genetic",
    "population": 100,
    "generations": 80
  },
  "objective": {
    "maximize": [
      "sharpe",
      "return"
    ],
    "constraints": {
      "max_drawdown": 0.08
    }
  },
  "validation": {
    "method": "walk_forward"
  },
  "test": {
    "locked": true
  }
}
```

Response:

```json
{
  "experiment_id": "EXP-2026-002183",
  "status": "draft"
}
```

---

# 35. Async Job Architecture

Training / GA / backtest HTTP request içerisinde synchronous çalıştırılmamalı.

```text
POST /run
   ↓
Job created
   ↓
202 Accepted
   ↓
experiment_id + job_id
```

Örnek response:

```json
{
  "experiment_id": "EXP-2026-002183",
  "job_id": "JOB-84920",
  "status": "queued"
}
```

Job state DB + Redis'te tutulmalı.

---

# 36. SSE / WebSocket

Frontend için canlı event stream.

Örnek eventler:

```text
experiment.status.changed
experiment.log.appended
optimization.generation.completed
optimization.best_candidate.changed
training.model.completed
backtest.completed
experiment.completed
experiment.failed
```

Örnek payload:

```json
{
  "type": "optimization.generation.completed",
  "experiment_id": "EXP-219",
  "generation": 37,
  "total_generations": 100,
  "best_sharpe": 2.17,
  "mean_sharpe": 1.23,
  "population_diversity": 0.73
}
```

---

# 37. MCP Desteği

MCP server, RegimeLab domain servislerine adapter olmalıdır.

**MCP içerisinde duplicate business logic yazma.**

```text
MCP Tool
   ↓
Application Service
   ↓
Domain / Orchestrator
   ↓
DB / Worker
```

---

# 38. İlk MCP Tool Set

İlk sürümde aşağıdaki tools yeterlidir:

```text
search_datasets
inspect_dataset
list_features
search_features
create_experiment
clone_experiment
run_experiment
cancel_experiment
get_experiment_status
get_experiment
list_experiments
compare_experiments
get_optimization_result
get_best_candidates
get_feature_analysis
get_backtest_results
get_regime_analysis
get_artifacts
propose_champion
```

Agent'a doğrudan production promotion verilmemesi önerilir.

---

# 39. MCP Tool — create_experiment

Input schema, REST Experiment Specification ile aynı olmalı.

Örnek:

```json
{
  "name": "EURUSD GA Agent Research",
  "symbol": "EURUSD",
  "timeframe": "4H",
  "feature_groups": ["technical", "macro"],
  "models": ["xgboost", "tft"],
  "optimizer": "genetic",
  "objective": ["sharpe", "return"],
  "max_drawdown": 0.10
}
```

---

# 40. MCP Tool — compare_experiments

Input:

```json
{
  "experiment_ids": [
    "EXP-201",
    "EXP-207",
    "EXP-219"
  ],
  "metrics": [
    "sharpe",
    "return",
    "max_drawdown",
    "sortino"
  ]
}
```

Output structured JSON olmalı.

---

# 41. MCP Resources

Agent'ın readonly veri keşfi için resources sunulabilir.

Örnek resource URI'lar:

```text
regimelab://experiments/EXP-219
regimelab://datasets/EURUSD-4H-v18
regimelab://features/FX-MACRO-v12
regimelab://models/XGB-482
regimelab://backtests/BT-927
regimelab://strategies/STRAT-102
```

---

# 42. MCP ve Long Running Tasks

Uzun işlerde tool çağrısı sonucu hemen final result dönmemeli.

```text
run_experiment
    ↓
TASK / JOB ID
    ↓
queued
    ↓
running
    ↓
completed
```

MCP client job status sorgulayabilmeli.

REST ile MCP aynı Job Service'i kullanmalı.

---

# 43. Agent Activity UI

Web arayüzüne yeni panel:

**AI Research Agent**

Gösterilecekler:

- Agent name
- Current action
- Tool name
- Experiment ID
- Reason/summary (kısa)
- Tool status
- Timestamp

Örnek:

```text
AI Research Agent

17:42 Dataset inspected
17:43 Created EXP-487
17:43 Started GA optimization
17:51 Validation completed
17:52 Locked test completed
17:53 EXP-488 created from EXP-487
17:53 Reduced feature count 48 → 20
```

Agent'ın private chain-of-thought'u gösterilmemeli. Sadece action summary / auditable decision summary gösterilmeli.

---

# 44. Multi-Agent Gelecek Tasarımı

İlk sürümde zorunlu değil; mimari hazır olmalı.

```text
Quant Orchestrator Agent
│
├── Data Agent
├── Feature Agent
├── Model Agent
├── Optimization Agent
├── Backtest Agent
├── Risk Agent
└── Reviewer Agent
```

## Data Agent
- Data quality
- Leakage
- Point-in-time checks

## Feature Agent
- Feature generation
- Stability
- Redundancy

## Model Agent
- Model selection
- Hyperparameter search

## Optimization Agent
- GA
- Optuna
- Pareto

## Backtest Agent
- Costs
- Slippage
- Walk-forward

## Risk Agent
- Drawdown
- Exposure
- Regime sensitivity

## Reviewer Agent
- Validation/test degradation
- Overfitting warnings
- Robustness summary

---

# 45. Agent Policy / Compute Limits

Agent sınırsız computation başlatamamalı.

Policy config:

```text
max_population
max_generations
max_models
max_candidates
max_training_minutes
max_cpu_hours
max_gpu_hours
max_parallel_jobs
```

Örnek policy reject:

```json
{
  "status": "policy_rejected",
  "reason": "Estimated compute exceeds tenant limit",
  "estimated_gpu_hours": 49.2,
  "allowed_gpu_hours": 20
}
```

---

# 46. Authentication / Authorization

API ve MCP ortak identity sistemi kullanmalı.

Destek:

- User auth
- API key
- Service account
- OAuth-compatible agent auth

Scope örnekleri:

```text
experiment:read
experiment:create
experiment:run
experiment:cancel

dataset:read
feature:read

model:read
model:train

artifact:read

champion:propose
champion:approve
```

Tenant isolation baştan düşünülmeli.

---

# 47. Audit Log

Önemli her action kaydedilmeli.

```text
actor_type
actor_id
source
operation
entity_type
entity_id
request_id
before
change
after
timestamp
```

Actor type:

```text
USER
AI_AGENT
API_CLIENT
SYSTEM
```

---

# 48. Database Entity Taslağı

Ana tablolar:

```text
users
tenants
api_keys

experiments
experiment_runs
experiment_events
experiment_tags

datasets
dataset_snapshots

features
feature_sets
feature_set_items

models
model_versions
model_runs

optimization_runs
optimization_generations
optimization_candidates
chromosomes

backtests
backtest_trades
backtest_equity

metrics
artifacts

regime_runs
regime_metrics

champions
champion_proposals

audit_logs
jobs
```

---

# 49. experiments Tablosu Örnek Alanlar

```text
id UUID
experiment_code VARCHAR UNIQUE
parent_experiment_id UUID NULL
name VARCHAR
description TEXT
market VARCHAR
symbol VARCHAR
timeframe VARCHAR
status VARCHAR
specification JSONB
dataset_snapshot_id UUID
created_by UUID
created_at TIMESTAMP
updated_at TIMESTAMP
```

---

# 50. experiment_runs

```text
id
experiment_id
run_number
status
started_at
completed_at
random_seed
code_version
git_commit
worker_id
runtime_metadata JSONB
error_message
```

---

# 51. metrics

Generic metric table veya JSONB + indexed core metrics kullanılabilir.

Core fields ayrıca experiment summary içinde indexed tutulmalı:

```text
train_sharpe
validation_sharpe
test_sharpe
return_pct
max_drawdown
sortino
calmar
win_rate
turnover
trade_count
```

---

# 52. Artifacts

Her experiment aşağıdaki artifact'ları üretebilir:

- Model binary
- Feature list
- Config JSON/YAML
- Equity curve data
- Drawdown series
- Trade log
- Optimization history
- Pareto candidate data
- Feature importance
- Feature survival
- Report HTML/PDF later

DB sadece metadata/path tutmalı. Büyük binary DB'ye gömülmemeli.

---

# 53. Cache / Idempotency

Experiment run çağrıları idempotent hale getirilmeli.

Özellikle AI agent aynı tool'u tekrar çağırabilir.

Kullanılabilecek alan:

```text
idempotency_key
```

Aynı key ile duplicate run oluşturma.

---

# 54. Observability

Her request / experiment / job için correlation ID olmalı.

Log fields:

```text
request_id
experiment_id
job_id
agent_id
user_id
worker_id
```

Metrics:

- Job queue length
- Running jobs
- Failed jobs
- Experiment duration
- Optimization candidate/sec
- CPU/GPU utilization
- API latency
- Error rate

---

# 55. Existing Dashboard Güncellemesi

Mevcut ana dashboard korunmalı ancak üst kısım experiment-aware olmalı.

Örnek:

```text
EUR/USD                    EXP-207
Stacked GA Strategy

TEST RESULT

Return       Sharpe       Max DD       Sortino
+18.6%       1.91         -5.9%        2.27
```

Sekmeler:

```text
Overview
Equity
Trades
Features
Models
Optimization
Regimes
Validation
Explainability
Artifacts
```

---

# 56. Sol Menü Önerisi

```text
Genel Bakış

Araştırma
  Yeni Deney
  Deneyler
  Karşılaştırma
  Optimization Lab

Veri Merkezi
Feature Lab
Model Lab
Piyasa Rejimleri
Champion / Challenger

AI Research Agent

MCP / API

Metodoloji
Ayarlar
```

---

# 57. AI Prompt Box

Ana sayfaya doğal dil experiment builder eklenebilir.

Placeholder:

```text
Nasıl bir araştırma yapmak istiyorsun?

Örn: EURUSD 4H için XGBoost ve TFT dene, technical + macro feature kullan,
GA ile feature selection yap, validation Sharpe maksimize et ve drawdown %8'i geçmesin.
```

Button:

```text
AI ile deney oluştur
```

AI direkt çalıştırmadan önce generated spec'i kullanıcıya göstermeli.

---

# 58. Generated Experiment Review

AI prompt sonrası:

```text
AI Generated Experiment

Market: EUR/USD
Timeframe: 4H
Models: XGBoost, TFT
Features: Technical, Macro
Optimizer: Genetic Algorithm
Population: 100
Generations: 80
Objective: Max Sharpe + Return
Constraint: Max DD <= 8%
Validation: Walk Forward
Test: Locked

[Edit] [Create Experiment]
```

---

# 59. Robustness / Overfitting Kontrolü

Sistem final result'ta sadece yüksek Sharpe göstermemeli.

Kontroller:

- Train vs validation gap
- Validation vs test gap
- Rolling Sharpe stability
- Parameter sensitivity
- Feature stability
- Performance by regime
- Turnover / cost sensitivity
- Number of trades

Örnek warning:

```text
OVERFITTING WARNING

Validation Sharpe: 2.31
Test Sharpe: 0.88
Degradation: -61.9%

Potential causes:
- Excessive feature count
- Parameter over-optimization
- Low trade count
```

---

# 60. Research Agent Auto-Iteration

Agent isterse sonuçlara göre child experiment önerebilir / oluşturabilir.

Örnek:

```text
EXP-487
Validation Sharpe: 1.38
Test Sharpe: 0.72
```

Agent summary:

```text
High validation-to-test degradation detected.
```

Olası child experiment'lar:

```text
EXP-488
Feature count 48 → 20

EXP-489
Stronger regularization

EXP-490
Walk-forward window changed
```

Bu davranış policy ile açılıp kapatılabilir.

---

# 61. İlk Release İçin Önceliklendirme

## Phase 1 — Foundation

Zorunlu:

- Experiment entity
- Experiment Registry
- Dataset snapshot
- API-first backend
- Async job runner
- Run status/logs
- Existing dashboard → experiment detail
- Experiment persistence

## Phase 2 — Research Engine

- Feature registry
- Multi-model support
- Genetic feature selection
- Hyperparameter optimization
- Validation
- Locked test
- Backtest metrics

## Phase 3 — Comparison

- Experiment comparison
- Equity overlay
- Parameter diff
- Feature diff
- Experiment clone
- Experiment lineage

## Phase 4 — Advanced Optimization

- GA full genome
- Optuna
- Multi-objective
- Pareto frontier
- Feature survival
- Ensemble / stacking

## Phase 5 — AI / MCP

- Experiment Specification DSL
- AI prompt → experiment spec
- REST tool contracts
- MCP Server
- MCP tools
- MCP resources
- Agent activity log
- Compute policy

## Phase 6 — Advanced Agentic Research

- Auto child experiments
- Reviewer agent
- Multi-agent architecture
- Champion/challenger workflow

---

# 62. Minimum Viable Product — Tavsiye

İlk MVP'de aşağıdaki kombinasyon yeterlidir:

```text
EURUSD
4H

Models:
XGBoost
LightGBM

Features:
Technical
Macro

Optimizer:
Genetic Algorithm

Genome:
Feature Selection
Hyperparameters

Validation:
Walk Forward

Metrics:
Sharpe
Return
Max Drawdown
Sortino

Persistence:
Experiment Registry

Comparison:
2-5 experiment

External Interface:
REST API
MCP
```

TFT/HMM/stacking sonraki iteration'da eklenebilir ancak adapter yapısı ilk günden hazırlanmalı.

---

# 63. Acceptance Criteria — Experiment

Bir feature tamamlandı sayılabilmesi için:

1. Kullanıcı yeni experiment oluşturabiliyor.
2. Experiment DB'ye kaydediliyor.
3. Unique experiment code alıyor.
4. Run async başlıyor.
5. UI canlı progress gösteriyor.
6. Çalışma bitince metrics kaydediliyor.
7. Sayfa yenilense bile experiment kaybolmuyor.
8. Experiment daha sonra açılabiliyor.
9. Clone edilebiliyor.
10. Başka experiment ile karşılaştırılabiliyor.

---

# 64. Acceptance Criteria — Genetic Algorithm

1. Feature pool seçilebiliyor.
2. Population ve generation config edilebiliyor.
3. GA validation data üzerinde optimize ediyor.
4. Locked test optimizer tarafından görülmüyor.
5. Her generation sonucu kaydediliyor.
6. Best candidate kaydediliyor.
7. Feature survival hesaplanıyor.
8. Final candidate locked test'e uygulanıyor.
9. Test metrics experiment altında saklanıyor.
10. Aynı seed/config ile reproducibility hedefleniyor.

---

# 65. Acceptance Criteria — Experiment Comparison

1. Kullanıcı minimum 2 experiment seçebiliyor.
2. En az 5 experiment aynı anda karşılaştırılabiliyor.
3. Sharpe/Return/MaxDD/Sortino görülebiliyor.
4. Equity curves overlay ediliyor.
5. Config differences görülebiliyor.
6. Feature differences görülebiliyor.
7. Validation/test degradation karşılaştırılıyor.

---

# 66. Acceptance Criteria — REST API

1. UI tüm experiment işlemlerini API üzerinden yapıyor.
2. API versioned.
3. Async job endpoints mevcut.
4. Idempotency destekleniyor.
5. Validation errors structured JSON.
6. Auth uygulanabilir halde.
7. OpenAPI schema otomatik üretilebiliyor.

---

# 67. Acceptance Criteria — MCP

1. MCP server ayrı adapter modülü olarak çalışıyor.
2. Core business logic MCP'ye duplicate edilmiyor.
3. Agent experiment oluşturabiliyor.
4. Experiment run başlatabiliyor.
5. Status alabiliyor.
6. Result okuyabiliyor.
7. Experiment karşılaştırabiliyor.
8. Feature/backtest/regime sonuçlarını okuyabiliyor.
9. Agent'ın raw Python/SQL execution tool'u yok.
10. Audit log'da MCP/agent source görülebiliyor.

---

# 68. Kod Organizasyonu Önerisi

Örnek backend dizini:

```text
backend/
├── api/
│   └── v1/
├── domain/
│   ├── experiments/
│   ├── datasets/
│   ├── features/
│   ├── models/
│   ├── optimization/
│   ├── validation/
│   ├── backtesting/
│   └── regimes/
├── application/
│   ├── experiment_service.py
│   ├── optimization_service.py
│   └── comparison_service.py
├── infrastructure/
│   ├── db/
│   ├── redis/
│   ├── jobs/
│   └── storage/
├── workers/
├── mcp/
│   ├── server.py
│   ├── tools/
│   └── resources/
├── agents/
│   ├── experiment_spec_agent.py
│   └── reviewer_agent.py
└── tests/
```

Frontend:

```text
frontend/
├── app/
├── components/
├── features/
│   ├── experiments/
│   ├── optimization/
│   ├── comparison/
│   ├── datasets/
│   ├── models/
│   ├── regimes/
│   └── agent/
├── services/
└── types/
```

---

# 69. Temel Domain Interfaces

Optimizer adapter:

```python
class OptimizerAdapter:
    def optimize(self, experiment_context): ...
    def get_progress(self): ...
    def get_best_candidates(self): ...
```

Model adapter:

```python
class ModelAdapter:
    def fit(self, X, y): ...
    def predict(self, X): ...
    def get_params(self): ...
```

Feature selector:

```python
class FeatureSelector:
    def select(self, X, y, context): ...
```

Validator:

```python
class ValidationStrategy:
    def split(self, dataset): ...
    def evaluate(self, candidate): ...
```

Backtester:

```python
class BacktestEngine:
    def run(self, signals, market_data, config): ...
```

---

# 70. Kritik Finansal Araştırma Kuralları

Astra implementasyonunda aşağıdaki kuralları ihlal etme:

1. Random shuffle time-series validation default olmasın.
2. Test set optimizer'a verilmesin.
3. Transaction cost dahil edilebilsin.
4. Slippage dahil edilebilsin.
5. Look-ahead leakage kontrolü olsun.
6. Data snapshot/version kaydedilsin.
7. Seed kaydedilsin.
8. Feature computation sadece geçmiş bilgi kullanmalı.
9. Final result train metric'ten ibaret olmasın.
10. Validation ve test ayrı raporlansın.

---

# 71. Kullanıcı Deneyimi Hedefi

Kullanıcı uygulamaya girdiğinde şu döngüyü 2-3 dakikada anlayabilmeli:

```text
Yeni deney oluştur
      ↓
Veri seç
      ↓
Feature seç
      ↓
Model seç
      ↓
Optimizer seç
      ↓
Deneyi çalıştır
      ↓
Canlı ilerlemeyi izle
      ↓
Sonucu incele
      ↓
Eski deney ile karşılaştır
      ↓
Clone ederek yeni varyasyon dene
```

AI kullanıldığında:

```text
Prompt yaz
      ↓
AI experiment spec oluştursun
      ↓
Kullanıcı gözden geçirsin
      ↓
Run
      ↓
AI sonucu yorumlasın
      ↓
Gerekirse child experiment önersin
```

---

# 72. Astra İçin Uygulama Sırası

Bu sırayla ilerle:

### Step 1
Mevcut kod tabanını analiz et. Var olan sayfaları, routing'i, state management'i, backend servislerini ve DB yapısını tespit et.

### Step 2
Experiment domain modelini ve DB migration'larını ekle.

### Step 3
Experiment REST API'lerini oluştur.

### Step 4
Async job altyapısını ekle.

### Step 5
Mevcut deney çalıştırma akışını Experiment Orchestrator arkasına taşı.

### Step 6
Experiment History/Registry ekranını gerçek DB datasına bağla.

### Step 7
Experiment Detail ve live logs/progress ekranını tamamla.

### Step 8
Clone + Compare özelliklerini ekle.

### Step 9
Feature Registry ve Model Adapter mimarisini ekle.

### Step 10
Genetic Algorithm optimizer'ı ekle.

### Step 11
Walk-forward validation + locked test kuralını uygula.

### Step 12
Optimization Lab ekranını ekle.

### Step 13
Feature survival + Pareto analizlerini ekle.

### Step 14
Experiment Specification schema'sını standardize et.

### Step 15
AI prompt → experiment specification akışını ekle.

### Step 16
MCP server ve tool/resource adapter'larını ekle.

### Step 17
Agent audit / activity log ekle.

### Step 18
Champion/challenger altyapısını ekle.

---

# 73. Astra İçin “Definition of Done”

Proje aşağıdaki noktaya geldiğinde ilk büyük sürüm tamamlanmış sayılmalı:

- Mevcut dark RegimeLab UI korunmuş.
- Yeni experiment wizard çalışıyor.
- Experiment DB'de kalıcı.
- Sayfa yenilendiğinde geçmiş kaybolmuyor.
- Experiment clone edilebiliyor.
- En az 2-5 experiment karşılaştırılabiliyor.
- Multi-model seçim var.
- Genetic Algorithm feature selection çalışıyor.
- Validation Sharpe optimizer metric'i olabiliyor.
- Return ve drawdown beraber raporlanıyor.
- Locked test kuralı uygulanıyor.
- Canlı optimization progress var.
- Feature survival görülebiliyor.
- REST API tam çalışıyor.
- MCP server aynı domain servislerini kullanıyor.
- AI agent MCP ile experiment oluşturup run edebiliyor.
- AI agent sonucu ve karşılaştırmayı okuyabiliyor.
- Raw Python / SQL execution zorunlu değil ve varsayılan olarak kapalı.
- Audit log mevcut.
- Compute policy mevcut.
- OpenAPI ve temel backend testleri mevcut.

---

# 74. Son Ürün Tanımı

RegimeLab'ın hedefi:

> **Kullanıcının veya bir AI agent'ın finansal dataset üzerinde feature engineering, model seçimi, genetic / Bayesian optimization, walk-forward validation, locked test ve backtest süreçlerini reproducible experiment'lar halinde çalıştırabildiği; sonuçları Sharpe, Return ve Drawdown başta olmak üzere risk-adjusted metriklerle karşılaştırabildiği; deney lineage, champion/challenger, REST API ve MCP desteği sunan AI-native quantitative research platformu.**

Sistem tasarlanırken UI sadece istemci olarak düşünülmeli. Research Engine, Experiment Registry, API ve MCP katmanları bağımsız ve yeniden kullanılabilir olmalı.

---

# 75. Astra'ya Verilecek Kısa Çalışma Prompt'u

Aşağıdaki cümleyi bu dokümanla birlikte Astra'ya ver:

> Mevcut RegimeLab kod tabanını incele ve bu dokümandaki gereksinimleri mevcut sistemi bozmadan iteratif biçimde uygula. Önce mevcut mimariyi analiz edip uygulanacak değişiklik planını çıkar. Ardından Phase 1'den başlayarak production-quality kod yaz. UI içine business logic koyma; API-first ve experiment-centric ilerle. Tüm long-running ML/GA/backtest işlemlerini async job olarak çalıştır. Test dataset'ini optimizer'dan kesin olarak izole et. Experiment Specification'ı UI, REST API, AI Agent ve MCP arasında ortak contract olarak kullan. MCP katmanında business logic duplicate etme. Her büyük adımda migration, API contract, test ve UI entegrasyonunu birlikte tamamla.

