# RegimeLab — Notebook Lab Integration Work Plan

## 0. Amaç

Bu planın amacı, mevcut ve yeni `.ipynb` araştırma notebook'larını RegimeLab içinde güvenli, tekrar üretilebilir, workspace-aware ve experiment-aware biçimde çalıştırabilen bir **Notebook Lab** katmanı oluşturmaktır.

Notebook Lab, production Research Engine'in alternatifi olmayacaktır. Notebook'lar:

- araştırma/prototipleme,
- yeni feature/model/optimizer fikirlerini deneme,
- tez/araştırma kodunu RegimeLab içine taşıma,
- bir Experiment'e bağlı analiz üretme,
- artifact/metric/log kaydetme

amaçlarıyla kullanılacaktır.

Temel prensip:

```text
Notebook = Research Client
RegimeLab Core = Source of Truth
```

Notebook'lar mümkün olduğunca RegimeLab core servislerini kullanmalı; production business logic zamanla notebook içinden core modüllere çıkarılmalıdır.

---

# 1. Mevcut Notebook'tan Çıkan Gereksinimler

Mevcut `tezmodelfinal (1).ipynb`:

- Dukascopy FX verisi çekiyor.
- `pandas`, `numpy`, `yfinance`, `pandas_datareader` kullanıyor.
- FX / macro serileri için timezone temizliği ve 4H alignment yapıyor.
- Feature engineering fonksiyonları içeriyor.
- HMM bağımlılığı kullanıyor.
- Optuna bağımlılığı kullanıyor.
- Çok sayıda model/feature-set sonucunu klasörlere ve CSV'lere kaydediyor.
- Notebook içinde `pip install` çalıştırıyor.
- FRED API anahtarını notebook içinde hard-code ediyor.

Bu nedenle Notebook Lab sadece "ipynb upload + execute" olmamalı; environment, secret, dataset, artifact ve job lifecycle yönetimi içermelidir.

---

# 2. Hedef Kullanıcı Akışı

```text
Workspace seç
   ↓
Notebook Lab
   ↓
Notebook yükle / mevcut notebook seç
   ↓
Environment seç
   ↓
Dataset Snapshot seç
   ↓
Experiment seç veya yeni Experiment oluştur
   ↓
Parametreleri gözden geçir
   ↓
Run
   ↓
Async Notebook Job
   ↓
Canlı log / cell progress
   ↓
Metrics + Artifacts + Executed Notebook
   ↓
Experiment Registry'ye bağla
```

Örnek:

```text
Workspace:
FX Research

Notebook:
EURUSD_GA_AUTOML.ipynb

Dataset:
EURUSD_4H_20260905_v32

Experiment:
EXP-207

Environment:
regimelab-quant:1.0

Status:
READY

[ Run Notebook ]
```

---

# 3. Scope

## V1 — Zorunlu

- Notebook registry
- `.ipynb` upload/import
- Workspace binding
- Experiment binding
- Dataset Snapshot binding
- Parameterized execution
- Async notebook worker
- Executed notebook artifact
- stdout/stderr log
- Artifact collection
- Metric logging
- Notebook environment definition
- Secret injection
- Timeout / cancellation
- Run history
- REST API
- MCP read/run tools
- Audit log
- Workspace isolation

## V2 — Sonraki faz

- JupyterLab-like interactive editing
- Scheduled notebook runs
- GPU environment selection
- Notebook version diff
- Notebook template marketplace
- Collaborative editing
- Notebook → production module promotion workflow
- Remote kernels
- distributed notebook workers

---

# 4. Mimari

```text
                    REGIMELAB

        ┌───────────────────────────┐
        │         CLIENTS           │
        │                           │
        │ Web UI   AI Agent   MCP   │
        └─────────────┬─────────────┘
                      │
                      ▼
            Notebook Application API
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
     Registry     Run Service   Policy
          │           │
          │           ▼
          │     Async Job Queue
          │           │
          │           ▼
          │    Notebook Worker
          │      (isolated)
          │           │
          │     papermill/nbclient
          │           │
          ▼           ▼
      PostgreSQL   Artifact Store
                       │
                       ├── executed.ipynb
                       ├── metrics.json
                       ├── logs.txt
                       ├── csv/parquet
                       ├── png/html
                       └── model artifacts
```

---

# 5. Notebook Runner Teknolojisi

Önerilen öncelik:

```text
1. Papermill
2. nbclient
3. nbconvert
```

