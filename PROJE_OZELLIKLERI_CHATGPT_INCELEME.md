# RegimeLab — Proje Özellikleri (ChatGPT İncelemesi İçin)

> Tarih: 2026-09-06
> Repo: `D:\agentic\ml` (branch `main`)
> Amaç: Bu dosya projenin mevcut tüm özelliklerini, mimarisini, API'lerini, UI ekranlarını, veri sözleşmelerini, test durumunu ve eksik/planlı işleri tek yerde toplar. ChatGPT'ye verip mimari/kalite/quant-doğruluk incelemesi istemek için hazırlanmıştır.
> Kaynaklar: `README.md`, `PRODUCT_PLAN.md`, `IMPLEMENTATION_STATUS.md`, `TODO_NEXT.md`, `V2_IMPLEMENTATION_BACKLOG.md`, `v3.md`, `CHANGELOG.md`, `AI_ASSISTANTS.md`, `REGIMELAB_NOTEBOOK_LAB_IMPLEMENTATION_PLAN.md`, `NOTEBOOK_LAB_UI_FIX_PLAN.md`, `md/01_CURRENT_ARCHITECTURE.md`, `md/TASKS.md`, kod taraması (`backend/`, `frontend/src/`, `tests/`, `regimelab_sdk/`).

---

## 1. Proje Özeti

**RegimeLab**, EUR/USD (genelde FX) araştırması için local-first deney platformudur:

- **Frontend:** React + TypeScript + Vite (`frontend/src/ResearchPlatform.tsx` tek sayfa + `QuantLab.tsx`, `QuantLabRisk.tsx`, `NotebookLab.tsx`, `Assistants.tsx`, `workspace.tsx`, `App.tsx`).
- **Backend:** Python/FastAPI (`backend/app.py` + `backend/platform/` + `backend/engine.py` + `backend/quant/` + `backend/mcp/server.py`).
- **DB:** Yerelde SQLite/WAL + SQLAlchemy + Alembic (`backend/migrations/versions/0001-0015`); `REGIMELAB_DATABASE_URL` ile PostgreSQL seçilebilir.
- **Çalışma şekli:** Immutable Experiment Specification → SHA-256 snapshot → tek worker'da async çalıştırma → holdout / walk-forward validasyon → sealed final test → SSE canlı ilerleme.
- **Kullanım:** `.\start.ps1` (veya `start.cmd`) → `http://127.0.0.1:8000`; API docs `/docs`, platform `/api/v1`, quant `/api`.
- **Hedef kullanıcı:** Tek kullanıcı, local araştırmacı. Çok-kiracılı SaaS, canlı trading, dağıtık GPU **non-goal (v1)**.

Ana ilkeler:
- `Notebook = Research Client, RegimeLab Core = Source of Truth`.
- GA test verisini görmez; aday dondurulduktan sonra test tek kez ölçülür.
- Maliyet/validasyon/final-test aynı `merged_reality` yolunu kullanır.
- `result.json` silinse bile Candidate/Feature listeleri DB'den render olur (tasarım gereği overview/validation/test/regime/compare görünümleri `result.json` okur).

---

## 2. Teknoloji Stack

| Katman | Teknoloji |
|---|---|
| Backend API | FastAPI, Pydantic, SQLAlchemy, Alembic, SSE |
| ML/Quant | scikit-learn (Ridge, RF, HGB), XGBoost, LightGBM, hmmlearn GaussianHMM, SciPy, Optuna (notebook env), pandas/numpy/pyarrow |
| Quant ek | `backend/quant/`: ic, clustering, validation, ablation, fitness, calibration, stress, dimensionality, config |
| Frontend | React 18 + TS + Vite, `platform-api.ts`, `quant-demo.ts`, i18n TR/EN, light/dark tema |
| Notebook exec | Papermill + nbclient + nbformat (async isolated worker) |
| AI Asistan | Ollama Chat API (`REGIMELAB_AI_MODEL`, `REGIMELAB_AI_URL`, default `http://127.0.0.1:11434`), 90sn timeout |
| MCP | Resmi MCP SDK adapter (`backend/mcp/server.py`, stdio: `python -m backend.mcp.server`) |
| Auth | Tek API key (`REGIMELAB_API_KEY` Bearer) + localhost bind + JWT (24s? 24h — `auth_utils.py`), `0015_auth_admin` |
| Test/CI | pytest (`tests/` 15 dosya), `vite build` + `tsc -b`, `.github/workflows/ci.yml` (`pytest + vite build`) |
| Deploy | Local-first; `vercel.json` + `api/index.py` legacy Vercel adapter mevcut ama local-first kararıyla sökülme/ertelemede; Docker yok |

