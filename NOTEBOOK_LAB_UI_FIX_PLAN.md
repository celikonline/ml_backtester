# Notebook Lab — Sayfa İncelemesi ve Düzeltme Planı

Tarih: 2026-09-06

## Uygulama durumu — 2026-09-06

Kod değişiklikleri tamamlandı. Aşağıdaki bulgular ilk incelemenin tarihsel kaydıdır; güncel durum:

- [x] Faz 0: Mevcut `notebook.css` ve import doğrulandı; durum tokenları `style.css` içine taşındı. Inspection banner'ları, dialog boyutları, log sarma ve tablo taşması düzenlendi. Açık/koyu tema ve seçili satır stilleri mevcut.
- [x] Faz 1: Workspace kapsamlı snapshot endpoint'i eklendi; UI gerçek snapshot ID ve `details.name` kullanıyor. Snapshot seçmeden çalıştırma korundu.
- [x] Faz 2: Workspace ve dosya yolu kontrolüyle artifact/`executed.ipynb` indirme eklendi. Alt klasörlerdeki artifact'ler destekleniyor; dışarıya işaret eden symlink'ler listelenmiyor. Genel Bakış'tan Yeni Versiyon yüklenebiliyor.
- [x] Faz 3: Inspection kodu ve ayrıntısı warning/critical renkleriyle gösteriliyor. Sabit UI metinleri TR/EN sözlüğüne taşındı. Sıfır saniye gösterimi, SSE GET başlıkları, event payload gösterimi, JSON nesne kontrolü ve Artifacts sekmesindeki çalıştırma seçimi düzeltildi. Workspace/notebook değişiminde eski seçimler temizleniyor.
- [x] Faz 4: `npx tsc -b` ve `npm run build` başarılı. `pytest tests/test_notebooks.py -q`: **9 geçti**. Testler geçici veritabanı/depolama ile çalıştırıldı.
- [x] Otomatik uçtan uca REST testi: upload → yeni versiyon → snapshot ile gerçek notebook execution → SSE → nested artifact ve executed notebook indirme. Yanlış workspace, eksik dosya ve path traversal için 404 doğrulandı.
- [ ] Görsel/manual tarayıcı kontrolü: Oturumda kullanılabilir tarayıcı bulunmadığından gerçekleştirilemedi. Açık/koyu tema, dar ekran ve dosya seçicilerinin görsel kontrolü bekliyor; otomatik API doğrulaması bunun yerine görsel doğrulama sayılmadı.

Doğrulamayı engelleyen mevcut çalışma alanı hatalarına da küçük düzeltmeler yapıldı: `i18n.tsx` içindeki yinelenmiş/yarım tanımlar, `ResearchPlatform.tsx` içindeki çift state tanımları ve activity response tipi, `AccountPage.tsx` icon/Promise kullanımı ve `App.tsx` API helper export'u. `auth_utils.py` içinde import sırasında çöken rastgele hex → decimal süre dönüşümü 24 saatlik JWT süresiyle değiştirildi. Önceden var olan diğer değişiklikler korundu.

Notebook upload sonrası görünen `405 Method Not Allowed` için eksik `GET /api/v1/experiments` liste endpoint'i eklendi. Upload isteği aslında başarılı olduğu halde bu takip isteği hatayı genel upload banner'ında gösteriyordu.

---

Bu doküman, `frontend/src/NotebookLab.tsx` sayfasının backend (`api.py`, `backend/platform/notebooks/*`) ve stil katmanıyla birlikte gözden geçirilmesinden çıkan bulguları ve öncelikli düzeltme planını içerir.

Kapsam:

- `frontend/src/NotebookLab.tsx` (visual + logic + backend uyumu)
- `backend/platform/notebooks/service.py` (run/snapshot/secret kontratı)
- `backend/platform/api.py` (REST kontratı)
- `frontend/src/style.css`, `frontend/src/platform.css` (tasarım tokenları)

---

## 1. Bulgular

### K1 — Kritik: Sayfanın CSS'i yok

`NotebookLab.tsx` içindeki tüm `nb-*` sınıfları (`nb-grid`, `nb-card`, `nb-table`, `nb-tabs`, `nb-dialog`, `nb-live-run`, …) hiçbir stylesheet'te tanımlı değil. Yalnızca global `style.css`'teki paylaşılan sınıflar (`.badge`, `.primary`, `.secondary`, `.alert`, `.text-button`, `.icon-button`, `.spin`) geçerli. Sayfa düz HTML gibi görünür; tüm layout kayıp.

Tespitler:

- `NotebookLab.tsx` hiç bir CSS dosyası import etmiyor.
- `nb-*` içeren hiçbir kural `style.css` / `platform.css` / `assistants.css` / `workspace.css` içinde yok.
- `statusColor()` fonksiyonu `var(--color-emerald)`, `--color-sky`, `--color-amber`, `--color-rose`, `--color-muted` kullanıyor ama bu değişkenler tanımlı değil (tanımlı tokenlar: `--muted`, `--border`, `--green`, `--panel`). Durum renkleri fallback'e düşer.
- Runs tab'daki seçili satır vurgusu `.selected-row` sınıfı da tanımsız.