### Papermill

Parameterized notebook execution için kullanılabilir.

### nbclient

Notebook cell execution lifecycle üzerinde daha fazla kontrol gerektiğinde kullanılabilir.

### nbconvert

Executed notebook'u HTML/PDF gibi formatlara dönüştürmek için opsiyonel kullanılabilir.

V1'de:

```text
Papermill + nbclient
```

yeterlidir.

---

# 6. Notebook Domain Entity

Tablo:

```text
notebooks
```

Alanlar:

```text
id UUID
notebook_code VARCHAR UNIQUE

workspace_id UUID
name VARCHAR
description TEXT

source_filename VARCHAR
storage_path VARCHAR
content_hash VARCHAR

version INT
status VARCHAR

default_environment_id UUID NULL

created_by UUID
created_at TIMESTAMP
updated_at TIMESTAMP
archived_at TIMESTAMP NULL
```

Status:

```text
ACTIVE
ARCHIVED
INVALID
```

---

# 7. Notebook Versions

Notebook içeriği değiştirildiğinde eski çalışma geçmişi bozulmamalıdır.

Tablo:

```text
notebook_versions
```

Alanlar:

```text
id
notebook_id
version
content_hash
storage_path
created_by
created_at
change_summary
```

Bir NotebookRun mutlaka:

```text
notebook_version_id
```

ile çalışmalıdır.

---

# 8. Notebook Run Entity

Tablo:

```text
notebook_runs
```

Alanlar:

```text
id UUID
run_code VARCHAR UNIQUE

workspace_id UUID
notebook_id UUID
notebook_version_id UUID

experiment_id UUID NULL
dataset_snapshot_id UUID NULL
environment_id UUID

status VARCHAR

parameters JSONB
runtime_metadata JSONB

job_id UUID

started_at
completed_at
duration_seconds

exit_code
error_type
error_message

executed_notebook_artifact_id UUID NULL

created_by
created_at
```

Status:

```text
DRAFT
QUEUED
PREPARING
RUNNING
COLLECTING_ARTIFACTS
COMPLETED
FAILED
CANCELLED
TIMEOUT
POLICY_REJECTED
```

---

# 9. Notebook Parameters Contract

Her RegimeLab-compatible notebook'un ilk bölümlerinden biri standart parameter cell olmalıdır.

Örnek:

```python
# REGIMELAB_PARAMETERS

WORKSPACE_ID = None
EXPERIMENT_ID = None
DATASET_SNAPSHOT_ID = None

SYMBOL = "EURUSD"
TIMEFRAME = "4H"

RANDOM_SEED = 42

INPUT_DIR = None
ARTIFACT_DIR = None
```

Papermill tag:

```text
parameters
```

olmalıdır.

RegimeLab run sırasında inject eder:

```python
WORKSPACE_ID = "WS-FX-001"
EXPERIMENT_ID = "EXP-207"
DATASET_SNAPSHOT_ID = "DS-991"

SYMBOL = "EURUSD"
TIMEFRAME = "4H"

RANDOM_SEED = 42

INPUT_DIR = "/runtime/input"
ARTIFACT_DIR = "/runtime/artifacts"
```

---

# 10. Dataset Kullanım Modları

## Mode A — Snapshot Mode

Production'a en yakın ve default mode.

```text
RegimeLab Data Hub
      ↓
Dataset Snapshot
      ↓
Notebook
```

Notebook internetten tekrar veri çekmez.

Avantaj:

- reproducibility
- point-in-time consistency
- sealed-test kontrolü
- auditability
- aynı data ile tekrar çalıştırma

## Mode B — Exploratory / Live Research Mode

```text
Notebook
   ↓
External Data Provider
```

Kullanım:

- yeni veri kaynağı keşfi
- prototip
- notebook-only araştırma

Bu mode açıkça:

```text
NON-REPRODUCIBLE / EXPLORATORY
```

olarak işaretlenmelidir.

Çalışma sonunda:

```text
Save Output as Dataset Snapshot
```

opsiyonu verilebilir.

---

# 11. Dataset Snapshot Mount

Notebook worker'a snapshot read-only olarak mount edilmelidir.

Örnek:

```text
/runtime/input/dataset.parquet
/runtime/input/dataset_metadata.json
```

Metadata:

```json
{
  "dataset_snapshot_id": "DS-991",
  "symbol": "EURUSD",
  "timeframe": "4H",
  "hash": "...",
  "created_at": "...",
  "point_in_time": true
}
```

