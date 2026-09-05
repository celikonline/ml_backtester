# AI Asistanlar

Deney platformundaki **AI Asistanlar** sekmesi dört hazır şablon sunar: araştırma,
fikir üretimi, doğrulama ve backtest değerlendirmesi. Şablonlar salt okunurdur;
**Klonla** ile çalışma alanınıza kopyalayıp adını, açıklamasını, sistem talimatını,
araştırma aşamasını ve okuma izinlerini düzenleyebilirsiniz. **Asistan ekle**
boş bir yapılandırma oluşturur.

**Yeni görev** üzerinden talimatınızı yazın ve isteğe bağlı bir deney seçin.
Deney yapılandırması ve backtest metrikleri ayrı okuma izinlerine tabidir.
Görevler sekmesi son 100 görevin yanıtını veya bağlantı hatasını gösterir.
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
sunucu ve platformun istek süresi sınırlarına uygun çalışma gerekir.

## İlk sürümün kapsamı

- Gerçek model yanıtı ile araştırma ve analiz; model cevabı düz metin gösterilir.
- Yalnızca seçilen deneyin yapılandırması ve izinli metrikleri modele gönderilir.
  Ham veri dosyaları, dosya yolları veya anahtarlar gönderilmez.
- Asistanlar kod çalıştırmaz, deney oluşturmaz, backtest veya canlı işlem
  başlatmaz. Aşama alanı sınıflandırmadır; kanban kartı taşımaz.
- Alt asistan zincirleri, araç çağırma, zamanlama ve sohbet devamı bu sürümde yoktur.
- Görev HTTP isteği içinde çalışır; model isteği 90 saniyede zaman aşımına uğrar.
  Sunucu zorla kapatılırsa RUNNING kaydı otomatik sürdürülmez. Sayfayı yenilemek
  görevi iptal etmez; Görevler sekmesi durumu yeniden okur.

Doğrulama: `python -m pytest tests/test_assistants.py tests/test_platform.py tests/test_api.py -q`
ve `frontend` klasöründe `npm run build`. Model bağlantısı testlerde taklit edilir;
gerçek yanıt için çalışan Ollama ve kurulu model gerekir.