---

## 3. Mimari ve Klasör Haritası

```text
backend/app.py                 # FastAPI app, legacy /api/runs + /api/datasets + mount platform/quant
backend/engine.py              # Çekirdek: read_prices, features, causal_probabilities, backtest/fx_backtest/metrics, audit_calendar, fx_holidays
backend/platform/
  schema.py                    # ExperimentSpec, OptimizationSpec, SearchSpaceDefinition, BacktestRealityConfig, POLICY
  db.py / models.py            # SQLAlchemy tablolar
  service.py                   # ExperimentService: registry, snapshot, seal, budget, ledger, clone, lineage, workspace CRUD
  research.py                  # GA optimize(), feature_frame(), registry(), RegimeRouter, frozen_candidate, cost-sensitivity
  api.py                       # /api/v1 REST surface
  quant_api.py                 # /api/features/*, /validation/*, /calibration/run, /backtest/*, /optimization/fitness, /quant/*
  worker.py / scope.py         # tek worker (ThreadPoolExecutor max_workers=1), workspace_scope contextvar guard
  models.py / families.py      # MODEL_REGISTRY (ridge, rf, hgb, xgb, lgb), family_for_column (macro__/cross_asset__/fx__/rates__)
  assistants.py                # AI asistan zincir servisi
  auth_utils.py / i18n.py
  notebooks/                   # Notebook Lab: service, executor, parser, inspector, migrator, artifacts, generate_starters
  migrations/versions/0001-0015 # registry, governance, search_space, feature_intel x2, seal, workspace, budgets, parents, feature_intel v2, assistants, audit_ws, notebook_lab, candidate_fold, auth_admin
backend/quant/
  ic.py, clustering.py, dimensionality.py, ablation.py, validation.py, fitness.py, calibration.py, stress.py, config.py
backend/mcp/server.py          # domain-only MCP tools, Bearer auth
frontend/src/
  ResearchPlatform.tsx         # ana platform: wizard (6 adım), registry, detail (8 sekme), compare, budget, catalog, activity
  QuantLab.tsx / QuantLabRisk.tsx # Feature Quality, Validation, Models/Calibration/Quantile, Stress
  NotebookLab.tsx + notebook.css # registry, detail (Overview/Source/Params/Runs/Artifacts/Deps/Security/Versions), run dialog, secrets, SSE
  Assistants.tsx               # 4 hazır şablon + klonla + zincir + görevler
  workspace.tsx / ws-store.ts  # WorkspaceContext, ?workspace= persist (URL > localStorage > default)
  platform-api.ts / quant-demo.ts / i18n.tsx / auth.tsx / AuthPage.tsx / AccountPage.tsx / App.tsx
regimelab_sdk/__init__.py      # notebook içi SDK: run.log_metric/param/artifact/message, metrics.json/params.json flush
tests/                         # test_api, test_engine, test_platform, test_backtest_golden (21), test_assistants, test_auth_security, test_notebooks (9), test_quant_* (7 dosya)
data/                          # run-*.json, dataset-*, snapshot store (local)
```

---

## 4. Veri ve Hesaplama Protokolü

### 4.1 CSV Sözleşmesi
- `Timestamp,Open,High,Low,Close` (case-insensitive; date/datetime/time kabul).
- ISO8601 önerilir, tz yoksa UTC. Bar başlangıcı. Min 400, max 200.000 satır, 25 MB.
- OHLC tutarlılık, missing/inf/sıfır-negatif/duplicate reject. Küçük TF'ye sentetik üretim yok, büyük TF'ye OHLC aggregation (sonra yine 400 bar şartı).
- Sentetik demo: sabit tohumlu 3000 x 4H bar (gerçek piyasa verisi değil).

### 4.2 Laglı Makro / Cross-asset
- Prefix: `macro__`, `cross_asset__`, `fx__`, `rates__`.
- Opsiyonel `__available_at` (UTC yayın anı). Yoksa 1 bar gecikmeli kullanılır ama snapshot `unverified` işaretler.
- Feature'lar: value/delta/return hepsi ≥1 bar gecikmeli; yayın anı bar zamanından sonraysa o gözlem kullanılmaz.
- Vintage/revision/provider/survivorship garantisi yok — kullanıcı beyanı.

