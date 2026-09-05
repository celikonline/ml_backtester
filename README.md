# Regime Lab

EUR/USD araştırması için **React + TypeScript** arayüzü ve **Python/FastAPI** hesaplama servisi. CSV yükleme, üç uzman modelin eğitimi, Gaussian HMM, doğrulamada rejim ağırlıkları, maliyetli backtest ve kalıcı deney geçmişi içerir.

## Deney platformu

Ana ekran artık sürümlü bir deney platformu içerir. Her çalışma önce Experiment Specification olarak kaydedilir, verinin SHA-256 hash'i ile snapshot alınır ve sonra ayrı worker sürecinde çalışır. Çalıştırılan experiment tekrar koşturulamaz; varyasyon oluşturmak için **Klonla** kullanılır.

- Yerelde SQLite/WAL + SQLAlchemy/Alembic kayıt defteri; `REGIMELAB_DATABASE_URL` ile PostgreSQL bağlantısı.
- Holdout veya gap'li expanding-window walk-forward doğrulama, kilitli test ve canlı SSE ilerlemesi.
- Ridge, Random Forest, Histogram Gradient Boosting, XGBoost, LightGBM; genetik özellik/model/sınırlı parametre seçimi, Pareto adayları ve feature survival.
- Deney klonlama, lineage, 2–5 deney karşılaştırması, equity overlay, ayar ve özellik farkları.
- `/api/v1` REST ve aynı domain servislerine bağlanan MCP adapter'ı.

Kapsam ve harici veri gerektiren yöntemlerin durumu: [IMPLEMENTATION_STATUS.md](D:/agentic/ml/IMPLEMENTATION_STATUS.md).

## Çalıştırma

Bu bilgisayarda `.venv`, Node bağımlılıkları ve üretim derlemesi hazırlanmıştır:

```powershell
.\start.ps1
```

Alternatif: `start.cmd` dosyasına çift tıklayın. Tarayıcıda **http://127.0.0.1:8000** adresini açın. Durdurmak için terminalde `Ctrl+C` kullanın. API ve React aynı yerel sunucudan sunulur. API belgesi: `/docs`; yeni platform uçları `/api/v1`, şeması `/api/v1/specification/schema` adresindedir.

Başka bir bilgisayarda Python **3.11/3.12** ve Node **20.19+** kurduktan sonra:

```powershell
.\setup.ps1 -Python 'C:\Python312\python.exe'
.\start.ps1
```

`requirements.lock.txt` ve `frontend/package-lock.json` test edilen sürümleri sabitler. `requirements.txt` doğrudan bağımlılıkların desteklenen aralıklarını içerir. Sunucu sadece `127.0.0.1` adresine bağlanır; uygulama yerel, tek kullanıcı içindir.

## Kullanım

1. **Yeni deney** ile sentetik veri üzerinde akışı deneyin veya **Veri merkezi** üzerinden CSV yükleyin.
2. Veri seti, bar periyodu, 2–5 HMM durumu, sermaye, tek yön maliyeti ve eğitim oranını seçin.
3. **Eğitimi ve backtesti başlat** düğmesini kullanın. Günlükte gerçek hesaplama aşamaları görünür; iptal mevcut eğitim adımı bitince uygulanır.
4. Test sermaye eğrisi, düşüş, uzman karşılaştırması ve rejim ağırlıklarını inceleyin.
5. **CSV** düğmesinden tam bar sonuçlarını indirin; **Deney geçmişi** ile önceki çalıştırmaları açın.

## Vercel dağıtımı

Kök dizindeki `vercel.json`, Vite frontend derlemesini ve `api/index.py` içindeki FastAPI girişini yapılandırır. Vercel projesini bu deponun kök dizinine bağlayın; Build/Install ayarları dosyadan otomatik alınır. `/api/v1` uçlarını uzaktan kullanmak için Vercel Project Settings → Environment Variables bölümünde `REGIMELAB_API_KEY` tanımlayın ve frontend oturumunda aynı anahtarı girin. Vercel Functions geçici dosya sistemi kullandığından kalıcı veri için `REGIMELAB_DATABASE_URL` ve uygun harici depolama yapılandırması gerekir.

Yeni akışta üstteki **Yeni deney** düğmesi altı adımlı wizard'ı açar. Taslağı kaydedin, experiment detayında specification'ı gözden geçirin ve ayrı **Çalıştır** düğmesiyle başlatın. GA yalnızca geliştirme/verifikasyon dönemini görür; aday dondurulduktan sonra test sadece bir kez ölçülür. Deneyler ekranında 2–5 tamamlanmış kayıt seçerek karşılaştırma yapabilirsiniz.

MCP stdio server, uygulama çalışırken şu komutla başlatılır:

```powershell
.\.venv\Scripts\python.exe -m backend.mcp.server
```