Notebook:

```python
from pathlib import Path
import pandas as pd

df = pd.read_parquet(
    Path(INPUT_DIR) / "dataset.parquet"
)
```

ile okumalıdır.

---

# 12. Notebook Environment Registry

Notebook içinde:

```text
!pip install ...
```

production run'da kullanılmamalıdır.

Entity:

```text
notebook_environments
```

Alanlar:

```text
id
environment_code
name
python_version
image_ref
package_lock_hash
requirements_artifact_id
supports_gpu
created_at
status
```

İlk environment:

```text
regimelab-quant:1.0
```

Paketler:

```text
python 3.12
numpy
pandas
scipy
scikit-learn
xgboost
lightgbm
optuna
hmmlearn
yfinance
pandas-datareader
dukascopy-python
matplotlib
joblib
pyarrow
papermill
nbclient
nbformat
```

Versiyonlar lock edilmelidir.

---

# 13. Dependency Validation

Notebook upload edildiğinde statik inspection yapılmalıdır.

Kontrol:

- shell cells
- `pip install`
- `apt install`
- unknown imports
- hardcoded paths
- network access
- environment assumptions

UI:

```text
Notebook Compatibility

✓ Python 3.12
✓ pandas
✓ sklearn
✓ Optuna
✓ hmmlearn

⚠ pip install detected
⚠ External network request detected
⚠ Hardcoded local path detected
```

---

# 14. Secret Management

Notebook içine secret yazılmamalıdır.

Yanlış:

```python
FRED_API_KEY = "..."
```

Doğru:

```python
import os

FRED_API_KEY = os.environ["FRED_API_KEY"]
```

RegimeLab:

```text
Workspace Secrets
```

alanı sunmalıdır.

Secret entity / secret manager:

```text
FRED_API_KEY
DATA_PROVIDER_KEY
...
```

NotebookRun yalnızca izin verilen secret'ları environment variable olarak almalıdır.

Secret değerleri:

- notebook output'una yazılmamalı
- logs'ta maskelenmeli
- artifact içine serialize edilmemeli

---

# 15. Mevcut FRED Key İçin Yapılacak İş

Mevcut tez notebook'undaki açık FRED key:

```text
compromised / exposed
```

kabul edilmelidir.

Yapılacaklar:

1. Eski key rotate/revoke.
2. Yeni key RegimeLab secret store'a ekle.
3. Notebook'taki literal key kaldır.
4. Environment variable ile oku.
5. Secret scanner testine ekle.

---

# 16. Network Policy

Notebook worker default:

```text
network = disabled
```

olmalıdır.

Mode:

```text
SNAPSHOT_ONLY
```

Network gerekiyorsa explicit:

```text
EXPLORATORY_NETWORK
```

mode gerekir.

Allowlist opsiyonu:

```text
fred.stlouisfed.org
finance.yahoo.com
dukascopy...
```

Policy kayıt altına alınmalıdır.

---

# 17. Notebook Güvenliği

Arbitrary notebook execution remote code execution'dır.

Bu nedenle:

```text
Notebook Worker
```

ana API process içinde çalışmamalıdır.

Minimum izolasyon:

- ayrı worker process
- temp çalışma dizini
- CPU/RAM limiti
- timeout
- environment isolation
- read-only dataset mount
- isolated artifact output
- restricted network
- secret allowlist

Production'da tercih:

```text
Docker / container sandbox
```

---

# 18. Execution Limits

Policy:

```text
max_runtime_minutes
max_memory_mb
max_cpu
max_output_mb
max_artifact_count
max_artifact_size_mb
network_allowed
gpu_allowed
```

Örnek:

```text
Runtime       60 min
RAM           8 GB
CPU           4
Output        1 GB
Network       Disabled
GPU           Disabled
```

Workspace Research Budget ile entegre edilebilir.

---

# 19. Async Execution

Notebook HTTP request içinde çalıştırılmamalıdır.

Flow:

```text
POST /notebook-runs
        ↓
202 Accepted
        ↓
JOB-NB-001
        ↓
Queue
        ↓
Notebook Worker
```

Response:

```json
{
  "run_id": "NR-0041",
  "job_id": "JOB-8821",
  "status": "queued"
}
```

---

# 20. Cell Progress

Notebook executor cell event'lerini yayınlamalıdır.

Eventler:

```text
notebook.run.started
notebook.cell.started
notebook.cell.completed
notebook.cell.failed
notebook.artifact.created
notebook.metric.logged
notebook.run.completed
notebook.run.failed
```

Payload:

```json
{
  "type": "notebook.cell.completed",
  "workspace_id": "WS-FX-001",
  "run_id": "NR-0041",
  "cell_index": 18,
  "cell_count": 62,
  "elapsed_seconds": 4.2
}
```

---

# 21. SSE / WebSocket UI

Notebook Run ekranı:

```text
EURUSD_GA_AUTOML

RUNNING

Cell 18 / 62

████████████░░░░░░ 29%

00:00 Data loaded
00:12 Features generated
00:27 Model training started
01:48 Optuna trial 12/100
...
```

Existing RegimeLab SSE altyapısı tekrar kullanılmalıdır.

---

# 22. Artifact Contract

Notebook sadece kendi `SAVE_DIR` klasörüne göre davranmamalıdır.

Standart:

```text
ARTIFACT_DIR
```

kullanmalıdır.

Output:

```text
/runtime/artifacts/
```

altında tutulur.

Örnek:

```text
metrics.json
all_results.csv
best_per_feature_set.csv
group_summary.csv
feature_jaccard_similarity.csv
equity_curve.parquet
feature_survival.csv
model.pkl
plots/equity.png
```

Run sonunda Artifact Collector bunları Registry'ye taşır.

---

# 23. RegimeLab Notebook SDK

Yeni küçük Python SDK:

```text
regimelab_sdk
```

İlk API:

```python
from regimelab_sdk import run

run.log_metric("sharpe", 1.87)
run.log_metric("return", 0.174)
run.log_metric("max_drawdown", -0.061)

run.log_param("model", "xgboost")
run.log_param("threshold", 0.61)

run.log_artifact("feature_survival.csv")
run.log_artifact("equity_curve.png")

run.log_message("Genetic search completed")
```

SDK notebook içinde REST çağırmak yerine mümkünse local run context / file contract kullanabilir.

Worker run sonunda SDK output manifest'i toplar.

---

# 24. metrics.json Standardı

Notebook SDK olmadan da uyumluluk için:

```text
ARTIFACT_DIR/metrics.json
```

okunmalıdır.

Örnek:

```json
{
  "sharpe": 1.87,
  "return": 0.174,
  "max_drawdown": -0.061,
  "sortino": 2.18,
  "trade_count": 387
}
```

---

# 25. run_manifest.json

Her NotebookRun:

```json
{
  "workspace_id": "WS-FX-001",
  "experiment_id": "EXP-207",
  "notebook_id": "NB-004",
  "notebook_version": 3,
  "dataset_snapshot_id": "DS-991",
  "environment": "regimelab-quant:1.0",
  "random_seed": 42,
  "started_at": "...",
  "completed_at": "...",
  "status": "COMPLETED"
}
```

manifest üretmelidir.

---

# 26. Executed Notebook Artifact

Her başarılı/başarısız run'ın executed notebook'u saklanmalıdır:

```text
original.ipynb
executed.ipynb
```

Bu araştırmanın audit izi için kritiktir.

---

# 27. Experiment Entegrasyonu

NotebookRun:

```text
experiment_id
```

ile bağlanabilir.

Experiment Detail tabs:

```text
Overview
Equity
Trades
Features
Models
Optimization
Regimes
Validation
Notebook Runs
Artifacts
Logs
```

Notebook Runs ekranı:

```text
NR-041  EURUSD_GA_AUTOML v3   COMPLETED
NR-042  FEATURE_INTELLIGENCE  COMPLETED
NR-043  REGIME_ROUTER         FAILED
```

---

# 28. Notebook Sonucundan Experiment Metric Yazma

Default davranış:

Notebook metric'leri:

```text
NotebookRun Metrics
```

olarak tutulmalıdır.

Ana Experiment metrics'i otomatik overwrite edilmemelidir.

Explicit action:

```text
Promote Notebook Results to Experiment
```

veya Experiment Specification tarafından yetkilendirilmiş pipeline step üzerinden promotion yapılmalıdır.

---

# 29. Sealed Test Entegrasyonu

En kritik kural:

Notebook, sealed test politikasını bypass edememelidir.

Snapshot metadata:

```text
TRAIN
VALIDATION
SEALED_TEST
```

classification taşımalıdır.

NotebookRun:

```text
SEALED_TEST
```