### 4.3 Feature Engineering
- `engine.features`: gecikmeli return, momentum, SMA oranları, volatilite (14b), momentum (30b), RSI, MACD, range/body, hour_sin/cos.
- `research.feature_frame`: + `lag__/delta__/return__` external + statistical (25 engine / 34 research).
- Quant: Spearman IC, IC decay [1,2,3,5,10,20], sign consistency, quality score, hierarchical clustering (distance=1-|corr|), redundancy pruning (absIC > sign > missing), PCA/PLS train-only, tanh/sigmoid/threshold/winsorize, sequential ablation, SHAP-stability (SHAP bağımlılığı yok).

### 4.4 Modeller ve Ensemble
- Trend: StandardScaler+Ridge; Momentum: RandomForest; Volatilite: HistGradientBoosting.
- Ek registry: XGBoost, LightGBM (`MODEL_REGISTRY`, ModelAdapter).
- HMM girdileri: return + 14b vol + 30b momentum; **forward-filtering only** (Viterbi yok); scaler train-only.
- Rejim başına validasyon MSE tersi normalize → uzman ağırlığı; <15 rejim gözlemi ise global fallback.
- Eşik `[0,0.25,0.5,1,2]` bp validasyon Sharpe'a göre; testte re-opt yok.
- Sinyal t close → t+1 open işlem → t+2 open'a kadar tut; hedef t+1→t+2 open return. CSV `signal_timestamp` vs `timestamp` ayrımı korunur.

### 4.5 Train/Val/Test ve Validasyon
- Train %50-75, val %15, kalan test; sınırlarda 2'şer bar purge.
- Holdout veya gap'li expanding-window walk-forward.
- `quant/validation.py`: PurgedKFold (purge+embargo), rolling/anchored splits, gridsiz nested HPO.
- GA dev-only görür; `frozen_candidate.json` sonrası tek final test.

### 4.6 Backtest Reality (FX)
- 1bp=%0.01. Tek-yön maliyet girişte+pozisyon değişiminde+final çıkışta; long→short 2x.
- `BacktestRealityConfig`: fixed/`ohlc_range` spread, komisyon, slippage, flat+long/short swap, Wed triple; fill/latency/stop yok (dokümante).
- Kaldıraç: `exposure = max_leverage * max_position_fraction`, tek-bar -%100 floor + likidasyon sonrası flat (`margin_calls`/`liquidated`).
- Sharpe rf=0, yıllık bar `252*24/medyan_bar_saati`, DD ilk sermaye dahil, win-rate aktif bar üzerinden.
- Takvim: `audit_calendar` + `fx_holidays_for_year` (1 Oca, Good Friday, Easter Monday, 25/26 Ara + observed); weekend/midweek/holiday gap flag (reject yok).
- Golden testler: `tests/test_backtest_golden.py` (21 test) — spread, gap equity geçişi (+%2 weekend jump), DST/tz tespiti, financing, margin.

### 4.7 Politika Limitleri (local)
Max 32 pop, 20 gen, 128 aday, 5 model, 50k bar, 10dk, tek worker. Aşan `policy_rejected`.

---

## 5. Experiment Platformu (Çekirdek)