### K2 — Kritik: Run dialog dataset/snapshot seçimi bozuk

`loadAll()` snapshot yerine `/datasets` (Data Hub engine setleri) çekiyor:

```ts
const [nbs, ev, snaps] = await Promise.all([
  request<Notebook[]>(`/workspaces/${wsId}/notebooks`),
  request<Experiment[]>(`/experiments?workspace_id=${wsId}`),
  request<Snapshot[]>(`/datasets`),            // yanlış kaynak
]);
```

Kullanıcı dataset seçtiğinde `dataset_snapshot_id` olarak **dataset id** gönderiliyor; backend `create_run` içinde bu değeri `dataset_snapshots` tablosunda arıyor:

```py
select(snapshots).where(snapshots.c.id == dataset_snapshot_id)
```

Snapshot id'leri `uid()` (UUID) olarak üretiliyor; dataset id'lerinden tamamen farklı. Sonuç: seçim yapıldığında run her zaman `Dataset snapshot bulunamadı` (404) ile başarısız olur.

Ek sorunlar:

- Snapshot listeleyen REST endpoint yok (`/datasets` snapshot değil).
- `Snapshot` arayüzü TypeScript'te ne `/datasets` ne de `dataset_snapshots` shape'iyle uyumlu.

### K3 — Yüksek: Artifact indirilemiyor

Notebook run artefakt listesi sunuluyor (`collect_artifacts`) ama:

- İndirme için backend endpoint yok (yalnızca `get_run_artifacts` listesi var).
- UI'daki artifact satırları tıklanabilir değil; download denenmiyor.
- Experiment tarafında karşılığı var: `GET /experiments/{id}/artifacts/{name}`.

### M4 — Orta: "Yeni Versiyon" akışı yok

Backend hazır: `POST /workspaces/{ws}/notebooks/{id}/versions`. Detail ekranında versiyon yükleme aksiyonu yok (plan: "Actions: Run, Clone, New Version, Archive").

### M5 — Orta: Inspection uyarıları hata olarak gösteriliyor

Upload sonrası `inspection.issues` kırmızı error banner'a basılıyor; `severity` (warning/critical) bilgisi kayboluyor. Uyarıların amber bilgi olarak ayrıştırılması gerekir.

### M6 — Orta: i18n yok

Notebook Lab tüm metinleri Türkçe hardcode ediyor; uygulama `useLang()` + TR/EN toggle sunduğu halde bu sayfa dile duyarsız.

### L7 — Düşük

- Artifacts tab yalnızca seçili run'ın artefaktlarını gösterir; plan tüm run'lar üzerinden listeleme öngörüyor.
- SSE fetch'i GET isteğinde `Content-Type: application/json` gönderir (zararsız ama temizlenebilir).
- `fmtDuration(0)` `—` döndürür (gerçek 0 saniye de dahil).
- Secrets tab'da "Açıklama" sütunu `description` yerine güncellemeyi gösterir (başlık tutarsız değil ama zayıf).

## 2. Çözüm Sırası

### Faz 0 — Görünüm (K1)

- `frontend/src/notebook.css` oluştur; `--green`, `--border`, `--panel`, `--muted` tokenlarını ve `[data-theme='light']` karşılıklarını kullanarak tüm `nb-*` sınıflarını tanımla.
- `NotebookLab.tsx` içinde `import './notebook.css'` ekle.
- `statusColor()`'u tanımlı tokenlara çevir (DOĞRU renkler: COMPLETED→`--green`, RUNNING/PREPARING→sky, QUEUED→amber, FAILED/TIMEOUT→rose, diğer→muted); gerekli `--color-*` değişkenlerini `style.css` içinde tanımla.
- `.selected-row` stilini ekle.

### Faz 1 — Run doğrulanabilirliği (K2)

- Backend: `GET /workspaces/{workspace_id}/snapshots` endpoint ekle → `dataset_snapshots` tablosundan workspace kapsamlı liste (id, sha256, details, created_at).
- Frontend: `loadAll()`'u bu endpoint'e bağla; `Snapshot` tipini gerçek shape'e göre düzelt; run dialog'da snapshot adını `details.name` ile göster.
- Run dialog'da snapshot seçilmediğinde "Exploratory / snapshot yok" davranışı korunur.

### Faz 2 — Artifact + Versiyon (K3, M4)

- Backend: `GET /workspaces/{ws}/notebook-runs/{run_id}/artifacts/{name}` download endpoint (`FileResponse`, workspace scope + path guard).
- Frontend: artifact satırlarına indirme düğmesi; detail sayfasında "Yeni Versiyon" dosya yükleme.

### Faz 3 — Deneyim & i18n (M5, M6, L7)

- Inspection sonuçlarını severity'e göre ayrı bilgi banner'ına taşı (kod + detail).
- Tüm sabit metinleri `i18n.tsx` dict'ine taşı; `t(...)` kullan.
- `fmtDuration(0)`, SSE header, Artifacts tab run seçimi.

### Faz 4 — Doğrulama

- `npx tsc -b` (frontend typecheck)
- `npm run build`
- `pytest tests/test_notebooks.py`
- Manuel kontrol: upload → versiyon → run (snapshot ile) → canlı logs → executed.ipynb / artifact indirme.