dataset'e erişmek isterse:

```text
TestSealService
```

üzerinden permission kontrolü yapılmalıdır.

Notebook'a dosya yolu direkt verilerek seal atlatılmamalıdır.

---

# 30. Post-Test Iteration

Notebook sealed test gördükten sonra yeni araştırma üretirse:

```text
POST_TEST_ITERATION_FROM
```

lineage event'i üretilebilmelidir.

Notebook çalıştırma da Research Budget'a trial olarak yazılmalıdır.

---

# 31. Research Budget Entegrasyonu

Her NotebookRun için:

- run count
- CPU time
- GPU time
- backtest count (SDK üzerinden mümkünse)
- external data fetch
- sealed test access

ledger'a yazılmalıdır.

---

# 32. Workspace Scope

Her:

```text
Notebook
NotebookVersion
NotebookRun
Artifact
```

workspace-aware olmalıdır.

Cross-workspace erişim backend tarafından engellenmelidir.

---

# 33. Notebook Registry UI

Sol menü:

```text
Research
 ├── Experiments
 ├── Optimization Lab
 ├── Feature Lab
 ├── Notebook Lab
 └── Lineage
```

Notebook Lab liste:

```text
Name                        Version   Last Run   Status
EURUSD_GA_AUTOML            v3        2h ago     Ready
FEATURE_INTELLIGENCE        v2        1d ago     Ready
REGIME_ROUTER               v1        Never      Ready
tezmodelfinal               v1        Never      Review
```

---

# 34. Notebook Detail UI

Header:

```text
EURUSD_GA_AUTOML
Version 3
FX Research
```

Tabs:

```text
Overview
Source
Parameters
Runs
Artifacts
Dependencies
Security
Versions
```

Actions:

```text
Run
Clone
New Version
Archive
```

---

# 35. Run Dialog

```text
Run Notebook

Workspace:
FX Research

Experiment:
EXP-207

Dataset:
EURUSD_4H_v32

Environment:
Quant Python 3.12

Parameters:
SYMBOL       EURUSD
TIMEFRAME    4H
RANDOM_SEED  42

Network:
Disabled

Secrets:
FRED_API_KEY [not required in Snapshot Mode]

Estimated Runtime:
18 min

[Cancel] [Run]
```

---

# 36. REST API

## Notebook Registry

```http
POST   /api/v1/workspaces/{workspace_id}/notebooks
GET    /api/v1/workspaces/{workspace_id}/notebooks
GET    /api/v1/workspaces/{workspace_id}/notebooks/{notebook_id}
PATCH  /api/v1/workspaces/{workspace_id}/notebooks/{notebook_id}
POST   /api/v1/workspaces/{workspace_id}/notebooks/{notebook_id}/archive
```

## Versions

```http
GET  /api/v1/workspaces/{workspace_id}/notebooks/{id}/versions
POST /api/v1/workspaces/{workspace_id}/notebooks/{id}/versions
```

## Runs

```http
POST /api/v1/workspaces/{workspace_id}/notebook-runs
GET  /api/v1/workspaces/{workspace_id}/notebook-runs
GET  /api/v1/workspaces/{workspace_id}/notebook-runs/{run_id}
POST /api/v1/workspaces/{workspace_id}/notebook-runs/{run_id}/cancel

GET /api/v1/workspaces/{workspace_id}/notebook-runs/{run_id}/logs
GET /api/v1/workspaces/{workspace_id}/notebook-runs/{run_id}/metrics
GET /api/v1/workspaces/{workspace_id}/notebook-runs/{run_id}/artifacts
```

---

# 37. Upload Validation API

```http
POST /api/v1/workspaces/{workspace_id}/notebooks/inspect
```

Response:

```json
{
  "compatible": false,
  "python": "3.x",
  "imports": [
    "pandas",
    "numpy",
    "sklearn",
    "optuna",
    "hmmlearn"
  ],
  "issues": [
    {
      "severity": "warning",
      "code": "INLINE_PIP_INSTALL"
    },
    {
      "severity": "critical",
      "code": "POSSIBLE_SECRET"
    }
  ]
}
```

---

# 38. MCP Tools

İlk versiyon:

```text
list_notebooks
get_notebook
list_notebook_runs
get_notebook_run
get_notebook_metrics
get_notebook_artifacts
run_notebook
cancel_notebook_run
```

Tool input her zaman workspace-aware olmalıdır.

---

# 39. Agent Policy