MCP yalnızca domain araçları sağlar: deney oluşturma/çalıştırma/durum, karşılaştırma ve sonuç okuma. Ham Python veya SQL aracı yoktur. `REGIMELAB_API_KEY` tanımlanırsa REST ve MCP aynı Bearer anahtarını kullanır.

CSV: virgülle ayrılmış, `Timestamp,Open,High,Low,Close` sütunları; büyük/küçük harf önemli değildir. Tarih sütunu `date`, `datetime`, `time` olabilir. ISO 8601 tarihleri önerilir; saat dilimi yoksa UTC kabul edilir. Zaman damgası bar başlangıcını göstermelidir. En az 400, en fazla 200.000 satır ve 25 MB. Eksik, sonsuz, sıfır/negatif, tekrarlanan tarih veya tutarsız OHLC değerleri reddedilir. Küçük zaman aralığına yapay veri üretilmez; büyük aralığa OHLC birleştirmesi yapılır. Birleştirme sonrasında da 400 bar gerekir. Başlangıç/bitişte eksik oluşmuş birleştirilmiş barları yüklemeden önce çıkarmanız önerilir.

### Laglı makro ve cross-asset CSV sözleşmesi

Notebooklardaki laglı yaklaşımı kullanmak için OHLC sütunlarının yanına sayısal haricî serileri ekleyin. Tanınan ad önekleri `macro__`, `cross_asset__`, `fx__` ve `rates__` şeklindedir. Örneğin `macro__policy_rate` için yayın anını UTC ile `macro__policy_rate__available_at` sütununda verin. Platform değer, değişim ve getiri feature'larını **en az bir bar gecikmeyle** üretir; yayın anı bar zamanından sonraysa o gözlemi kullanmaz.

```csv
Timestamp,Open,High,Low,Close,macro__policy_rate,macro__policy_rate__available_at,cross_asset__dxy,cross_asset__dxy__available_at
2024-01-02T00:00:00Z,1.0940,1.0948,1.0935,1.0944,5.50,2024-01-01T19:00:00Z,102.10,2024-01-01T23:00:00Z
```

`/api/sample-external.csv` ya da Veri merkezi ekranındaki **Laglı veri örneği** bu şemayı sentetik değerlerle indirir. `__available_at` yoksa seri yine bir bar gecikmeli kullanılabilir, fakat snapshot bunu `unverified` olarak işaretler. Vintage/revision, sağlayıcı kimliği ve survivorship kanıtı bu CSV sözleşmesinin dışında kalır; bunlar gerçek bir point-in-time veri kaynağından ayrıca sağlanmalıdır.

Sentetik veri, sabit tohumla üretilmiş 3.000 adet dört saatlik bardır. Piyasa verisi veya notebookların kaydedilmiş performansı değildir. Grafikler yalnızca tamamlanmış deneyin hesaplanmış sonuçlarını gösterir.

## Notebook incelemesi ve kapsam

| Kaynak | İçerik | Bu uygulamadaki karşılığı |
|---|---|---|
| `optimusprime.ipynb` (76 hücre) | Teknik göstergeler, PyTorch/TFT mimari denemeleri, fiyat tahmini ve backtest | OHLC verisi ve teknik özellik yaklaşımı |
| `tezmodelfinal (1).ipynb` (66 hücre) | Dukascopy FX, FRED/YFinance makro veriler, teori uzmanları, XGB/LGBM/HGBM, ensemble havuzları, HMM ve tez raporları | Uzman birleştirme, rejim analizi ve sonuç karşılaştırması |

Başlangıç klasöründe yalnızca iki notebook vardı. `eurusd_cleaned.csv`, model checkpointleri ve makro veriler yoktu. Notebooklar tekrar eden alternatif hücreler, hücreler arası durum bağımlılıkları, GPU varsayımları ve harici ağ bağımlılıkları içeriyor. Kaynaklar değiştirilmedi ve doğrudan/örtülü çalıştırılmıyor. Notebook kaynakları API üzerinden yayınlanmaz.

**Bu uygulama notebookların tamamının birebir çalıştırıcısı değildir.** Yerelde çalışabilen, OHLC ile sınırlı araştırma uyarlamasıdır. TFT, FRED/Dukascopy veri çekimi, teori/makro özellikleri, 25 uzman havuzu, MAIN_14/THEORY_11 ve tez tablolarının birebir yeniden üretimi bu sürümde yoktur. Bunlar için ayrıca veri sağlanması ve notebook deneylerinin ayrı pipeline'lara dönüştürülmesi gerekir. UI'da bu kısıtlar Metodoloji ekranında belirtilir.

## Hesaplama protokolü

