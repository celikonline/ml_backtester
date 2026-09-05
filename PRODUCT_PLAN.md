# RegimeLab — Product Planı (v1.0)

Tarih: 2026-09-06
Kaynaklar: `README.md`, `IMPLEMENTATION_STATUS.md`, `TODO_NEXT.md`, `V2_IMPLEMENTATION_BACKLOG.md`, `v3.md`
Hedef: local-first prototipten kurulabilir, güvenilir, tek-kullanıcıdan çok-kullanıcılı ürüne geçiş.

## 0. Mevcut Durum Özeti

- Mimari: `backend/app.py` (FastAPI) + `backend/platform/` (experiment registry) + `backend/engine.py` (backtest) + `frontend/src/ResearchPlatform.tsx` (tek sayfa React).
- Çalışan: immutable experiment, snapshot hash, holdout/walk-forward, GA, sealed test epoch, research budget ledger, workspace scope (query param), MCP adapter.
- Borç: tek worker (`ThreadPoolExecutor(max_workers=1)`), in-memory job, SQLite/WAL local, auth tek API key, legacy `/api/runs` ve `/api/datasets` scope'suz, Feature/Candidate sekmeleri kısmen `result.json` bağımlı, lineage writer eksik, optimizer tek skaler fitness, HMM report-only.
- Kalite: `tests/` 4 dosya (~40 test), CI sadece `pytest + vite build`, e2e/load/lint yok.

## 1. Ürün Kararı (F0 — 1 gün, önce yapılmalı)

- [ ] Product tipi seç: A) Local Pro Tool (tek kullanıcı, kurulumlu) / B) Hosted SaaS (çok kullanıcı).
- [ ] Bu karar olmadan deploy/auth/billing işine girme.
- Kabul: `README.md` ilk paragraf hangi ürün olduğu yazar, desteklenmeyen tip "non-goal" olarak işaretlenir.

Öneri: Önce A'yı product yap, B'yi faz 4'e bırak.

## 2. Faz 1 — Fonksiyonel Borç Kapatma (1–2 hafta)

Amaç: Mevcut vaat edilen akışı gerçekten bitirmek. Yeni model/metrik ekleme yok.

### 2.1 DB-backed Lab sekmeleri
- [ ] `feature_regime_metrics`, `feature_selection_events` tabloları + migration + `service.py:persist_feature_analysis` düzelt (`missingness` hardcoded `0.0` kaldır).
- [ ] Candidate satır `metrics` + fold-detay ayrımı: satır toplu validasyon, detay `result.json`/artifact linki. UI'da bunu açık yaz.
- [ ] `result.json` okuyan tüm UI sekmelerini DB kaynağına bağla (`TODO_NEXT.md:11` borcu).
- Kabul: `result.json` silinse bile Candidate/Feature listeleri DB'den render olur.

### 2.2 Search-space selector (wizard step 1)
- [ ] Backend+MCP hazır contract'ı wizard'a bağla (`ResearchPlatform.tsx` step 1).
- [ ] `OptimizationSpec` içine gömülü ayar yerine sürümlü `SearchSpaceDefinition` seçimi.
- Kabul: REST/MCP/wizard aynı contract'ı kullanır, geçersiz spec `policy_rejected` olur.

### 2.3 Lineage writer + graf
- [ ] `service.py:clone` civarı eksik 5 relation writer'ı ekle: `AUTO_REFINED_FROM`, `FEATURE_REDUCED_FROM`, `REGULARIZED_FROM`, `VALIDATION_CHANGED_FROM`, `REGIME_SPECIALIZED_FROM`.
- [ ] `experiment_edges` tablosu varsa doldur, yoksa migration ekle. Lineage graf UI (node: Sharpe/return/DD + validation→test degradation).
- Kabul: klon/zincir deneylerde graf boş dönmez.

### 2.4 Workspace tutarlılığı
- [ ] Legacy `/api/datasets` ve `/api/runs` için scope kararı: ya workspace'e bağla ya `deprecated` işaretle.
- [ ] `?workspace=` → `/w/{id}` path routing'e geçiş planı (v3 §10). En azından refresh-safe kalmalı.
- [ ] Audit tablosuna `workspace_id` kolonu + migration.
- Kabul: cross-workspace erişim 404/403 ile backend'de engellenir, isolation testi yeşil.

## 3. Faz 2 — Product Hardening (2–3 hafta)