AI agent:

- approved notebook çalıştırabilir
- snapshot seçebilir
- experiment'e bağlayabilir
- sonuç okuyabilir

Ancak default olarak:

- arbitrary notebook upload edemez
- shell-enabled yeni notebook oluşturup çalıştıramaz
- network izni açamaz
- secret göremez
- sealed test'i açamaz

Policy levels:

```text
AUTO_READ
AUTO_RUN_APPROVED_NOTEBOOK
APPROVAL_REQUIRED_FOR_NETWORK
APPROVAL_REQUIRED_FOR_UNAPPROVED_NOTEBOOK
HUMAN_REQUIRED_FOR_TEST_UNSEAL
```

---

# 40. Audit Log

Yeni operations:

```text
NOTEBOOK_UPLOADED
NOTEBOOK_VERSION_CREATED
NOTEBOOK_RUN_CREATED
NOTEBOOK_RUN_STARTED
NOTEBOOK_RUN_CANCELLED
NOTEBOOK_RUN_COMPLETED
NOTEBOOK_RUN_FAILED
NOTEBOOK_ARTIFACT_CREATED
NOTEBOOK_SECRET_INJECTED
NOTEBOOK_NETWORK_APPROVED
```

Secret değeri audit'e yazılmaz.

---

# 41. Mevcut tezmodelfinal Notebook'u İçin Migration Planı

Mevcut notebook'u doğrudan production run'a vermeden önce bir compatibility pass yapılmalıdır.

## Adım 1 — Backup

Orijinal notebook değişmeden saklanır:

```text
tezmodelfinal_original.ipynb
```

## Adım 2 — Secret temizliği

Hardcoded FRED key kaldırılır.

## Adım 3 — pip cells

`!pip install` hücreleri:

```text
DISABLED_FOR_REGIMELAB
```

olarak işaretlenir veya kaldırılır.

## Adım 4 — Parameter Cell

RegimeLab parameter cell eklenir.

## Adım 5 — SAVE_DIR

Sabit:

```python
SAVE_DIR = "..."
```

yerine:

```python
SAVE_DIR = ARTIFACT_DIR
```

kullanılır.

## Adım 6 — Data Mode

İlk compatibility sürümünde iki seçenek:

```text
legacy_fetch
snapshot
```

Snapshot mode default yapılır.

## Adım 7 — Output Manifest

Notebook sonunda:

```text
metrics.json
run_manifest.json
```

üretilir.

## Adım 8 — Compatibility Run

Known snapshot üzerinde çalıştırılır.

## Adım 9 — Result Diff

Legacy run vs RegimeLab run karşılaştırılır.

## Adım 10 — Register

Başarılıysa:

```text
Notebook Registry
```

içinde `APPROVED` yapılır.

---

# 42. Notebook'tan Core'a Kod Taşıma Planı

Notebook çalıştırmak son hedef değildir.

Mevcut notebook içindeki reusable kodlar sırayla production modüllerine çıkarılmalıdır.

Öneri:

```text
Notebook Code
     ↓
Compatibility wrapper
     ↓
Unit-tested Python module
     ↓
RegimeLab Core
     ↓
Notebook imports core
```

Örnek:

```text
make_index_tz_naive
align_market_to_4h
align_macro_to_4h
rolling_zscore
technical feature functions
```

ileride:

```text
regimelab.data.alignment
regimelab.features
```

altına taşınmalıdır.

Notebook aynı fonksiyonu tekrar tanımlamamalıdır.

---

# 43. İlk Üç Yeni Notebook

Notebook Lab V1 ile beraber şu notebook'lar hazırlanmalıdır.

## NB-001 — EURUSD_GA_AUTOML

```text
Feature Pool
   ↓
GA
 ├ feature selection
 ├ model selection
 ├ hyperparameters
 └ thresholds
   ↓
Walk Forward
   ↓
Pareto
   ↓
Candidate outputs
```

## NB-002 — EURUSD_FEATURE_INTELLIGENCE

```text
IC
IC Decay
Rolling IC
Sign Consistency
Redundancy
Drift
Regime IC
Feature Survival
```

## NB-003 — EURUSD_REGIME_ROUTER

```text
Regime Model
   ↓
Per-regime candidate performance
   ↓
Routing policy
   ↓
Worst regime risk
   ↓
Regime-aware strategy
```

---

# 44. Phase Plan

## Phase 0 — Spike / Proof of Concept