| Özellik | Açıklama |
|---|---|
| Immutable spec | Her run önce `ExperimentSpecification` kaydı; koşan experiment tekrar koşmaz, varyasyon **Klonla** ile |
| Snapshot | Doğrulanmış OHLC'nin değişmez kopyası + SHA-256 + satır/şema/UTC/aralık stats + PIT denetimi |
| Lifecycle | DRAFT → QUEUED → RUNNING → COMPLETED/FAILED/CANCELLED/TIMEOUT/POLICY_REJECTED; cancel adım sonu uygulanır; restart running'i failed/interrupted yapar |
| Async+SSE | Tek worker + canlı SSE ilerleme + polling fallback; `experiment.status.changed` event'leri workspace_id taşır |
| 6-adımlı wizard | 1) Search-space seçici (space dropdown → spec'e kopyala + `search_space_id` bağla, elle düzenleme bağı keser), 2) dataset/bar/HMM/capital/cost/train-ratio, 3) multi-objective constraint (min-trade/max-pos), devamı model/feature/validation |
| SearchSpaceDefinition | Sürümlü, workspace-scoped; feature groups/count bounds, model candidates, hp aralıkları, thresholds/regime/max_drawdown (lookback yok — borç) |
| GA | pop/select/crossover/mutate; feature+model+sınırlı hp+eşik arar; generation/parents izler; `candidate_parents` (mig 0008) iki-fazlı yazar; `pareto_ranks` gerçek katmanlı rank |
| Multi-objective | Aday başına 6'lı vektör (sharpe/return/sortino↑, max_drawdown/turnover/cost_bps↓ + `OBJECTIVE_DIRECTIONS`); constraint `max_drawdown+min_trades+max_exposure` (`constraint_violations`); Pareto scatter X/Y seçilebilir; seçim hâlâ skaler fitness (NSGA-II yok — borç) |
| Quant fitness | `QuantFitnessCalculator` (sharpe/fq/drawdown/turnover ağırlıklı) + `feature_count_penalty` (default kapalı) + `fitness_breakdown` + `reproducibility` (seed/pop/gen/rates/weights/universe); opt-in `use_quant_fitness` |
| Candidate Registry | `optimization_candidates` DB-backed tablo (nesil/rank/dominance/karar/ebeveyn); satır toplu val skoru, fold-detay `result.json`da (borç); `GET /experiments/{id}/candidates`, `GET /candidates/{id}` |
| Feature Intelligence | `feature_analysis` ölçülen missingness + dev rejim IC; mig 0009 (`feature_regime_metrics`, `selection_events`, `redundancy_pairs`); `GET .../feature-intelligence`; Features sekmesi DB, yoksa `result.json` fallback; lag maskelemede %10-20 missing smoke |
| RegimeRouter | HMM fiti optimize öncesine (dev-only causal); aday başına val-dilim rejim metrikleri + worst-regime DD + coverage; `max_worst_regime_drawdown` gate (infeasible); Regimes sekmesinde best-aday tablosu; inference-anında yönlendirme yok (bilinçli) |
| Lineage | 7 tip: `CLONED_FROM`, `POST_TEST_ITERATION_FROM` (seal-kirliliği öncelikli), `FEATURE_REDUCED_FROM`, `VALIDATION_CHANGED_FROM`, `REGIME_SPECIALIZED_FROM`, `REGULARIZED_FROM`, `AUTO_REFINED_FROM`; `experiment_edges`; Köken sekmesi 3-derinlik BFS + node Sharpe/return/DD + val→test delta |
| Compare | 2-5 deney: equity overlay, drawdown, ayar/feature farkları |
| Sealed test | `test_seals` + epoch (`uq_test_seals_dataset_epoch`), `test_access_events`; seal kapalı kalır, erişim auditlenir; `seal/invalidate|rotate`, `seal/history`; child `POST_TEST_ITERATION_FROM` |
| Budget/Ledger | `research_budgets` + `trial_events` (per-workspace, mig 0007, legacy global devri); `POST /research/estimate` (policy+maliyet+risk, yaratmadan); `GET /research/ledger`; Bütçe sekmesi limit bar + pressure score; `policy_rejected` |
| Capability | `GET /capabilities` — ALFRED/vintage, PSR/PBO, Optuna, TFT, Champion/Challenger, dağıtık worker `planned` |
| Artifacts | `specification.json`, `frozen_candidate.json`, `model.joblib`, `result.json`, `metrics.json`, `params.json`, executed.ipynb vb.; model nesnesi saklanmaz, config ile retrain |
| Legacy | `/api/runs`, `/api/datasets` korunur (scope'suz, deprecated adayı); yeni iş `/api/v1/experiments` |

---

## 6. Workspace (first-class domain)

- `workspaces` entity (mig 0006: id, workspace_code UNIQUE örn `WS-FX-001`, name, description, market, base_currency, timezone, owner/tenant, archived).
- Scope: experiments, snapshots, search-spaces, budgets, seals, edges/lineage, agent-runs, jobs, artifacts, notebooks — header `X-Workspace-Id` / `?workspace_id=` / `?workspace=` (query persist, refresh-safe; `/w/{id}` path yok — borç).
- Guard: `workspace_scope` contextvar; cross-workspace okuma **404** (enumeration engeli); test tekrarı bloklanmaz, sayaç+`POST_TEST_ITERATION_FROM`+risk bayrağı.
- Selector backend'den (`GET /workspaces` sayaçlı); switch tüm listeleri reload eder; New Workspace `POST /workspaces` (otomatik geçiş); Archive (hard delete yok).
- Audit: `WORKSPACE_CREATED/UPDATED/ARCHIVED/SWITCHED` + workspace kolonu (mig 0011, Activity'de WS sütunu).
- Bütçe/seal workspace başına izole; legacy CSV listesi global kalır (borç); tenant/RBAC yok (ürün kararı gerekir).

---

## 7. Quant Lab (backend `quant/` + UI)

Backend endpointler (`backend/platform/quant_api.py`, `{success,experiment_id,data,error}` zarfı):
- `POST /api/features/ic`, `/ic-decay`, `/stability`, `/quality`, `/clustering`, `/prune`, `/ablation`, `/shap-stability`
- `POST /api/validation/purged-kfold`, `/retraining` (rolling/anchored)
- `POST /api/calibration/run` (Platt/isotonic, Brier/log-loss/eğri), `POST /api/quantile/predict` (P10/P50/P90, LGBM quantile yoksa sklearn GBR)
- `POST /api/backtest/slippage-stress`, `/latency-stress`, `/stress` (commission×slippage matrix + 7 senaryo, hep `fx_backtest` üzerinden), `POST /api/optimization/fitness`, `GET /api/quant/config`, `GET /experiments/{id}/quant-artifacts`

UI:
- `QuantLab.tsx`: Quality (IC bar, filtre, quality/cluster/selected tablo, IC decay eğrisi, korelasyon heatmap, seed'li demo fallback) + Validation (purged/rolling/anchored, TRAIN/PURGE/VALIDATION/EMBARGO timeline, fold tablosu).
- `QuantLabRisk.tsx`: Models (fitness breakdown, kalibrasyon eğrisi+Brier, quantile tablo+band) + Stress (baz/en-kötü kart, commission×slippage heatmap, latency→Sharpe, 7 senaryo; tamamlanmış deney eğrisi veya demo).

Config: `backend/quant/config.py` (`DEFAULT_QUANT_CONFIG` + 9 artifact tipi + `selected_feature_list`).

---

## 8. Notebook Lab

- Registry: `.ipynb` upload/import, hash+versiyon (`notebooks`, `notebook_versions`, mig 0012), ACTIVE/ARCHIVED/INVALID, workspace+experiment+snapshot binding.
- Run: `notebook_runs` (DRAFT→QUEUED→PREPARING→RUNNING→COLLECTING→COMPLETED/FAILED/CANCELLED/TIMEOUT/POLICY_REJECTED), async worker (Papermill+nbclient), `REGIMELAB_PARAMETERS` cell inject (`WORKSPACE_ID`, `EXPERIMENT_ID`, `DATASET_SNAPSHOT_ID`, `SYMBOL`, `TIMEFRAME`, `RANDOM_SEED`, `INPUT_DIR`, `ARTIFACT_DIR`), 202 Accepted + job id.
- Mount: snapshot read-only (`/runtime/input/dataset.parquet` + metadata json); Mode A Snapshot (default, reproducible) / Mode B Exploratory (NON-REPRODUCIBLE flag, network gerekir).
- Env: `regimelab-quant:1.0` (py3.12, numpy/pandas/scipy/sklearn/xgb/lgbm/optuna/hmmlearn/yfinance/dukascopy/mpl/pyarrow/papermill/nbclient); `!pip install` production'da yasak/uyarı; dependency inspection (shell/pip/network/hardcoded-path/secret) + compatibility banner.
- Secret: workspace secrets, env inject, log maskeleme, artifact'a serialize yok; tez notebook'undaki hardcode FRED key compromised sayılıp rotate istenir.
- Artifact: `ARTIFACT_DIR` collector (`metrics.json`, `run_manifest.json`, csv/parquet/png/html/model), executed.ipynb saklanır, nested artifact + symlink guard + download endpoint.
- SDK: `regimelab_sdk.run.{log_metric,log_param,log_artifact,log_message,get_input_path,summary}`.
- Governance: sealed-test bypass yok (SEALED_TEST snapshot `TestSealService` izni), budget'a trial yazar, post-test `POST_TEST_ITERATION_FROM`.
- UI (`NotebookLab.tsx`): grid/list, search, detail 8 sekme (Overview/Source/Parameters/Runs/Artifacts/Dependencies/Security/Versions), Run dialog (ws/exp/snapshot/env/params/network/secrets/runtime tahmini), canlı cell progress (18/62 + %), log sarma, Yeni Versiyon (Overview'dan), TR/EN i18n.
- REST: `/workspaces/{ws}/notebooks*`, `/versions`, `/notebook-runs*`, `/logs|metrics|artifacts`, `/artifacts/{name}` download, `/snapshots`, `/notebooks/inspect`.
- MCP: `list_notebooks`, `get_notebook`, `list_runs`, `get_run`, `get_metrics`, `get_artifacts`, `run_notebook`, `cancel_run` (hep workspace-aware).
- Migration: `tezmodelfinal*` sanitize (backup→secret temizliği→pip disable→param cell→`SAVE_DIR=ARTIFACT_DIR`→snapshot mode→manifest→compat run→diff→APPROVED); 3 yeni pack planlı (GA_AUTOML, FEATURE_INTELLIGENCE, REGIME_ROUTER).
- Durum: UI fix plan 4 faz tamam (9 notebook testi yeşil), manuel tarayıcı kontrolü eksik.

---

## 9. AI Asistanlar

- Sekmede 4 salt-okunur şablon: Research, Idea, Validation, Backtest; Klonla ile kopyala + **Asistan ekle** (boş config); ad/açıklama/sistem talimatı/aşama/izin/alt-zincir düzenlenir.
- İzinler: deney-config okuma, metrik okuma, backtest çalıştır ayrı; talimat + opsiyonel deney seçimi; otomatik backtest kutusu işaretlenmezse sadece analiz.
- Zincir: kök ilk, sonra alt asistanlar sırayla (max 8 kök dahil); döngü/tekrar/cross-workspace reddedilir; her adım önceki çıktıları alır (sonraki asistanın okuma izni olmalı); başlatmada zincir snapshot'lanır.
- Backtest: taslak mevcut worker'da koşar, zincir `WAITING_BACKTEST` bekler, gerçek özetle devam; devam eden beklenir, tamamlanmışın sonucu kullanılır; aynı deney zincirde tekrar koşmaz; bütçe/policy/tek-run/kilitli-test korunur; fail/cancel/reject zinciri durdurur.
- Model: Ollama Chat API; env değişince restart; Vercel localhost'a ulaşamaz + bg worker garantisiz → local/sürekli sunucu önerilir.
- Görevler: son 100, durum/step çıktısı/backtest id/hata; polling auto-refresh; `GET /assistant-tasks/{id}`, `POST .../cancel` (kalan adımlar engellenir, geç yanıt tamamlayamaz, backtest ayrıca iptal edilir).
- Güvenlik: sadece seçili deney config+izinli metrik gönderilir (ham dosya/yol/anahtar yok); model çıktısı yürütülmez; deney yaratma/değiştirme/canlış işlem yok; aşama sadece etiket.
- Persist: config+görev WS-bağlı DB'de (mig 0010); restart kaydedilmiş adımdan devam, tamamlanmış korunur, yarım model adımı retry edilebilir.
- Doğrulama: `pytest test_assistants/test_platform/test_api + npm run build`; model bağlantısı mock'lanır.

---

## 10. MCP Adapter

- Stdio server (`python -m backend.mcp.server`), domain-only (ham Python/SQL yok).
- Araçlar: experiment create/run/status, compare, sonuç okuma, validate (`POST /research/estimate`), search-space/candidates/lineage/budget/seal/robustness/feature-stability, notebook list/get/run/cancel/metrics/artifacts, workspace list/get/create + filtreli liste.
- Auth: `REGIMELAB_API_KEY` varsa REST+MCP aynı Bearer.
- Eksik (bilinçli): `request_test_unseal` approval akışı yok (direkt erişim vermez tasarım), seviyeler (`AUTO_READ/CREATE_DRAFT/APPROVAL_REQUIRED_TO_RUN/AUTO_RUN_WITHIN_BUDGET`) ve RBAC yok.

---

## 11. Frontend Ekran Envanteri

- **Toolbar:** registry (Experiments), Quant Lab, AI Asistanlar, Budget, Compare, Catalog, Activity + refresh.
- **Wizard (Yeni deney):** 6 adım, taslak kaydet → detail'de spec review → ayrı Çalıştır.
- **Detail 8 sekme:** overview (KPI: return/Sharpe/maxDD/sortino, val→test delta, equity overlay, CSV export, warnings), optimization (GA eğrisi best/mean fitness, survival, Pareto, DB aday tablosu), features (DB intel veya `result.json` fallback: IC/rolling-IC/sign/MI/redundancy), validation (fold tablosu train_end/val_start/gap/Sharpe + cost-sensitivity multiplier/bps/return/Sharpe/DD), regimes (bar/share/mean_bps + best-aday rejim Sharpe/return/DD/qualified + worst-DD/coverage), lineage (graf), artifacts (spec/frozen_candidate/model.joblib/result.json download + spec/snapshot json), logs (event stream, candidate.started filtreli).
- **Diğer:** Compare (2-5), Budget (limit bar+pressure+ledger), Catalog (feature/model listesi), Activity (audit, WS sütunlu, paginated), Data Hub (CSV upload + laglı örnek + snapshot listesi), Metodoloji (kısıtlar: TFT/FRED/Dukascopy/25-uzman/MAIN_14/THEORY_11 yok), Workspace switcher/popup + Overview (counts, best strategy, budget %, running jobs, recent).
- **Genel:** TR/EN toggle (`Accept-Language` + `useLang`), responsive ~600 nokta seyreltme (metrik/CSV tam), empty state, error/loading state, risk disclaimer ("tavsiye değildir", "sentetik ≠ gerçek", "test tekrarı holdout'u zayıflatır").

---

## 12. API Yüzeyi (özet)

- Legacy: `/api/datasets`, `/api/runs`, `/api/features`, `/api/models`, `/api/capabilities`, `/api/feature-families`, `/api/sample-external.csv`.
- Platform `/api/v1`: `/experiments` (GET liste eksikti, eklendi; POST create), `/experiments/{id}` (+`/result`, `/logs`, `/export`, `/candidates`, `/feature-intelligence`, `/seal`, `/seal/history`, `/seal/invalidate|rotate`, `/artifacts/{name}`, `/clone`, `/run`, `/cancel`), `/search-spaces`, `/workspaces*` (+`/summary`), `/snapshots`, `/research/estimate|budget|ledger`, `/activity`, `/assistant-tasks*`, `/notebooks*` (bkz §8).
- Quant `/api` (§7), health: `/api/health`, `/ready` (planlı/tamamlanmamış kısım — PRODUCT_PLAN'da istenir).
- Envelope: quant `{success,experiment_id,data,error}`; SSE `experiment.status.changed` + notebook cell event'leri.

---

## 13. Testler ve Kalite

- `tests/`: 15 dosya; golden 21, notebooks 9, quant 7 dosya (ic/clustering/validation/stress/calibration/api/advanced), engine/platform/api/assistants/auth/validation_sprint3.
- Son durum: `pytest -q` 64 passed (TODO_NEXT) / 115 passed + 3 ledger hatası (`service.ledger()` dict vs list — test tarafı `["items"]` fix bekler) / sprint 48 passed quant; `vite build` + `tsc -b` yeşil.
- Kapsam: CSV hataları, causal feature, HMM filtresi, maliyet, kronolojik split, upload→train→export→history, seal/budget/isolation, notebook upload→run→SSE→download+404 guard, takvim/gap/PSR (kısmi).
- Eksik: e2e (Playwright smoke), load (50k bar+GA bütçesi), lint (`ruff/black`, `eslint`), Sentry/structured log/request-id, backup/restore runbook.

---

## 14. Bilinen Sınırlılıklar ve Non-Goal (dürüstlük notları)

- Notebook'ların birebir koşturucusu değil; TFT, FRED/Dukascopy çekme, teori/makro feature, 25-uzman havuzu, MAIN_14/THEORY_11, tez tabloları yok.
- `__available_at` kullanıcı beyanı; vintage/revision/provider/survivorship yok; snapshot `unverified/not supplied` gizlenmez.
- Rejim numarası ekonomi etiketi değil; test hedef getirisi açıklayıcı.
- Spread/funding ayrı model yok (tek maliyet alanı); kaldıraç/floor basitleştirilmiş; fill/latency/stop yok.
- Tek worker, in-memory job, restart keser; dağıtık Redis/S3, RQ/Celery/ARQ, Docker/compose, Postgres prod-doğrulama yok.
- Auth tek key, OAuth/OIDC/RBAC/tenant/RLS/billing/KVKK silme yok; CORS/rate-limit/input-limit denetimi eksik.
- İstatistik: PSR/Deflated Sharpe/PBO/sensitivity/robustness raporu yok (salt-okunur rapor planlı).
- Quant: stacking tam yok, Optuna/Bayesian yok, conformal yok, CPCV/nested-tam yok, TFT/LSTM yok, online learning yok, drift ayrı metrik değil.
- Notebook: interaktif JupyterLab, schedule, GPU select, version diff, marketplace, collab, promotion workflow, remote kernel yok.
- MCP approval, prompt-to-spec DSL/LLM adapter, Champion/Challenger, deployment bridge yok.

---

## 15. Product Planı Özeti (sprintlere bölünmüş)

- **F0:** Ürün tipi seç (A Local Pro Tool önerilir, B SaaS faz 4'e).
- **Faz 1 (1-2hf):** DB-backed lab borçları (feature/candidate `result.json` bağı, search-space selector, lineage writer, workspace tutarlılığı) — çoğu TODO_NEXT'te yapıldı olarak işaretli, faz-1 DoD: `result.json` silinse listeler DB'den.
- **Faz 2 (2-3hf):** Dockerfile/compose, Alembic prod-safe, S3 adapter, kuyruk (RQ/Celery/ARQ), cancel semantiği, auth/guard/audit, Sentry/health/ready, CI (pytest+tsc+vite+ruff/black+eslint+Playwright), load smoke.
- **Faz 3 (2-4hf):** Takvim/gap/PSR/parity/provenance/risk metni + golden testler.
- **Faz 4 (4-6hf):** Tenant→workspace→experiment, RLS/isolation, billing/entitlement, backup/KVKK, MCP approval.
- **Faz 5:** Gerçek multi-obj, RegimeRouter inference, Optuna/Bayesian/stacking, TFT/LSTM, prompt-to-spec, Champion/Challenger.
- **DoD (v1):** temiz kurulum demo e2e, CI yeşil, sızma testi yeşil, restart/cancel dokümante, metodoloji=README=export, lisans+disclaimer+silme yolu.

---

## 16. ChatGPT'den İstenen İnceleme (önerilen prompt)

```text
Ekteki RegimeLab özellik dokümanını ve repo'yu incele:
1) Mimari riskler (tek worker, SQLite, in-memory job, workspace guard, seal/budget bütünlüğü)?
2) Quant metodoloji hataları (leakage, HMM forward-only doğruluğu, purge/embargo, cost parity, rejim-ağırlık, eşik seçimi, Sharpe yıllıklandırma)?
3) Backtest gerçekçiliği (spread/swap/slippage/latency/fill, gap/DST/tatil, margin/likidasyon)?
4) GA/optimizasyon (skaler fitness vs Pareto, overfit, seed reproducibility, budget guard)?
5) API/MCP/auth güvenliği (tek key, cross-workspace 404, notebook RCE, secret maskeleme, approval eksikleri)?
6) Test boşlukları (hangi golden/negatif/load testleri şart)?
7) Öncelikli 10 düzeltme + hızlı kazançlar (low-effort high-impact)?
Lütfen her bulguya dosya: satır + ciddiyet (Kritik/Yüksek/Orta/Düşük) + önerilen fix ver.
```

---

## 17. Dosya Referansları

- Giriş: `README.md`, `AI_ASSISTANTS.md`, `IMPLEMENTATION_STATUS.md`
- Plan: `PRODUCT_PLAN.md`, `TODO_NEXT.md`, `V2_IMPLEMENTATION_BACKLOG.md`, `v3.md`, `REGIMELAB_ASTRA_IMPLEMENTATION_SPEC*.md`, `REGIMELAB_NOTEBOOK_LAB_IMPLEMENTATION_PLAN.md`, `NOTEBOOK_LAB_UI_FIX_PLAN.md`
- Durum: `CHANGELOG.md`, `md/01_CURRENT_ARCHITECTURE.md`, `md/TASKS.md`, `md/00_PROJECT_CONTEXT.md`, `md/06_UI_SPEC.md`, `IMPLEMENTATION_STATUS.md`
- Kod: `backend/app.py`, `backend/engine.py`, `backend/platform/{schema,db,service,research,api,quant_api,worker,scope,models,families,assistants}`, `backend/quant/*`, `backend/mcp/server.py`, `frontend/src/*`, `regimelab_sdk/__init__.py`, `tests/test_*.py`
- Veri: `data/`, `notebooks/`, `*.ipynb` (orijinaller değiştirilmedi, API'den yayınlanmaz)

---

*Bu dosya otomatik tarama + doküman birleştirme ile üretildi; sayısal iddialar (test sayıları, limitler) kaynak dosyalardaki son yazana göredir. İncelemede kodla çelişki bulunursa kod esas alınmalıdır.*
