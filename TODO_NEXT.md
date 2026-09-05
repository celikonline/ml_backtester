# Kalan İşler — Handoff (2026-09-05)

Bu dosya yeni pencerede devam etmek içindir. Repo: `D:\agentic\ml`, branch `main`.
Son durum: `pytest` 31 passed, `vite build` yeşil. **Commit'lenmemiş değişiklikler var**
(Vercel-revert turu: requirements birleştirme, optional-model sökümü, README).

## Kararlar (değiştirme)
- Local-first: Vercel uyumluluk katmanı söküldü, deploy hedefi yok.
- Yeni ekleme yok; mevcut fonksiyonlar çalışır hale getirilir.
- Cross-workspace okuma → 404 (enumeration engeli). Tekrar test bloklanmaz;
  sayaç + `POST_TEST_ITERATION_FROM` + risk bayrağı ile izlenir.
- `result.json` okuyan UI sekmeleri henüz DB'ye bağlanmadı (bilinen borç).

## P0
1. **Kaldıraç/margin uygulaması** — `BacktestRealityConfig`'te alanlar var
   (`backend/platform/schema.py`), hesapta kullanılmıyor. `fx_backtest`
   (`backend/engine.py`) içine pozisyon ölçekleme + margin guard + golden test.
2. **CI workflow'u** — `.github/` boş. `pytest tests -q` + `npm --prefix frontend run build`.

## P1
3. **Candidate Lab UI** — backend hazır (`GET /experiments/{id}/candidates`
   DB'den okur, `backend/platform/api.py:181`). Optimization Lab sekmesine aday
   tablosu. `generation` hep `None`, `pareto_rank` bayrak
   (`backend/platform/service.py` persist_candidates) — gerçek rank + parent
   kaydı için `candidate_parents` tablosu + migration gerekir.
4. **Lineage grafiği UI** — `GET .../lineage` API'si var ama 7 relation
   type'tan 5'i hiç yazılmıyor (`AUTO_REFINED_FROM` vb., `service.py:clone`
   civarı). Önce writer'lar, sonra graf.
5. **DB-backed Feature Lab** — sekme `result.json` okuyor
   (`frontend/src/ResearchPlatform.tsx` features tab). Eksik:
   `feature_regime_metrics` / `feature_selection_events` tabloları,
   `missingness` hardcoded `0.0` (`service.py:persist_feature_analysis`),
   redundancy/survival sadece `result.json`'da.
6. **Wizard'da search-space seçici** — backend+MCP hazır, UI'da yok
   (`frontend/src/ResearchPlatform.tsx` step 1).

## P2
7. **Gerçek multi-objective optimizer** — GA tek skaler fitness'ta
   (`backend/platform/research.py:optimize`). Objective vektörü +
   min-trades/max-exposure constraint'leri.
8. **RegimeRouter** — HMM bilerek report-only (`research.py` notları).
   Rejim-bazlı değerlendirme/yönlendirme yok; string repo'da geçmiyor.
9. **Tatil takvimi + price-gap equity testi** — `audit_calendar`
   (`backend/engine.py`) audit seviyesinde; resmi tatiller ve gap-jump testi yok.

## P3 / v3 artıkları
10. **DSL/prompt-to-spec, approval policy, RBAC** — MCP ince REST geçişi;
    `request_test_unseal` yok; auth tek API key/localhost.
11. **P3 fazları** — ALFRED/vintage veri, PSR/PBO, Optuna, TFT, Champion/
    Challenger, dağıtık worker: hepsi `planned` (`GET /capabilities`).
12. **v3 artıkları** — legacy CSV listesi (`/api/datasets`) scope'suz;
    `?workspace=` yerine `/w/{id}` path routing; audit tablosunda workspace
    kolonu yok; tenant modeli yok.
13. **Backend barındırma** — local-only kararıyla ertelendi; kalıcı kullanım
    gerekirse Render/Fly/Railway + frontend Vercel.

## Tamamlananlar (referans)
- TR/EN + `Accept-Language`/`X-Workspace-Id` header'ları
- Workspaces entity, migration 0006, guard, switcher UI, `?workspace=` persist
- Seal epoch/invalidation/rotation (migration 0005), budget ledger + Risk kartı
- Per-workspace budget (migration 0007, legacy `global` devri)
- FX reality: ohlc_range spread, birleşik maliyet yolu, long/short swap,
  Wed triple, calendar audit, `tests/test_backtest_golden.py` (11 test)

## Hızlı başlangıç (yeni pencere)
```powershell
git status            # uncommitted Vercel-revert değişikliklerini gözden geçir
.\.venv\Scripts\python.exe -m pytest tests -q
npm --prefix frontend run build
.\start.ps1           # http://127.0.0.1:8000
```