Amaç:

Bir basit `.ipynb` dosyasını async worker ile çalıştırıp executed notebook'u artifact olarak saklamak.

Deliverables:

- Papermill POC
- Job integration
- basic logs
- output artifact
- cancellation/timeout

Kabul:

```text
Notebook upload → run → executed.ipynb
```

uçtan uca çalışıyor.

---

## Phase 1 — Notebook Registry

Deliverables:

- notebooks table
- notebook_versions
- upload API
- hash/version
- list/detail UI
- workspace scope
- archive

Kabul:

Notebook upload edilir, versiyonlanır ve refresh sonrası kaybolmaz.

---

## Phase 2 — Parameterized Execution

Deliverables:

- parameter contract
- NotebookRun
- experiment binding
- dataset snapshot binding
- environment binding
- async execution
- run history

Kabul:

Aynı notebook iki farklı Experiment/Dataset ile ayrı run oluşturabiliyor.

---

## Phase 3 — Environment + Secrets

Deliverables:

- environment registry
- quant environment
- dependency inspection
- secret manager adapter
- log masking
- hardcoded secret detection

Kabul:

Notebook içindeki `pip install` gerekmiyor; FRED benzeri key'ler environment üzerinden geliyor.

---

## Phase 4 — Artifact + Metrics

Deliverables:

- ARTIFACT_DIR
- Artifact Collector
- metrics.json
- SDK
- Experiment Notebook Runs tab
- plots/csv/model outputs

Kabul:

Notebook sonucu RegimeLab UI'dan okunabiliyor.

---

## Phase 5 — Security Sandbox

Deliverables:

- isolated runner
- CPU/RAM limit
- timeout
- network policy
- read-only dataset
- artifact quota
- workspace guard

Kabul:

Notebook API process'i veya başka workspace datasını etkileyemiyor.

---

## Phase 6 — Sealed Test + Research Governance

Deliverables:

- TestSealService integration
- research budget events
- post-test lineage
- approval flow

Kabul:

Notebook, REST/MCP/UI üzerinden sealed-test politikasını bypass edemiyor.

---

## Phase 7 — MCP + Agent

Deliverables:

- notebook MCP tools
- approved notebook policy
- agent run summary
- audit

Kabul:

Agent approved notebook'u workspace/dataset/experiment seçerek çalıştırabiliyor.

---

## Phase 8 — tezmodelfinal Migration

Deliverables:

- sanitized notebook
- parameterized notebook
- snapshot mode
- artifact mode
- compatibility regression
- approved registry version

Kabul:

Mevcut tez notebook'u RegimeLab içinde reproducible şekilde çalışıyor.

---

## Phase 9 — New Research Packs

Deliverables:

- EURUSD_GA_AUTOML.ipynb
- EURUSD_FEATURE_INTELLIGENCE.ipynb
- EURUSD_REGIME_ROUTER.ipynb

Kabul:

Üç notebook da aynı Dataset Snapshot / Experiment / Artifact contract'ını kullanıyor.

---

# 45. Uygulama Sırası

Astra için önerilen sıra:

1. Mevcut async job + artifact + workspace altyapısını analiz et.
2. Papermill execution POC yap.
3. `notebooks`, `notebook_versions`, `notebook_runs` migration'larını ekle.
4. Notebook upload/registry API'lerini oluştur.
5. Workspace-aware Notebook Lab UI ekle.
6. Parameter cell contract'ını uygula.
7. Dataset Snapshot mount ekle.
8. Experiment binding ekle.
9. Quant environment oluştur.
10. Inline pip kullanımını compatibility warning yap.
11. Secret injection/masking ekle.
12. Artifact collector ekle.
13. Metrics contract/SDK ekle.
14. Live cell progress events ekle.
15. Cancellation, timeout, resource limits ekle.
16. Network policy ekle.
17. Sealed Test integration ekle.
18. Research Budget integration ekle.
19. MCP notebook tools ekle.
20. Agent approval policy ekle.
21. `tezmodelfinal` migration adapter'ını yap.
22. Compatibility regression çalıştır.
23. Üç yeni research notebook'u ekle.

---

# 46. Mevcut Kodla Entegrasyon Noktaları

Mevcut yapıya göre uyarlanacak muhtemel alanlar:

```text
backend/platform/schema.py
backend/platform/db.py
backend/platform/service.py
backend/platform/api.py
backend/platform/research.py

backend/workers/
backend/mcp/server.py

frontend/src/ResearchPlatform.tsx
frontend/features/notebooks/
frontend/services/
```

