# AI Asistanlar

Deney platformundaki **AI Asistanlar** sekmesi dört hazır şablon sunar: araştırma,
fikir üretimi, doğrulama ve backtest değerlendirmesi. Şablonlar salt okunurdur;
**Klonla** ile çalışma alanınıza kopyalayıp adını, açıklamasını, sistem talimatını,
araştırma aşamasını, izinlerini ve alt asistan zincirini düzenleyebilirsiniz. **Asistan ekle**
boş bir yapılandırma oluşturur.

**Yeni görev** üzerinden talimatınızı yazın ve isteğe bağlı bir deney seçin.
Deney yapılandırması ve backtest metrikleri ayrı okuma izinlerine tabidir.
Görevler sekmesi son 100 görevin durumunu, her adımın çıktısını, backtest kimliğini
ve hatalarını gösterir. Aktif görevlerin durumu otomatik yenilenir.
Yapılandırmalar ve görev geçmişi platform veritabanında, çalışma alanına bağlı
saklanır. `0010_assistants` migration'ı uygulama başlatılırken uygulanır.

## Model bağlantısı

Bu sürüm Ollama'nın [Chat API](https://docs.ollama.com/api/chat) uç noktasını
kullanır. Ollama'yı kurup seçtiğiniz modeli indirdikten sonra uygulamayı şu
ortam değişkenleriyle başlatın (model adını kendi kurulu modelinizle değiştirin):

```powershell
$env:REGIMELAB_AI_MODEL = 'kurulu-model-adi'
$env:REGIMELAB_AI_URL = 'http://127.0.0.1:11434'
.\start.ps1
```

URL isteğe bağlıdır; varsayılanı yukarıdaki yerel adrestir. Model adının
ayarlanmış olması modelin erişilebilir olduğunun garantisi değildir; bağlantı
hatası görev sonucuna kaydedilir. Ortam değişkenleri değişince sunucuyu yeniden
başlatın. Vercel'de localhost masaüstündeki Ollama'ya ulaşmaz; erişilebilir bir
sunucu gerekir. Görev kuyruğu sürekli çalışan tek bir API süreci gerektirir;
Vercel'in isteğe bağlı fonksiyonlarında arka plan worker'ının çalışması garanti
edilmez. Bu akış için yerel sunucuyu veya sürekli çalışan bir sunucu dağıtımını kullanın.

## Otomatik backtest

1. **Backtest Assistant → Yeni görev** seçin veya özel bir asistanda deney okuma,
   metrik okuma ve **Backtest çalıştır** izinlerini açıp **Otomatik backtest**
   seçeneğini etkinleştirin.
2. Görev formunda bir deney seçin ve **Bu görevde otomatik backtest çalıştır**
   kutusunu işaretleyin. Seçilmezse otomasyon adımları yalnızca analiz yapar.
3. Görevi başlatın. Taslak deney mevcut deney worker'ında çalıştırılır. Zincir
   `WAITING_BACKTEST` durumunda sonucu bekler; tamamlanınca gerçek sonuç özeti ve
   metrikleriyle analiz yapıp sonraki asistana geçer.

Devam eden deney beklenir, tamamlanmış deneyin mevcut sonucu kullanılır. Aynı
deney zincirde birden fazla backtest adımında yer alsa da tekrar çalıştırılmaz.
Bütçe, hesaplama politikası, tek çalıştırma ve kilitli test kuralları korunur.
Backtest başarısız olur, iptal edilir veya politika tarafından reddedilirse
zincir durur. Yeni deneme için deneyi mevcut **Klonla** akışıyla hazırlayın.

## Alt asistan zincirleri

Bir asistanı düzenlerken **Alt asistan zinciri** bölümünden asistan ekleyin;
yukarı/aşağı düğmeleriyle sıralayın veya çıkarın. Kök asistan ilk çalışır, ardından
her alt asistan ve onun alt zinciri sırayla çalışır. Toplam sınır kök dahil
8 adımdır. Döngüler, tekrarlanan asistanlar ve başka çalışma alanındaki asistanlar
sunucuda reddedilir.

Örnek: özel bir Research Assistant klonuna önce **Backtest Assistant**, ardından
**Validation Assistant** ekleyin. Araştırma adımı planı çıkarır, backtest adımı
deneyi çalıştırır ve yorumlar, doğrulama adımı önceki çıktıları ve sonuçları inceler.
Bu akış mevcut deney yapılandırmasını kullanır; modelin yazdığı plan deney
parametrelerini otomatik değiştirmez.

Her adım önceki adımların çıktısını alır. Deney bağlamı varsa sonraki asistanın
önceki adımlarda paylaşılan verileri okuma izni de olmalıdır; örneğin metrik okuma
izni olmayan bir asistan metrikleri okuyabilen bir adımın arkasına konulamaz.
Görev başlatıldığında zincir, talimatlar, izinler ve model adı kalıcı olarak
kopyalanır; sonraki yapılandırma değişiklikleri devam eden görevi değiştirmez.

**Zinciri durdur** kalan adımları engeller. Sürmekte olan model isteğinin geç
gelen yanıtı görevi yeniden tamamlandı durumuna getiremez. Başlatılmış backtest
çalışmaya devam eder; gerekiyorsa deney ekranından ayrıca iptal edin.

## Çalışma ve kapsam

- Gerçek model yanıtı ile araştırma ve analiz; model cevabı düz metin gösterilir.
- Yalnızca seçilen deneyin yapılandırması ve izinli metrikleri modele gönderilir.
  Ham veri dosyaları, dosya yolları veya anahtarlar gönderilmez.
- Asistanlar mevcut deneyleri backtest servisiyle çalıştırabilir. Model çıktısı
  kod olarak yürütülmez; deney oluşturma/değiştirme ve canlı işlem araçları yoktur.
  Aşama alanı sınıflandırmadır; kanban kartı taşımaz.
- Zincir sırası yapılandırmadan gelir. Modelin dinamik asistan seçimi, genel araç
  çağırma, zamanlama ve sohbet devamı bu sürümde yoktur.
- HTTP isteği görevi kaydedip `202 Accepted` döndürür. Ayrı asistan worker'ı
  sıradaki adımları işler. Tek bir model isteğinin zaman aşımı 90 saniyedir.
- Yeniden başlatıldığında kaydedilmiş adımlardan devam edilir. Tamamlanma kaydı
  yazılmadan kesilen model adımı yeniden çağrılabilir; tamamlanmış adımlar korunur.
  Backtest çağrıları aynı deneyin tek çalıştırma kuralıyla korunur. Hesaplama
  sırasında sunucu kapanmışsa mevcut deney worker'ı bu çalıştırmayı başarısız
  sayar ve zincir bunu hata olarak gösterir; sessizce yeniden backtest başlatmaz.
- `GET /api/v1/assistant-tasks/{id}` tek görevi okur;
  `POST /api/v1/assistant-tasks/{id}/cancel` zinciri durdurur.

Doğrulama: `python -m pytest tests/test_assistants.py tests/test_platform.py tests/test_api.py -q`
ve `frontend` klasöründe `npm run build`. Otomasyon testi sentetik veride gerçek
backtest worker'ını çalıştırıp hesaplanan metriklerin sonraki adımlara aktarıldığını
ve tekrarlı backtest başlatılmadığını doğrular. Model bağlantısı testlerde taklit
edilir; gerçek AI yanıtı için çalışan Ollama ve kurulu model gerekir.
