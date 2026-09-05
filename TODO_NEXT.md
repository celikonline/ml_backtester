# Kalan İşler — Handoff (2026-09-05)

Bu dosya yeni pencerede devam etmek içindir. Repo: `D:\agentic\ml`, branch `main`.
Son durum: `pytest` 64 passed, `vite build` yeşil.

## Kararlar (değiştirme)
- Local-first: Vercel uyumluluk katmanı söküldü, deploy hedefi yok.
- Yeni ekleme yok; mevcut fonksiyonlar çalışır hale getirilir.
- Cross-workspace okuma → 404 (enumeration engeli). Tekrar test bloklanmaz;
  sayaç + `POST_TEST_ITERATION_FROM` + risk bayrağı ile izlenir.
- `result.json` okuyan UI sekmeleri henüz DB'ye bağlanmadı (bilinen borç).

## P0 (2026-09-05 tamamlandı — 37 passed, `vite build` yeşil)
1. **Kaldıraç/margin uygulaması** — yapıldı: `exposure = max_leverage *
   max_position_fraction` (`backend/engine.py:fx_backtest`), tek-bar -%100
   floor + likidasyon sonrası flat (`margin_calls`/`liquidated` özeti),
   `merged_reality` kaldıraç taşır (`backend/platform/research.py`).
   Golden testler: `tests/test_backtest_golden.py` (17 test bu dosyada).
2. **CI workflow'u** — yapıldı: `.github/workflows/ci.yml`
   (`pytest tests -q` + `npm --prefix frontend run build`).

## P1
3. **Candidate Lab UI** — yapıldı (2026-09-05): `optimize` ilk-görülen
   `generation` + `parents` izler, `pareto_ranks` gerçek katmanlı rank üretir
   (`backend/platform/research.py`); `candidate_parents` tablosu + migration
   0008; `persist_candidates` iki fazlı yazar, `candidates`/`candidate`
   `parents` ile okur (`backend/platform/service.py`); Optimization Lab
   sekmesinde DB-backed aday tablosu (nesil/rank/dominance/karar/ebeveyn,
   `frontend/src/ResearchPlatform.tsx`). GA smoke: 7 aday, nesil {1,2},
   rank {0,1,2}. Borç: aday-satır `metrics` toplu validasyon skorudur;
   fold-detay yalnızca `result.json`'dadır.
4. **Lineage grafiği UI** — yapıldı (2026-09-05): klon-sırası spec-diff
   sınıflandırma (`classify_lineage`, `backend/platform/service.py`) 7 tipin
   tamamını yazar — saf klon `CLONED_FROM`, seal-açılmış ebeveyn
   `POST_TEST_ITERATION_FROM` (öncelikli), özellik daraltma
   `FEATURE_REDUCED_FROM`, validasyon değişimi `VALIDATION_CHANGED_FROM`,
   rejim değişimi `REGIME_SPECIALIZED_FROM`, model-altküme/kapasite-sıkma
   `REGULARIZED_FROM`, diğer tek-bölüm aramalar `AUTO_REFINED_FROM`.
   Detail'de Köken sekmesi: 3-derinlik BFS graf, düğüm başına test
   Sharpe/getiri/düşüş + val→test farkı (`frontend/src/ResearchPlatform.tsx`).
5. **DB-backed Feature Lab** — yapıldı (2026-09-05): `feature_analysis`
   ölçülen `missingness` + geliştirme-verisi rejim IC'leri üretir
   (`backend/platform/research.py`); migration 0009
   (`feature_regime_metrics`, `feature_selection_events`,
   `feature_redundancy_pairs`); worker survival istatistiklerini de yazar,
   `GET .../feature-intelligence` paketi sunar (`service.py`/`api.py`/MCP);
   Features sekmesi DB tablosunu gösterir (eksik/rejim-IC/seçim-sıklık +
   korelasyon çiftleri), kayıt yoksa `result.json` görünümüne düşer.
   Smoke: gecikmeli-yayın maskelemesinde lag özellikleri %10-20 eksik.
6. **Wizard'da search-space seçici** — yapıldı (2026-09-05): 1. adımda
   space dropdown (`GET /search-spaces`, workspace kapsamlı); seçim
   modeller/özellikler/optimizasyon-sınırları/rejim-eşiği spec'e kopyalar ve
   `search_space_id` bağlar (backend create'te aynı kontratı uygular);
   elle düzenleme bağı keser (sessiz ezme yok). Borç: lookback aralığı
   space kontratında yok (backend de uygulamıyor).

## P2
7. **Gerçek multi-objective optimizer** — yapıldı (2026-09-05): GA skaler
   fitness'la seçmeye devam eder (turnuva skaler ister), ancak her aday
   6'lı objective vektörü taşır (`sharpe/return/sortino/max_drawdown↑`,
   `turnover/cost_bps_estimate↓`, yönler `OBJECTIVE_DIRECTIONS`'ta) ve
   feasibility `max_drawdown + min_trades + max_exposure` kısıtlarını
   uygular (`constraint_violations` ile, `backend/platform/research.py`).
   Wizard 3. adımda min-işlem/maks-pozisyon girdileri. Borç: NSGA-II tarzı
   rank+crowding seçimi yok; Pareto cephesi hâlâ getiri-kalite 3'lüsünde.
8. **RegimeRouter** — yapıldı (2026-09-05): HMM fiti optimize öncesine
   taşındı (dev-only, causal; test raporu aynı fiti kullanır).
   `RegimeRouter` her adaya validasyon-dilim rejim metrikleri + en-kötü-rejim
   düşüşü + kapsam yazar (`backend/platform/research.py`); seçim baskısı
   `max_worst_regime_drawdown` gate'iyle olur (ihlal → infeasible).
   Regimes sekmesinde en-iyi-aday rejim tablosu. Borç: inference-anında
   rejim-bazlı model/strateji yönlendirmesi yok (bilinçli; execution değişir).
9. **Tatil takvimi + price-gap equity testi** — yapıldı: `fx_holidays_for_year`
   (1 Oca, Good Friday, Easter Monday, 25/26 Ara + Cumartesi→Cuma/Pazar→Pzt
   gözlenen gün, `backend/engine.py`); `audit_calendar` boşluğu
   [önceki, güncel] aralığı tatil kapsıyorsa `holiday_gaps` sayar
   (Pzt-dönüş ve tatil-haftasonu yanlış sınıflanmaz; reject yok, audit).
   Golden testler: takvim tarihleri, tatil/haftasonu/kaynak-delik ayrımı,
   +%2 haftasonu sıçramasının equity'den aynen geçişi (maliyetli + finansmanlı).

## P3 / v3 artıkları
10. **DSL/prompt-to-spec, approval policy, RBAC** — doğrulandı: MCP'de
    `validate_experiment_spec` (`POST /research/estimate`: policy + maliyet +
    risk, yaratmadan) zaten var; eksik kalan `request_test_unseal` onay akışı,
    approval seviyeleri, auth tek API key/localhost (ürün kararı gerekir).
11. **P3 fazları** — ALFRED/vintage veri, PSR/PBO, Optuna, TFT, Champion/
    Challenger, dağıtık worker: hepsi `planned` (`GET /capabilities`).
    Veri/altyapı gerektirir, girilmedi.
12. **v3 artıkları** — yapıldı: audit tablosunda workspace kolonu
    (migration 0011, details/scope'tan doldurulur, Activity'de WS sütunu).
    Kalan: legacy CSV listesi (`/api/datasets`) scope'suz; `?workspace=`
    yerine `/w/{id}` path routing; tenant modeli yok (ürün kararı gerekir).
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
