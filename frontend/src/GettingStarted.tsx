import { Activity, ArrowRight, BookOpen, CircleHelp, Database, FlaskConical, History, Layers3, LayoutDashboard, ShieldCheck, Sparkles } from 'lucide-react';
import { useLang } from './i18n';
import './app/styles/getting-started.css';

type Props = { onNavigate: (page: string) => void; onNewExperiment: () => void; onDemo: () => void; onStartTour: () => void };

export default function GettingStarted({ onNavigate, onNewExperiment, onDemo, onStartTour }: Props) {
  const { t, lang } = useLang();
  const tr = lang === 'tr';
  const indicatorRows = [
    ...[7, 14, 21, 50].map(period => ({
      name: `RSI_${period}`,
      purpose: tr ? 'Fiyat hareketinin momentumunu ve aşırı alım/aşırı satım eğilimini ölçer.' : 'Measures price momentum and overbought/oversold tendency.',
      output: tr ? '0–100 arası değer üretir.' : 'Produces a value from 0 to 100.',
      reading: tr ? 'Yüksek değer güçlü son dönem artışını, düşük değer güçlü son dönem düşüşünü gösterir. Tek başına al-sat emri değildir.' : 'A high value means stronger recent gains; a low value means stronger recent losses. It is not a standalone buy/sell order.'
    })),
    ...[7, 14, 21, 50].map(period => ({
      name: `EMA_${period}`,
      purpose: tr ? `${period} barlık üstel hareketli ortalamaya göre fiyatın uzaklığını izler.` : `Tracks price distance from the ${period}-bar exponential moving average.`,
      output: tr ? 'Fiyat / EMA − 1 oranını üretir.' : 'Produces the price / EMA − 1 ratio.',
      reading: tr ? 'Pozitif değer fiyatın EMA üzerinde, negatif değer altında olduğunu gösterir. Mutlak değer uzaklığı belirtir.' : 'A positive value means price is above the EMA; a negative value means below it. Absolute size shows distance.'
    })),
    ...[7, 14, 21, 50].map(period => ({
      name: `ATR_${period}`,
      purpose: tr ? `${period} barlık ortalama gerçek aralıkla fiyat oynaklığını ölçer.` : `Measures price volatility using the average true range over ${period} bars.`,
      output: tr ? 'ATR / Close oranını üretir.' : 'Produces the ATR / Close ratio.',
      reading: tr ? 'Yüksek değer daha hareketli ve riskli dönemi, düşük değer daha sakin dönemi gösterir.' : 'A higher value indicates a more active and riskier period; a lower value indicates a calmer period.'
    })),
    ...[7, 14, 21, 50].map(period => ({
      name: `BB_position_${period}`,
      purpose: tr ? `${period} barlık Bollinger bantları içinde fiyatın göreli konumunu gösterir.` : `Shows the relative price position inside ${period}-bar Bollinger bands.`,
      output: tr ? 'Alt bantta yaklaşık 0, üst bantta yaklaşık 1 değeri üretir.' : 'Produces about 0 at the lower band and about 1 at the upper band.',
      reading: tr ? '0’a yakın değer alt banda, 1’e yakın değer üst banda yakınlığı gösterir. Bant dışı değerler de oluşabilir.' : 'Values near 0 are close to the lower band; values near 1 are close to the upper band. Values outside the bands can occur.'
    }))
  ];
  const financeTerms = tr ? [
    { term: 'İndikatör', definition: 'Fiyat ve hacim gibi geçmiş piyasa verilerinden hesaplanan ölçümdür.', use: 'Modelin veya sinyal kuralının kullanabileceği düzenli bir sayısal girdi üretir.' },
    { term: 'Feature (özellik)', definition: 'Modelin tahmin yaparken gördüğü her bir giriş değişkenidir.', use: 'Modelin gelecekteki hareketi öğrenmesi için kullanılacak bilgiyi temsil eder.' },
    { term: 'Sinyal', definition: 'Model tahmini ve koşulların birleşmesiyle oluşan işlem yönü işaretidir.', use: 'Pozisyon açılıp açılmayacağını ve yönün long mu short mu olacağını belirler.' },
    { term: 'Long', definition: 'Fiyatın yükseleceği beklentisiyle alınan pozisyondur.', use: 'Yukarı yönlü tahminde stratejinin pozitif pozisyon almasını sağlar.' },
    { term: 'Short', definition: 'Fiyatın düşeceği beklentisiyle alınan veya satılan pozisyondur.', use: 'Aşağı yönlü tahminde stratejinin negatif pozisyon almasını sağlar.' },
    { term: 'Momentum', definition: 'Fiyat hareketinin hızını ve yönündeki devamlılığı anlatır.', use: 'Son dönemdeki yükseliş veya düşüşün güçlenip güçlenmediğini ölçmeye yardım eder.' },
    { term: 'RSI', definition: 'Son dönem yükseliş ve düşüşlerini 0–100 aralığında özetleyen momentum göstergesidir.', use: 'Göreli güç, aşırı alım ve aşırı satım koşullarını incelemek için kullanılır.' },
    { term: 'EMA', definition: 'Yakın geçmiş fiyatlara daha fazla ağırlık veren hareketli ortalamadır.', use: 'Trend yönünü ve mevcut fiyatın ortalamaya göre uzaklığını izlemeye yarar.' },
    { term: 'ATR', definition: 'Gerçek fiyat aralığının ortalamasından hesaplanan oynaklık ölçüsüdür.', use: 'Piyasanın ne kadar hareketli olduğunu ve riskin artıp azaldığını gösterir.' },
    { term: 'Bollinger bandı', definition: 'Hareketli ortalama çevresindeki değişken fiyat bantlarıdır.', use: 'Fiyatın kendi yakın geçmiş aralığının neresinde olduğunu ve bant genişliğini incelemeye yarar.' },
    { term: 'Volatilite / oynaklık', definition: 'Fiyatın belirli bir sürede ne kadar değiştiğini anlatır.', use: 'Risk, pozisyon boyutu ve sakin-hareketli piyasa rejimlerini değerlendirmeye yardım eder.' },
    { term: 'Eşik (threshold)', definition: 'Bir indikatörün sinyal üretmesi için geçmesi gereken sayısal sınırdır.', use: 'Örneğin RSI > 50 koşuluyla long tahminlerinin ne zaman işleme dönüşeceğini sınırlar.' },
    { term: 'Kesişim (cross above/below)', definition: 'Bir değerin eşik seviyesini önceki bara göre yukarı veya aşağı geçmesidir.', use: 'Sadece seviyenin üzerinde olmayı değil, yeni oluşan geçiş anını yakalar.' },
    { term: 'Position change / pozisyon değişimi', definition: 'Stratejinin pozisyon yönünü veya büyüklüğünü değiştirdiği olaydır.', use: 'İşlem sıklığını, turnoverı ve maliyet etkisini ölçmeye yarar.' },
    { term: 'Benchmark', definition: 'Stratejiyi karşılaştırmak için kullanılan basit referans getiridir.', use: 'Modelin yalnızca piyasa hareketini takip edip etmediğini değerlendirmeye yardım eder.' },
    { term: 'Sharpe oranı', definition: 'Getiriyi oynaklığa göre düzelten risk-getiri ölçüsüdür.', use: 'Daha fazla riske karşı ne kadar getiri üretildiğini karşılaştırmak için kullanılır.' },
    { term: 'Drawdown / maksimum düşüş', definition: 'Bir tepe değerinden sonraki en büyük gerilemedir.', use: 'Stratejinin kötü dönemde yaşayabileceği kayıp derinliğini gösterir.' },
    { term: 'Slippage / kayma', definition: 'Beklenen işlem fiyatı ile gerçekleşen fiyat arasındaki farktır.', use: 'Gerçek hayatta oluşabilecek fiyat kaybını backtest maliyetlerine ekler.' },
    { term: 'Komisyon', definition: 'Alım-satım işlemi için aracıya veya piyasaya ödenen ücrettir.', use: 'İşlem maliyetinin net getiriyi ne kadar azalttığını ölçmeye yarar.' },
    { term: 'Rejim', definition: 'Piyasanın trendli, yatay, sakin veya hareketli gibi davranış durumudur.', use: 'Modelin ve stratejinin hangi piyasa koşullarında çalıştığını ayırmaya yarar.' }
  ] : [
    { term: 'Indicator', definition: 'A measure calculated from historical market data such as price or volume.', use: 'Produces a structured numeric input for a model or signal rule.' },
    { term: 'Feature', definition: 'An input variable observed by the model while making a prediction.', use: 'Represents information the model can use to learn future movement.' },
    { term: 'Signal', definition: 'A trade-direction indication formed from a model prediction and conditions.', use: 'Determines whether to open a position and whether it is long or short.' },
    { term: 'Long', definition: 'A position taken with the expectation that price will rise.', use: 'Lets an upward prediction create a positive position.' },
    { term: 'Short', definition: 'A position taken with the expectation that price will fall.', use: 'Lets a downward prediction create a negative position.' },
    { term: 'Momentum', definition: 'The speed and persistence of a price move.', use: 'Helps measure whether a recent rise or fall is strengthening or fading.' },
    { term: 'RSI', definition: 'A 0–100 momentum indicator summarizing recent gains and losses.', use: 'Helps study relative strength and overbought/oversold conditions.' },
    { term: 'EMA', definition: 'A moving average that gives more weight to recent prices.', use: 'Tracks trend direction and the distance of price from its average.' },
    { term: 'ATR', definition: 'A volatility measure based on the average true price range.', use: 'Shows how active the market is and whether risk is increasing or decreasing.' },
    { term: 'Bollinger band', definition: 'A variable price band around a moving average.', use: 'Helps inspect where price sits within its recent range and how wide that range is.' },
    { term: 'Volatility', definition: 'How much price changes over a given period.', use: 'Supports risk, position sizing, and calm-versus-active regime analysis.' },
    { term: 'Threshold', definition: 'A numeric boundary an indicator must cross for a signal condition.', use: 'For example, RSI > 50 controls when a long prediction becomes a trade.' },
    { term: 'Cross above/below', definition: 'A value crossing a threshold relative to the previous bar.', use: 'Captures a new transition, not merely being above or below a level.' },
    { term: 'Position change', definition: 'An event where the strategy changes position direction or size.', use: 'Measures trading frequency, turnover, and cost impact.' },
    { term: 'Benchmark', definition: 'A simple reference return used to compare the strategy.', use: 'Helps assess whether the model does more than simply follow the market.' },
    { term: 'Sharpe ratio', definition: 'A risk-adjusted return measure that relates return to volatility.', use: 'Compares how much return is produced for the risk taken.' },
    { term: 'Drawdown / maximum drawdown', definition: 'The largest decline from a previous peak.', use: 'Shows the depth of the loss the strategy could experience in a bad period.' },
    { term: 'Slippage', definition: 'The difference between expected and executed trade price.', use: 'Adds a realistic price-loss assumption to backtest costs.' },
    { term: 'Commission', definition: 'A fee paid to the broker or market for executing a trade.', use: 'Measures how transaction fees reduce net return.' },
    { term: 'Regime', definition: 'A market behaviour state such as trending, ranging, calm, or volatile.', use: 'Separates the conditions in which a model or strategy performs.' }
  ];
  const manualSections = tr ? [
    {
      number: '01', title: 'Giriş ve çalışma alanını tanı',
      intro: 'Regime Lab, veri üzerinde kod yazmadan kontrollü backtest deneyi kurmanı sağlar. Soldaki menü ekranlar arasında geçiş yapar; sağ üstteki profil menüsü hesap ayarlarını açar.',
      steps: [
        'Uygulamayı açtıktan sonra Başlarken sayfasını oku. Dil ve tema değişikliği profil menüsündeki Hesap ve Profil Ayarları bölümünden yapılır.',
        'Çalışma alanı veya proje seçimin varsa doğru çalışma alanında olduğunu kontrol et. Deneyler, veri snapshotları ve kullanım limitleri çalışma alanına göre tutulur.',
        'İlk deneme için sentetik EUR/USD verisini kullan. Gerçek bir araştırmada kendi verini Veri Merkezi üzerinden yükle.'
      ],
      tip: 'Her deneyi tekrar üretilebilir yapmak için aynı veri snapshotını, tarih aralığını, maliyeti ve seed değerini not et.'
    },
    {
      number: '02', title: 'Veriyi hazırla ve kontrol et',
      intro: 'İyi bir backtest önce doğru zaman sıralı veriye dayanır. Veri Merkezi, yüklenen dosyayı ve değişmez snapshot bilgisini kontrol edebileceğin yerdir.',
      steps: [
        'Soldan Veri Merkezi ekranını aç. Demo için sentetik veri kaynağını seç veya CSV yükle düğmesine bas.',
        'CSV dosyanda en az Timestamp, Open, High, Low ve Close kolonlarının bulunduğunu kontrol et. Timestamp sıralı ve tekrarsız olmalıdır.',
        'Makro veya başka varlık verisi kullanıyorsan kolon adını macro__, cross_asset__, fx__ veya rates__ ile başlat; kullanılabilirlik zamanını __available_at kolonu ile belirt.',
        'Dataset satır önizlemesini açıp ilk ve son tarihleri, boş değerleri ve fiyat kolonlarını kontrol et. Deneyde seçilecek veri kümesi burada belirlenir.'
      ],
      tip: 'İleri tarih bilgisi içeren bir kolonu modele doğrudan verme. Kullanılabilirlik zamanı, veri sızıntısını önlemek için gözlem zamanından önce olmalıdır.'
    },
    {
      number: '03', title: 'Yeni deney oluştur ve tarihleri seç',
      intro: 'Deney Platformu kod yazmadan bir backtest tarifini adım adım oluşturur. Deneyi henüz çalıştırmadan önce taslak olarak saklayabilirsin.',
      steps: [
        'Başlarken sayfasındaki Deney oluştur düğmesine veya Deney Platformu ekranındaki Yeni deney düğmesine bas.',
        'Veri adımında deney adını yaz, veri kümesini seç, zaman dilimini belirle ve açıklama ekle. Başlangıç-bitiş tarihleri verinin mevcut aralığı içinde olsun.',
        'Tarih aralığını üç parçaya ayır: train modeli öğretir, validation ayarları seçmek ve optimizasyonu değerlendirmek için kullanılır, test ise en sona saklanan nihai kontroldür.',
        'İleri düğmesiyle bir sonraki adıma geç. Geri dönüp önceki seçimleri değiştirebilirsin; inceleme adımında tüm ayarların özeti görünür.'
      ],
      tip: 'Test aralığını karar verme sürecinde kullanma. Test sonucu, daha önce görmediğin veri üzerindeki son kontrol olarak kalmalıdır.'
    },
    {
      number: '04', title: 'İndikatörleri ve sinyalleri seç',
      intro: 'Özellikler adımında sistemin önceden hesapladığı nedensel indikatörlerden seçim yaparsın. Bu indikatörler yalnızca o bar ve geçmiş barları kullanır.',
      steps: [
        'Özellikler adımında arama alanıyla indikatör bul. Trend, momentum, volatilite ve fiyat ailesinden ihtiyacın olan kolonları işaretle.',
        'RSI, EMA, ATR ve Bollinger gibi hazır indikatörleri seçerken çok fazla benzer özellik eklememeye çalış. Seçilen özelliklerin önizlemesini kontrol et.',
        'Long ve short sinyal filtrelerini seç. Filtreler, model çıktısının hangi koşulda pozisyona dönüşeceğini belirler; yalnızca model seçmek otomatik olarak iyi bir işlem stratejisi anlamına gelmez.',
        'İleri ile Modeller adımına geç. Özellikleri değiştirirsen optimizasyon ve validasyon sonuçlarını yeniden değerlendirmelisin.'
      ],
      tip: 'Bir indikatörün geleceği bilmediğinden emin değilsen onu kullanma veya uygun __available_at bilgisini ekle.'
    },
    {
      number: '05', title: 'Model ve piyasa rejimi seç',
      intro: 'Uzman modeller farklı piyasa davranışlarını arar. İstersen rejim yönlendirmesi ile farklı piyasa durumlarında farklı uzmanlar çalıştırabilirsin.',
      steps: [
        'Modeller adımında en az bir model seç. Trend, momentum veya volatilite davranışına uygun uzmanları birlikte seçerek validation sonuçlarını karşılaştırabilirsin.',
        'Rejime göre model yönlendirmesini açmak istersen etkinleştir, bir fallback modeli seç ve her rejim durumu için çalışacak modeli belirle.',
        'Minimum rejim bar sayısını ayarla. Bir durumda yeterli geçmiş yoksa sistem fallback modeline döner; bu durum sonuç özetinde görünür.',
        'Piyasa rejimleri ekranındaki durum numaralarını doğrudan boğa veya ayı diye adlandırma. Her durumun volatilite, trend ve performans özelliklerini sonuçlardan yorumla.'
      ],
      tip: 'Yönlendirme zorunlu değildir. Önce tek bir modelle temel sonuç al, sonra rejim yönlendirmesini açıp gerçekten iyileşme olup olmadığını karşılaştır.'
    },
    {
      number: '06', title: 'Optimizasyon ve validasyonu ayarla',
      intro: 'Bu bölüm, hangi ayarların seçileceğini ve seçimin hangi veri üzerinde yapılacağını belirler. Amaç test verisine bakarak en iyi sonucu seçmek değildir.',
      steps: [
        'Optimizasyon adımında kapalı, grid, random veya genetic yöntemlerinden birini seç. İlk denemede kapalı veya küçük bir aralıkla başlamak daha hızlıdır.',
        'Parametre alt-üst sınırlarını ve aday sayısını gereksiz genişletme. Çok geniş arama overfitting ve uzun çalışma süresi oluşturabilir.',
        'Validasyon adımında rolling veya walk-forward yöntemini, fold sayısını, train/validation oranını ve gerekiyorsa purge/gap aralığını seç.',
        'Komisyon, slippage, başlangıç sermayesi ve random seed değerini gerçekçi gir. Bu maliyetler sonuç metriklerine dahil edilir.'
      ],
      tip: 'Validation iyi görünen ayarı seçmek içindir; test yalnızca seçimin daha önce görülmemiş dönemde nasıl davrandığını ölçer.'
    },
    {
      number: '07', title: 'Taslağı kaydet ve deneyi çalıştır',
      intro: 'İnceleme ekranı, çalıştırmadan önce tarifin tamamını görmeni sağlar. Çalıştırma gerçek backtest iş akışını başlatır; yalnızca örnek bir sonuç göstermez.',
      steps: [
        'İnceleme adımında veri, tarih bölümleri, özellikler, model, optimizasyon, validasyon ve maliyet ayarlarını kontrol et.',
        'Taslağı kaydet. Kayıt sonrasında deney kodu oluşur; deney detayından ayarları yeniden açabilir veya çalıştırabilirsin.',
        'Çalıştır düğmesine bas. Log ekranında veri hazırlama, indikatör, eğitim, optimizasyon, validasyon ve test aşamalarını takip et.',
        'Çalışma başarısız olursa kırmızı durum ve hata logu görünür. Veri kolonları, tarih aralığı, yetersiz satır veya model ayarını düzelterek yeniden çalıştır.'
      ],
      tip: 'Çalışma çok hızlı bittiğinde logları ve deney kodunu kontrol et. Başarılı bir sonuçta gerçek eğitim, validasyon, test ve metrik üretim aşamaları kayıt altına alınır.'
    },
    {
      number: '08', title: 'Sonuçları doğru oku',
      intro: 'Sonuç ekranı tek bir getiri sayısından ibaret değildir. Her sekme farklı bir soruya cevap verir ve birlikte değerlendirilmelidir.',
      steps: [
        'Genel Bakış sekmesinde test tarihini, toplam getiriyi, Sharpe oranını, maksimum düşüşü, işlem sayısını ve equity eğrisini kontrol et.',
        'Özellikler sekmesinde seçilen indikatörlerin etkisini, optimizasyon sekmesinde adayları ve seçimin validation performansını incele.',
        'Validasyon sekmesinde fold sonuçlarını ve validation-test farkını karşılaştır. Büyük fark, kararlılık veya aşırı uyum sorunu olabileceğini gösterir.',
        'Rejimler sekmesinde durumların bar payını, geçişlerini ve rejim bazlı performansı incele. Artifact ve lineage sekmelerinde üretilen dosyaları ve kullanılan veri/ayar izini bul.',
        'Sonucu farklı maliyet, tarih ve model ayarlarıyla tekrar çalıştır. Tek bir deneyin yeşil görünmesi gelecekte aynı getirinin garantisi değildir.'
      ],
      tip: 'İyi bir sonuç; makul düşüş, tutarlı fold performansı, gerçekçi maliyet sonrası dayanıklılık ve validation-test yakınlığıyla birlikte değerlendirilir.'
    },
    {
      number: '09', title: 'Geçmiş deneyleri ve Notebook Lab’i kullan',
      intro: 'Kodlu bir araştırman varsa Notebook Lab ile çalıştırabilir, başarılı notebooku platform deneyine dönüştürebilirsin. Önceki çalışmalarını Geçmiş ekranından bulabilirsin.',
      steps: [
        'Geçmiş ekranında arama ve durum filtreleriyle deneyini bul. Deney kodunu açarak detay, log ve sonuç sekmelerine dön.',
        'Notebook Lab’de notebook yükle. Parametreleri kontrol et ve Çalıştır düğmesine bas; canlı loglardan çalışmanın durumunu izle.',
        'Notebook başarıyla tamamlandığında Deneye dönüştür düğmesine bas. Oluşan deney kodu bildirimde gösterilir ve uygulama otomatik olarak ilgili deney ekranına konumlanır.',
        'Dönüşen deneyde veri snapshotı, model ve sonuç izini kontrol et; gerekirse kodlu sonuçla no-code backtest sonucunu karşılaştır.'
      ],
      tip: 'Notebook dönüşümü tamamlanınca otomatik açılan deney ekranı, dönüşen deneyi incelemen için başlangıç noktasıdır; çalıştırma gerekiyorsa ayrıca Çalıştır düğmesine bas.'
    },
    {
      number: '10', title: 'Chatbot ile araştırmayı destekle',
      intro: 'Sağ taraftaki chatbot, uygulama içindeki sonuçları anlamana ve araştırma soruları hazırlamana yardımcı olur. Yanıtı sonuç yerine koyma; kaynak deney ve logları kontrol et.',
      steps: [
        'Chatbot düğmesine bas. Panel sağ tarafta açılır; sabitleme ile paneli sağa kilitleyip çalışma alanını sola kaydırabilir, tam ekranla paneli büyütebilirsin.',
        'Hazır sorulardan birini seç veya arama alanıyla soru bul. İhtiyacın olan soru yoksa kendi sorunu ekleyip tekrar kullanmak üzere kaydedebilirsin.',
        'Bir sohbeti sabitleyerek önemli konuşmaları üstte tut. Yanıt metnini kopyala veya dışa aktar; farklı dil seçimi için hesap ayarındaki dili değiştir.',
        'Chatbotun istediği işlem veya veri erişimini kontrol et. Önemli kararları deney sonuçları, validasyon ve log kayıtlarıyla doğrula.'
      ],
      tip: 'Chatbot iyi bir araştırma yardımcısıdır; geleceği tahmin eden veya kötü backtesti güvenilir hale getiren bir otorite değildir.'
    },
    {
      number: '11', title: 'Profil ve güvenlik ayarlarını yönet',
      intro: 'Profil menüsündeki hesap sayfası kişisel bilgilerini, dil/tema tercihlerini ve aktif oturumlarını yönetir.',
      steps: [
        'Profil menüsünü açıp Hesap ve Profil Ayarları sayfasına git. Genel Bakış bölümünde deney ve çalışma kullanımını gör.',
        'Ayarlar bölümünde görünen ad, dil ve temayı değiştir. Kaydetten sonra dil ve tema uygulamaya yansır.',
        'Güvenlik bölümünde e-posta veya şifre değiştirirken mevcut hesabını doğrula. Şifre değişiminden sonra diğer oturumların kapatılması beklenen güvenlik davranışıdır.',
        'Oturumlar bölümünde aktif cihazları ve son kullanım zamanlarını incele; tanımadığın oturumu sonlandır.'
      ],
      tip: 'Şifreni veya oturum bilgilerini chatbot ile paylaşma. Kullanmadığın oturumları kapat ve hesap bilgilerini yalnızca hesap sayfasından değiştir.'
    },
    {
      number: '12', title: 'Demo: baştan sona ilk deneyini çalıştır',
      intro: 'Aşağıdaki akış, platformu ilk kez kullanan birinin güvenli bir sentetik veri demosunu tamamlaması için hazırlanmıştır.',
      steps: [
        'Bu sayfanın altındaki Demo deneyini başlat düğmesine bas. Uygulama seni Deney Platformu’nda yeni deney sihirbazına götürür.',
        'Veri adımında sentetik EUR/USD veri kümesini, mevcut tam tarih aralığını ve bir deney adını seç.',
        'Özellikler adımında birkaç hazır indikatör seç; Modeller adımında tek bir uzman modelle başla. İlk denemede rejim yönlendirmesini kapalı bırakabilirsin.',
        'Optimizasyonu kapalı veya küçük bir aralıkta bırak. Validasyonda varsayılan fold/train-test ayarlarını, maliyet alanlarında da demo varsayılanlarını kullan.',
        'İnceleme ekranında taslağı kaydet, deney detayında Çalıştır düğmesine bas ve logların tamamlanmasını bekle.',
        'Tamamlanınca Genel Bakış, Validasyon ve Rejimler sekmelerini sırayla aç. Son olarak aynı deneyi farklı maliyet veya modelle yeniden çalıştırıp Geçmiş ekranında karşılaştır.'
      ],
      tip: 'Demo eğitim amaçlıdır; sentetik veriyle alınan performansı gerçek piyasaya veya gerçek para kararına doğrudan taşıma.'
    }
  ] : [
    {
      number: '01', title: 'Sign in and understand the workspace',
      intro: 'Regime Lab lets you build controlled backtests without writing code. The left menu switches screens; the profile menu opens account settings.',
      steps: [
        'Read the Get started page first. Language and theme are changed from Account & Profile Settings in the profile menu.',
        'If you use a workspace or project selector, confirm that you are in the intended workspace. Experiments, data snapshots, and usage limits are scoped to it.',
        'Use synthetic EUR/USD data for the first run. For real research, upload your own data through Data Hub.'
      ],
      tip: 'To reproduce a result, record the data snapshot, date range, costs, and seed used by the experiment.'
    },
    {
      number: '02', title: 'Prepare and inspect the data',
      intro: 'A good backtest starts with correctly ordered time-series data. Data Hub is where you inspect uploaded files and immutable snapshots.',
      steps: [
        'Open Data Hub from the left menu. Choose synthetic data for the demo or click Upload CSV for your own file.',
        'Confirm that the CSV has at least Timestamp, Open, High, Low, and Close columns. Timestamps should be ordered and unique.',
        'For macro or cross-asset data, use the macro__, cross_asset__, fx__, or rates__ prefix and provide __available_at when the value became observable.',
        'Open the dataset preview and check the first/last dates, missing values, and price columns. This is the dataset selected by experiments.'
      ],
      tip: 'Do not feed future information directly to a model. Availability time must be no later than the observation time.'
    },
    {
      number: '03', title: 'Create an experiment and choose dates',
      intro: 'Experiment Platform builds a backtest specification step by step. You can save it as a draft before running it.',
      steps: [
        'Click Create experiment on this page or New experiment in Experiment Platform.',
        'In Data, enter a name, select a dataset, set the timeframe, and add a description. Keep the dates inside the dataset range.',
        'Split the period into train for learning, validation for choosing settings, and test for the final locked check.',
        'Use Next to move forward. You can go back and change earlier choices; Review shows the complete specification.'
      ],
      tip: 'Do not use the test period to make decisions. It should remain the final check on unseen data.'
    },
    {
      number: '04', title: 'Choose indicators and signals',
      intro: 'The Features step provides precomputed causal indicators. They use the current bar and history, not future bars.',
      steps: [
        'Search for indicators in Features and select the families you need: trend, momentum, volatility, or price.',
        'Start with a small set such as RSI, EMA, ATR, or Bollinger. Review the feature preview and avoid adding many redundant columns.',
        'Choose long and short signal filters. Selecting a model alone does not automatically create a robust trading strategy.',
        'Continue to Models. If you change features, reassess optimization and validation results.'
      ],
      tip: 'If you cannot explain when an indicator became available, do not use it until its availability timing is defined.'
    },
    {
      number: '05', title: 'Select models and regime routing',
      intro: 'Expert models look for different market behaviours. Optional regime routing lets different specialists handle different states.',
      steps: [
        'Select at least one model in Models. Select several when you want validation to compare trend, momentum, and volatility specialists.',
        'To use routing, enable regime-based model routing, choose a fallback model, and assign a model to each regime state.',
        'Set the minimum bars per state. When a state has too little history, the system falls back and reports that choice in the result.',
        'Do not call state numbers bull or bear by default. Interpret each state from its volatility, trend, and performance.'
      ],
      tip: 'Start with one model, then enable routing and compare whether it improves stability rather than assuming it will.'
    },
    {
      number: '06', title: 'Configure optimization and validation',
      intro: 'These settings define how choices are searched and which data is allowed to influence them. The goal is not to select by test performance.',
      steps: [
        'Choose off, grid, random, or genetic optimization. Start with off or a small search space for the first run.',
        'Keep parameter bounds and candidate counts practical. A huge search can overfit and take longer.',
        'Choose rolling or walk-forward validation, fold count, train/validation ratio, and purge/gap when needed.',
        'Enter realistic commission, slippage, starting capital, and random seed. Costs are included in the metrics.'
      ],
      tip: 'Validation selects settings; test measures the frozen choice on data that was not previously seen.'
    },
    {
      number: '07', title: 'Save the draft and run it',
      intro: 'Review shows the full specification before execution. Run starts the real backtest workflow rather than displaying a placeholder result.',
      steps: [
        'Review data, date partitions, features, models, optimization, validation, and costs.',
        'Save the draft. An experiment code is created; open the detail view to edit or run it.',
        'Click Run. Follow the logs through data preparation, indicators, training, optimization, validation, and test.',
        'If it fails, the status and error log are shown in red. Fix the columns, dates, row count, or model settings and run again.'
      ],
      tip: 'When a run finishes unusually quickly, inspect its logs and experiment code. A successful run records training, validation, test, and metric stages.'
    },
    {
      number: '08', title: 'Read the results correctly',
      intro: 'The result view is more than a single return number. Each tab answers a different question.',
      steps: [
        'In Overview, check test dates, total return, Sharpe, maximum drawdown, trade count, and the equity curve.',
        'Use Features for selected indicators and their effects; Optimization for candidates and the validation-based selection.',
        'Use Validation to compare folds and the validation-test gap. A large gap can indicate instability or overfitting.',
        'Use Regimes for state share, transitions, and regime performance. Lineage and Artifacts show the data/config trace and generated files.',
        'Repeat with different costs, dates, or models. A single green result is not a guarantee of future returns.'
      ],
      tip: 'A strong result combines reasonable drawdown, stable folds, realistic after-cost performance, and a small validation-test gap.'
    },
    {
      number: '09', title: 'Use History and Notebook Lab',
      intro: 'Notebook Lab runs code-based research and can convert a successful notebook into a platform experiment. History helps you find earlier work.',
      steps: [
        'Use search and status filters in History to find an experiment, then open its code for details, logs, and results.',
        'Upload a notebook in Notebook Lab, check its parameters, click Run, and follow live logs.',
        'When it succeeds, click Convert to experiment. The created experiment code appears in the notice and the related experiment opens automatically.',
        'Review the converted dataset snapshot, model, and lineage; compare the notebook result with the no-code backtest when needed.'
      ],
      tip: 'Automatic navigation opens the converted experiment for inspection; click Run there if the converted experiment still needs execution.'
    },
    {
      number: '10', title: 'Use the research chatbot',
      intro: 'The right-side chatbot helps explain results and prepare research questions. Treat its answer as assistance, not as a replacement for logs and metrics.',
      steps: [
        'Open the chatbot. Pinning fixes it to the right and shifts the site left; fullscreen expands the panel.',
        'Choose a prepared question or search for one. Add your own question when the library does not cover your need.',
        'Pin important chats, copy an answer, or export it. Change the application language from account settings when needed.',
        'Review any requested action or data access. Verify important conclusions against experiment results, validation, and logs.'
      ],
      tip: 'The chatbot is a research assistant, not a guarantee of future returns or a way to make a weak backtest reliable.'
    },
    {
      number: '11', title: 'Manage profile and security',
      intro: 'Account & Profile controls personal information, language/theme preferences, and active sessions.',
      steps: [
        'Open the profile menu and choose Account & Profile Settings. Overview shows experiment and workspace usage.',
        'Change display name, language, or theme in Settings and save the section.',
        'Verify your current account before changing email or password. Other sessions are expected to be revoked after a password change.',
        'Review active devices and last-used times in Sessions and revoke anything unfamiliar.'
      ],
      tip: 'Never share passwords or session information with the chatbot. Change credentials only from the account page.'
    },
    {
      number: '12', title: 'Demo: run your first experiment end to end',
      intro: 'This flow lets a first-time user complete a safe synthetic-data demo from start to finish.',
      steps: [
        'Click Start demo experiment at the bottom of this page. The app opens a new experiment wizard with synthetic EUR/USD data.',
        'In Data, keep the synthetic dataset, use its available full date range, and enter an experiment name.',
        'Select a few prepared indicators, choose one expert model, and leave regime routing off for the first run.',
        'Keep optimization off or small, use the default validation split, and leave the demo cost defaults in place.',
        'Save the draft from Review, click Run in the experiment detail, and wait for the logs to finish.',
        'Open Overview, Validation, and Regimes in order. Then rerun with a different cost or model and compare both runs in History.'
      ],
      tip: 'This demo is educational. Do not transfer synthetic-data performance directly to live markets or real-money decisions.'
    }
  ];
  const screenLinks = tr ? [
    [{ id: 'getstarted', label: 'Başlarken' }],
    [{ id: 'data', label: 'Veri Merkezi' }],
    [{ id: 'platform', label: 'Deney Platformu' }],
    [{ id: 'platform', label: 'Deney Platformu' }],
    [{ id: 'platform', label: 'Deney Platformu' }, { id: 'models', label: 'Uzman Modeller' }, { id: 'regimes', label: 'Piyasa Rejimleri' }],
    [{ id: 'platform', label: 'Deney Platformu' }, { id: 'method', label: 'Metodoloji' }],
    [{ id: 'platform', label: 'Deney Platformu' }, { id: 'overview', label: 'Çalışma Alanı' }],
    [{ id: 'overview', label: 'Çalışma Alanı' }, { id: 'models', label: 'Uzman Modeller' }, { id: 'regimes', label: 'Piyasa Rejimleri' }, { id: 'platform', label: 'Deney Platformu' }],
    [{ id: 'history', label: 'Önceki Deneyler' }, { id: 'notebook', label: 'Notebook Lab' }],
    [{ id: 'getstarted', label: 'Başlarken' }],
    [{ id: 'account', label: 'Hesap ve Profil' }],
    [{ id: 'platform', label: 'Deney Platformu' }, { id: 'overview', label: 'Çalışma Alanı' }, { id: 'history', label: 'Önceki Deneyler' }]
  ] : [
    [{ id: 'getstarted', label: 'Get started' }],
    [{ id: 'data', label: 'Data hub' }],
    [{ id: 'platform', label: 'Experiment platform' }],
    [{ id: 'platform', label: 'Experiment platform' }],
    [{ id: 'platform', label: 'Experiment platform' }, { id: 'models', label: 'Expert models' }, { id: 'regimes', label: 'Market regimes' }],
    [{ id: 'platform', label: 'Experiment platform' }, { id: 'method', label: 'Methodology' }],
    [{ id: 'platform', label: 'Experiment platform' }, { id: 'overview', label: 'Workspace' }],
    [{ id: 'overview', label: 'Workspace' }, { id: 'models', label: 'Expert models' }, { id: 'regimes', label: 'Market regimes' }, { id: 'platform', label: 'Experiment platform' }],
    [{ id: 'history', label: 'Experiment history' }, { id: 'notebook', label: 'Notebook Lab' }],
    [{ id: 'getstarted', label: 'Get started' }],
    [{ id: 'account', label: 'Account & Profile' }],
    [{ id: 'platform', label: 'Experiment platform' }, { id: 'overview', label: 'Workspace' }, { id: 'history', label: 'Experiment history' }]
  ];
  const screens = [
    { id: 'platform', icon: FlaskConical, title: t('getStarted.platformTitle'), text: t('getStarted.platformText'), usage: t('getStarted.platformUse') },
    { id: 'overview', icon: LayoutDashboard, title: t('getStarted.overviewTitle'), text: t('getStarted.overviewText'), usage: t('getStarted.overviewUse') },
    { id: 'data', icon: Database, title: t('getStarted.dataTitle'), text: t('getStarted.dataText'), usage: t('getStarted.dataUse') },
    { id: 'models', icon: Layers3, title: t('getStarted.modelsTitle'), text: t('getStarted.modelsText'), usage: t('getStarted.modelsUse') },
    { id: 'regimes', icon: Activity, title: t('getStarted.regimesTitle'), text: t('getStarted.regimesText'), usage: t('getStarted.regimesUse') },
    { id: 'notebook', icon: BookOpen, title: t('getStarted.notebookTitle'), text: t('getStarted.notebookText'), usage: t('getStarted.notebookUse') },
    { id: 'platform', icon: Sparkles, title: t('getStarted.resultsTitle'), text: t('getStarted.resultsText'), usage: t('getStarted.resultsUse') },
    { id: 'history', icon: History, title: t('getStarted.historyTitle'), text: t('getStarted.historyText'), usage: t('getStarted.historyUse') },
    { id: 'method', icon: CircleHelp, title: t('getStarted.methodTitle'), text: t('getStarted.methodText'), usage: t('getStarted.methodUse') },
    { id: 'account', icon: ShieldCheck, title: t('getStarted.accountTitle'), text: t('getStarted.accountText'), usage: t('getStarted.accountUse') },
  ];

  return <div className="getting-started">
    <section className="panel getting-started-hero">
      <div className="getting-started-hero-icon"><Sparkles size={25} /></div>
      <div>
        <span className="eyebrow">{t('getStarted.kicker')}</span>
        <h2>{t('getStarted.title')}</h2>
        <p>{t('getStarted.intro')}</p>
      </div>
      <div className="getting-started-actions"><button className="secondary" onClick={onStartTour}><Sparkles size={16} />{tr ? 'Uygulama turunu başlat' : 'Start application tour'}</button><button className="primary" onClick={onNewExperiment}><FlaskConical size={16} />{t('getStarted.startButton')}</button></div>
    </section>

    <section className="getting-started-steps" aria-label={t('getStarted.kicker')}>
      <div><span>1</span><b>{t('getStarted.step1')}</b></div>
      <ArrowRight size={16} />
      <div><span>2</span><b>{t('getStarted.step2')}</b></div>
      <ArrowRight size={16} />
      <div><span>3</span><b>{t('getStarted.step3')}</b></div>
    </section>

    <section className="panel getting-started-start">
      <div><h3>{t('getStarted.startTitle')}</h3><p>{t('getStarted.startText')}</p></div>
      <div className="getting-started-start-actions"><button className="text-button" onClick={onStartTour}><Sparkles size={14} />{tr ? 'Turu tekrar başlat' : 'Restart tour'}</button><button className="secondary" onClick={onNewExperiment}>{t('getStarted.startButton')} <ArrowRight size={14} /></button></div>
    </section>

    <section className="full-manual" aria-label={tr ? 'Baştan sona kullanım kılavuzu' : 'End-to-end user manual'}>
      <div className="manual-heading">
        <span className="eyebrow">{tr ? 'BAŞTAN SONA KULLANIM KILAVUZU' : 'END-TO-END USER MANUAL'}</span>
        <h3>{tr ? 'Regime Lab’i ilk girişten sonuç karşılaştırmaya kadar kullan' : 'Use Regime Lab from first sign-in to result comparison'}</h3>
        <p>{tr ? 'Aşağıdaki sırayı izlersen veri hazırlamadan güvenli bir demo çalıştırmaya kadar bütün akışı tamamlayabilirsin.' : 'Follow these sections in order to complete the full flow from data preparation to a safe demo run.'}</p>
      </div>
      <div className="manual-sections">
        {manualSections.map((section, index) => <article className="manual-section" key={section.number}>
          <div className="manual-number">{section.number}</div>
          <div className="manual-content">
            <h4>{section.title}</h4>
            <div className="manual-related"><span>{tr ? 'Bu adımın ekranları' : 'Screens for this step'}</span>{screenLinks[index].map(screen => <button key={`${section.number}-${screen.id}`} onClick={() => onNavigate(screen.id)}>{screen.label}<ArrowRight size={11} /></button>)}</div>
            <p className="manual-intro">{section.intro}</p>
            <ol>{section.steps.map(step => <li key={step}>{step}</li>)}</ol>
            {section.number === '04' && <div className="indicator-reference">
              <div className="indicator-reference-heading"><div><b>{tr ? 'Hazır indikatörlerin tamamı' : 'All prepared indicators'}</b><span>{tr ? 'Her satır seçilebilir bir feature kolonunu açıklar.' : 'Each row describes a selectable feature column.'}</span></div></div>
              <div className="indicator-table-wrap"><table className="indicator-table"><thead><tr><th>{tr ? 'İndikatör' : 'Indicator'}</th><th>{tr ? 'Ne işe yarar?' : 'What does it do?'}</th><th>{tr ? 'Ürettiği sonuç' : 'Output'}</th><th>{tr ? 'Nasıl yorumlanır?' : 'How to read it'}</th></tr></thead><tbody>{indicatorRows.map(row => <tr key={row.name}><td><code>{row.name}</code></td><td>{row.purpose}</td><td>{row.output}</td><td>{row.reading}</td></tr>)}</tbody></table></div>
            </div>}
            {section.number === '04' && <div className="indicator-reference finance-terms-reference">
              <div className="indicator-reference-heading"><div><b>{tr ? 'Finansal ifadeler sözlüğü' : 'Financial terms glossary'}</b><span>{tr ? 'Bu ifadeler sinyal ve backtest sonucunu okurken karşına çıkar.' : 'These terms appear while selecting signals and reading backtest results.'}</span></div></div>
              <div className="indicator-table-wrap"><table className="indicator-table finance-terms-table"><thead><tr><th>{tr ? 'Finansal ifade' : 'Financial term'}</th><th>{tr ? 'Bu ifade nedir?' : 'What is it?'}</th><th>{tr ? 'Ne işe yarar?' : 'What is it used for?'}</th></tr></thead><tbody>{financeTerms.map(row => <tr key={row.term}><td><b>{row.term}</b></td><td>{row.definition}</td><td>{row.use}</td></tr>)}</tbody></table></div>
            </div>}
            <div className="manual-tip"><CircleHelp size={15} /><span><b>{tr ? 'İpucu' : 'Tip'}</b>{section.tip}</span></div>
          </div>
        </article>)}
      </div>
    </section>

    <div className="screen-guide-grid">
      {screens.map(({ id, icon: Icon, title, text, usage }) => <button className="screen-guide-card" key={`${id}-${title}`} onClick={() => onNavigate(id)}>
        <span className="screen-guide-icon"><Icon size={20} /></span>
        <span className="screen-guide-copy"><b>{title}</b><small>{text}</small><em><strong>{t('getStarted.useLabel')}:</strong> {usage}</em></span>
        <ArrowRight size={15} className="screen-guide-arrow" />
      </button>)}
    </div>

    <section className="getting-started-tip">
      <CircleHelp size={18} />
      <div><b>{t('getStarted.tipTitle')}</b><p>{t('getStarted.tipText')}</p></div>
    </section>

    <section className="panel getting-started-demo">
      <div className="getting-started-demo-icon"><FlaskConical size={22} /></div>
      <div><h3>{t('getStarted.demoTitle')}</h3><p>{t('getStarted.demoText')}</p><small>{t('getStarted.demoNote')}</small></div>
      <button className="primary" onClick={onDemo}><Sparkles size={16} />{t('getStarted.demoButton')}</button>
    </section>
  </div>;
}