### 3.1 Deploy & veri kalıcılığı
- [ ] `Dockerfile` + `docker-compose.yml` (api, worker, postgres, redis opsiyonel).
- [ ] Alembic migration zinciri prod-safe: backfill + `NOT NULL` + rollback testi.
- [ ] `REGIMELAB_DATABASE_URL` (Postgres) gerçek ortamda doğrula. Artifact/snapshot için S3-uyumlu storage adapter (local fallback'lı).
- [ ] `data/` dosya yazan legacy akışı object-storage soyutlaması arkasına al.
- Kabul: sıfırdan `docker compose up` ile temiz kurulum + demo deney çalışır.

### 3.2 Job/worker
- [ ] Tek worker → kuyruk (RQ/Celery/ARQ). Job persist, restart-safe resume/fail, progress SSE + polling fallback.
- [ ] Cancel semantiği netleştir: "adım sonu iptal" UI'da yazar.
- [ ] Eşzamanlılık: kullanıcı başına limit, global kuyruk limiti, `policy_rejected` ile uyumlu.
- Kabul: sunucu restartında `running` job `failed/interrupted` olarak işaretlenir, sonuç kaybolmaz.

### 3.3 Auth, guard, audit
- [ ] Local mod: tek API key + localhost bind korunur.
- [ ] Hosted mod (Faz 4'e hazırlık): OAuth/OIDC iskeleti, RBAC rolleri (Owner/Admin/Researcher/Viewer), workspace guard middleware'de enforce.
- [ ] API key rotation, rate-limit, CORS allowlist, input size limit denetimi.
- [ ] Audit: `WORKSPACE_CREATED/UPDATED/ARCHIVED/SWITCHED`, experiment create/clone/run, seal open/invalidate/rotate hepsi `workspace_id` ile.
- Kabul: sadece frontend filtresiyle veri sızmaz (negatif test).

### 3.4 Gözlemlenebilirlik & kalite kapısı
- [ ] Structured JSON log, request-id, Sentry (backend+frontend), `/api/health` + `/ready` (db migration durumu).
- [ ] CI genişlet: `pytest -q` + `tsc -b` + `vite build` + `ruff/black` + `eslint` + Playwright smoke (login → dataset yükle → deney çalıştır → sonuç gör).
- [ ] Load smoke: 50k bar + 32 pop/20 gen GA süre/bellek bütçesi ölç.
- Kabul: `main`'e merge için CI yeşil zorunlu, flaky test karantinaya alınır.

## 4. Faz 3 — Quant Güvenilirliği (2–4 hafta, product için kritik)

Sıralama önemli: önce doğruluk, sonra yeni model.

- [ ] Takvim: resmi tatil takvimi (FX), weekend/midweek gap ayrımı reject değil flag + test. `audit_calendar` → engine kuralına taşı.
- [ ] Price-gap jump testi: gap bar'ında equity/slippage davranışı golden test.
- [ ] Maliyet modeli parity: `merged_reality` validasyon ve final testte aynı yol — broker ifadesiyle dokümante et (spread/komisyon/slippage/swap/Wed triple). Fill/latency/stop yoksa "yok" diye yaz.
- [ ] İstatistik: PSR, Deflated Sharpe, PBO, parameter sensitivity raporu (en azından salt-okunur rapor).
- [ ] Data provenance dürüstlüğü: `__available_at` = kullanıcı beyanı, vintage/revision/provider yok. UI + docs'ta `unverified / not supplied` aynen kalmalı. ALFRED/gerçek PIT entegrasyonu Faz 5'e.
- [ ] Risk metni: "yatırım tavsiyesi değildir", "sentetik veri gerçek performans değildir", "test tekrarı holdout'u zayıflatır" uyarıları UI+export CSV'ye.
- Kabul: `tests/test_backtest_golden.py` + yeni takvim/gap/PSR testleri CI'de; metodoloji ekranı ile kod aynı sayıyı söyler.

## 5. Faz 4 — SaaS'a Açılma (karar verilirse, 4–6 hafta)

- [ ] Tenant modeli + `tenant → workspace → experiment` zinciri, `/w/{id}` routing tam geçiş.
- [ ] Postgres RLS veya app-level isolation + index'ler (`idx_experiments_workspace_id` vb.).
- [ ] Billing/entitlement iskeleti: plan → budget limiti eşleme (GPU saati/deney/aday kotası).
- [ ] Operasyon: backup/restore runbook, log retention, KVKK/GDPR silme akışı (workspace silme = archive + veri silme talebi).
- [ ] MCP V2 approval: `request_test_unseal` doğrudan erişim vermez, approval request açar. `AUTO_READ / APPROVAL_REQUIRED_TO_RUN / AUTO_RUN_WITHIN_BUDGET` seviyeleri.
- Kabul: iki tenant birbirinin deney/dataset/seal/budget'ını göremez (e2e negatif test).

## 6. Faz 5 — Araştırma Derinliği (ürün sonrası, opsiyonel)

- [ ] Gerçek multi-objective optimizer (objective vektörü + constraint + Pareto frontier UI).
- [ ] `RegimeRouter`: HMM'i report-only'den seçime sok (regime stability, worst-regime DD, coverage).
- [ ] Optuna/Bayesian, stacking, ensemble weights.
- [ ] TFT/LSTM model havuzu (GPU gereksinimiyle birlikte).
- [ ] Prompt-to-spec DSL + LLM adapter (domain'den izole).
- [ ] Champion/Challenger + deployment bridge.

Bunlar olmadan v1 product çıkar; v1'e blok koyma.

## 7. Definition of Done (v1 product)

- [ ] Temiz makinede `setup + start` veya `docker compose up` ile demo uçtan uca çalışır.
- [ ] `pytest -q` + `vite build` + lint + Playwright smoke yeşil.
- [ ] Cross-workspace/tenant sızma testi yeşil.
- [ ] Restart/cancel/kuyruk davranışları dokümante ve testli.
- [ ] Metodoloji ekranı + README + export aynı protokolü anlatır; `unverified` alanlar gizlenmez.
- [ ] Lisans + risk disclaimer + veri silme yolu mevcut.

## 8. Bilinen Non-Goal (v1)

- Gerçek PIT/vintage veri sağlayıcı entegrasyonu, exact release-time garantisi.
- Canlı trading bağlantısı / emir iletimi.
- Dağıtık GPU cluster, nested CV/CPCV tam otomasyonu.

## 9. Dosya Haritası

- `backend/platform/schema.py`, `db.py`, `service.py`, `research.py`, `api.py` — Faz 1–3 ana iş.
- `backend/engine.py`, `tests/test_backtest_golden.py` — Faz 3.
- `backend/mcp/server.py` — Faz 1.2 + Faz 4 approval.
- `frontend/src/ResearchPlatform.tsx`, router, API client — Faz 1.2/1.3/2.4.
- `alembic.ini`, `backend/migrations/` — her fazda migration zorunlu.