Yeni önerilen modüller:

```text
backend/platform/notebooks/
├── models.py
├── schema.py
├── service.py
├── executor.py
├── inspector.py
├── artifacts.py
├── policies.py
└── sdk_context.py

backend/workers/notebook_worker.py

frontend/features/notebooks/
├── NotebookList.tsx
├── NotebookDetail.tsx
├── NotebookRunDialog.tsx
├── NotebookRunDetail.tsx
└── NotebookArtifacts.tsx
```

---

# 47. Test Planı

## Unit

- parameter injection
- notebook hash/version
- artifact collection
- metric parsing
- timeout
- secret masking
- import inspection
- workspace guard
- test seal guard

## Integration

- upload → run → completed
- dataset mount
- experiment link
- artifact save
- failed notebook
- cancellation
- network denied
- secret injection
- MCP run
- post-test policy

## Regression

`tezmodelfinal` için:

- same input snapshot
- same random seed
- key output metric comparison
- output row count
- expected artifacts
- expected model count / run summary where deterministic

---

# 48. Acceptance Criteria

Notebook Lab V1 tamamlandı sayılabilmesi için:

- [ ] `.ipynb` yüklenebiliyor.
- [ ] Notebook workspace'e bağlı.
- [ ] Notebook versionlanıyor.
- [ ] Notebook DB'de kalıcı.
- [ ] Parameter cell detect/inject ediliyor.
- [ ] Dataset Snapshot seçilebiliyor.
- [ ] Experiment seçilebiliyor.
- [ ] Run async çalışıyor.
- [ ] UI canlı progress/log gösteriyor.
- [ ] Timeout/cancel çalışıyor.
- [ ] `pip install` run sırasında zorunlu değil.
- [ ] Environment version kaydediliyor.
- [ ] Secret notebook içine yazılmıyor.
- [ ] Secret logs'ta maskeleniyor.
- [ ] Executed notebook saklanıyor.
- [ ] Artifacts saklanıyor.
- [ ] Metrics saklanıyor.
- [ ] Notebook run Experiment Detail'de görülebiliyor.
- [ ] Workspace isolation uygulanıyor.
- [ ] Sealed test policy bypass edilemiyor.
- [ ] Audit log mevcut.
- [ ] MCP approved notebook çalıştırabiliyor.
- [ ] Mevcut `tezmodelfinal` notebook'u sanitize edilerek çalıştırılabiliyor.

---

# 49. V1 Definition of Done

Aşağıdaki akış tamamen çalışıyorsa V1 tamamdır:

```text
FX Research
   ↓
Notebook Lab
   ↓
tezmodelfinal_regimelab.ipynb
   ↓
Dataset Snapshot DS-991
   ↓
Experiment EXP-207
   ↓
regimelab-quant:1.0
   ↓
Run
   ↓
Async isolated worker
   ↓
Executed notebook
   ↓
Metrics
Artifacts
Logs
   ↓
Experiment Registry
```

Ve browser refresh sonrasında run/history/artifacts kaybolmamalıdır.

---

# 50. Astra'ya Verilecek Direkt Prompt

> Mevcut RegimeLab kod tabanına bu dokümandaki Notebook Lab özelliğini iteratif olarak ekle. Notebook'ları ana API process içinde çalıştırma; mevcut async job altyapısını kullan ve execution'ı izole worker'a taşı. Workspace, Experiment ve Dataset Snapshot context'lerini zorunlu first-class input olarak ele al. Default çalışma modu Snapshot Mode olsun. Notebook içinde runtime `pip install` ve hardcoded secret kullanımını production compatibility açısından yasakla/uyarı ver; dependency'leri versioned Quant Environment üzerinden sağla ve secret'ları environment injection ile ver. Her NotebookRun için notebook version, environment, parameters, dataset hash, random seed, executed notebook, metrics, logs ve artifacts kaydedilsin. Notebook sealed-test governance veya workspace isolation'ı bypass edemesin. Önce Papermill POC ve Notebook Registry'yi tamamla; sonra parameterized execution, environment/secrets, artifact/metrics, sandbox, governance, MCP ve mevcut tezmodelfinal notebook migration'ına geç. Mevcut GA/backtest/experiment akışını bozma. Her fazda migration, API, backend test, UI ve audit entegrasyonunu birlikte tamamla.