- Fiyatlardan gecikmeli getiriler, momentum, SMA oranları, volatilite, RSI, MACD, bar aralığı ve saat özellikleri üretilir.
- Trend uzmanı: StandardScaler + Ridge; momentum uzmanı: Random Forest; volatilite uzmanı: Histogram Gradient Boosting.
- Modeller ve HMM yalnızca eğitimde öğrenir. HMM girdileri getiri, 14 bar volatilitesi ve 30 bar momentumudur. Durumlar **ileri filtreleme** ile çıkarılır; geleceği gören Viterbi çözümü kullanılmaz.
- Eğitim oranı %50–75, doğrulama %15, kalan test. Eğitim/doğrulama ve doğrulama/test sınırlarında ikişer bar dışarıda bırakılır.
- Her rejimde uzmanların doğrulama MSE değerlerinin tersi normalize edilerek ağırlık bulunur. 15'ten az rejim gözlemi varsa tüm doğrulama dönemi kullanılır. İşlem eşiği `[0, 0.25, 0.5, 1, 2]` baz puan arasından doğrulama Sharpe değerine göre seçilir. Seçimden sonra test yeniden optimizasyon yapmaz.
- t barının kapanış bilgisiyle sinyal üretilir; t+1 açılışında işlem yapılır ve t+2 açılışına kadar tutulur. Tahmin edilen hedef bu iki açılış arasındaki basit getiridir. CSV'de `signal_timestamp` özellik barını, `timestamp` getirinin gerçekleştiği açılışı gösterir.
- 1 bp = %0,01. Tek yön maliyeti girişte, pozisyon değişiminde ve son çıkışta uygulanır. Long→short dönüşü iki yön maliyeti taşır. Ayrı spread/funding modeli yoktur; toplam tahmini sürtünme maliyet alanıyla temsil edilir. Kaldıraç yoktur. Deney platformunda `spread_model: ohlc_range` seçilirse spread bar aralığına göre ölçeklenir; validasyon ve final test aynı maliyet modelini kullanır. Long/short swap oranları ve Çarşamba triple rollover opsiyoneldir.
- Sharpe risksiz oranı 0'dır. Yıllık bar sayısı `252 × 24 / medyan_bar_saati` ile varsayılır. Düşüş ilk sermayeyi de zirve hesabına dahil eder. Pozisyon değişimi tamamlanmış işlem sayısı değildir. Kazanma oranı aktif barlar üzerinden hesaplanır.
- Rejim numaraları ekonomik yükseliş/düşüş etiketleri değildir. Durumdaki ortalama test hedef getirisi açıklayıcıdır, model eğitiminde kullanılmaz.
- Deney konfigürasyonları, günlükler ve raporlar `data/run-*.json`; yüklenen CSV'ler `data/dataset-*` olarak yerelde saklanır. Eğitilmiş model nesneleri kaydedilmez; konfigürasyonla yeniden eğitim yapılabilir. Aynı anda bir deney çalışır. Sunucunun kapanması devam eden çalıştırmayı keser; tamamlanan sonuçlar korunur.
- Çok uzun serilerin grafiği en fazla yaklaşık 600 noktaya seyreltilir; metrikler ve CSV tüm test barlarını içerir.

### Experiment platform protokolü

- Snapshot doğrulanmış OHLC CSV'nin değişmez kopyası ve SHA-256 hash'idir; satır sayısı, şema, UTC normalizasyonu ve aralık istatistikleri kaydedilir.
- OHLC dosyası vintage/revision, gerçek yayın anı, DST kaynağı veya eksik verinin sebebini ispatlayamaz. Snapshot bu alanları `unverified / not supplied` olarak açıkça tutar.
- GA test verisini almaz. Walk-forward fold'larında eğitim sonu ile validation başlangıcı arasında gap bırakılır. Aday dondurulduktan sonra `frozen_candidate.json` artifact'ı yazılır, ardından tek final test başlar.
- Test metrikleri, feature IC/stability ve maliyet duyarlılığı aday seçimine geri beslenmez. Aynı test dönemini klonla yeniden ölçmek holdout özelliğini zayıflatabilir; arayüz bunu belirtir.
- Yerel politika: en fazla 32 popülasyon, 20 nesil, 128 aday, 5 model, 50.000 bar, 10 dakika ve tek worker. Aşan istekler `policy_rejected` olur.

## Geliştirme ve doğrulama

```powershell
# Terminal 1
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
# Terminal 2
cd frontend
npm run dev
```

React geliştirme sunucusu `/api` isteklerini Python'a yönlendirir. Üretim derlemesini güncellemek için `cd frontend; npm run build`, ardından Python sunucusunu yeniden başlatın.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
npm --prefix frontend run build
```

Testler CSV hatalarını, nedensel özellikleri ve HMM filtresini, işlem maliyetlerini, kronolojik ayrımı ve API yükleme→eğitim→dışa aktarma→kalıcı geçmiş akışını kapsar.

Uygulama kodunda kullanılan API referansları: [FastAPI dosya yükleme](https://fastapi.tiangolo.com/tutorial/request-files/), [hmmlearn GaussianHMM](https://hmmlearn.readthedocs.io/en/stable/api.html). Font için Google Fonts kullanılır; internet yoksa sistem sans-serif fontuna döner.
