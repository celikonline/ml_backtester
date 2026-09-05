# Uygulama kapsamı

Kaynak: `REGIMELAB_ASTRA_IMPLEMENTATION_SPEC.md`. Bu dosya gereksinimlerle teslim edilen kodun ayrımını tutar.

## Bu geliştirme paketinin hedefi

- Phase 1: SQLAlchemy/Alembic deney kaydı, değişmez snapshot, sürümlü API, kalıcı job durumu, canlı SSE.
- Phase 2: ortak Pydantic specification, model/özellik kayıtları, GA özellik ve sınırlı hiperparametre seçimi, holdout/walk-forward, ayrı test.
- Phase 3: klon, lineage, 2–5 deney karşılaştırması, equity/drawdown overlay ve konfigürasyon farkları.
- Phase 4'ün alt kümesi: generation metrikleri, Pareto adayları ve feature survival.
- Phase 5'in alt kümesi: aynı REST servislerine bağlanan resmi MCP SDK adapter'ı, işlem kaydı ve compute sınırı.
- Laglı haricî veri: CSV üzerinden `macro__`, `cross_asset__`, `fx__`, `rates__` feature aileleri; her değer/değişim/getiri feature'ı bir bar gecikmeli üretilir. İsteğe bağlı `__available_at` sütunu snapshot'ta point-in-time denetimi olarak kaydedilir.

## Altyapı tercihi

Yerel ortam SQLite/WAL + SQLAlchemy kullanır; PostgreSQL `REGIMELAB_DATABASE_URL` ile seçilebilir. PostgreSQL bağlantısı ayrı ortam gerektirir ve yerel testle doğrulanmış sayılmaz. Snapshot ve artifact depolama yereldir. Tek API süreci, tek ML worker ve sınırlı kuyruk kullanılır. Dağıtık Redis/S3 altyapısı bu teslimin dışında.

## Tamamlanmış sayılmayan başlıklar

- ALFRED/vintage, exact release time, survivorship, microstructure ve cross-asset kaynakları. Yüklenen CSV'deki `__available_at` yalnızca kullanıcı tarafından sağlanan yayın zamanı denetimidir; veri sağlayıcısı/vintage doğrulaması değildir.
- TFT/LSTM, tam GA genome, Optuna, stacking, nested CV/CPCV ve conformal calibration.
- Doğal dil → specification için LLM sağlayıcısı; otomatik araştırma agent'ı.
- Çok kiracılı RBAC/OAuth, dağıtık worker ve production champion onayı.

Eski notebooklar ve `/api/runs` akışı korunur. Yeni deneyler `/api/v1/experiments` kullanır. Eski sonuçların snapshot'ı bulunmadığı için bu sonuçlara sonradan doğrulanmış snapshot atfedilmez.
