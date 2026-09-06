# No-code ML backtest

Deney Platformu → Yeni deney sihirbazına entegredir.

1. Veri ve bar periyodunu seçin. Başlangıç/bitiş tarihleri UTC'dir; bitiş günü dahildir.
2. Özellikler sekmesinde indikatörler ön hesaplanır. Hazır özelliklerden model girdilerini seçin.
3. İsteğe bağlı long/short sinyal koşullarını ekleyin. Koşullar AND ile birleştirilir; model tahminini filtreler. Filtre geçmezse o bar flat olur. Ayrı pozisyon taşıma/çıkış kural motoru değildir.
4. Ridge, Random Forest, HistGradientBoosting, XGBoost veya LightGBM seçin.
5. Sabit karşılaştırma, genetik, random veya grid arama seçin. Grid mevcut üç model parametre profili ve sinyal eşikleri üzerinde çalışır; random/genetik özellik alt kümesi de arar. En fazla 128 aday.
6. Holdout, walk-forward, purged K-fold, rolling veya anchored validasyon seçin. Train/validation oranlarını ve isteğe bağlı final test başlangıç tarihini belirtin. Tarih verildiğinde önceki dönem geliştirme verisidir. Final model geliştirme verisinin tamamıyla yeniden eğitilir.
7. Taslağı kaydedin; deney detayındaki Çalıştır ile gerçek worker eğitimini başlatın. Sonuçlar mevcut deney ekranlarına kaydedilir.

Yeni hazır indikatörler 7/14/21/50 periyotlarında RSI, EMA uzaklığı, normalize ATR ve Bollinger bant konumudur. Eski `rsi` 0–1, yeni `rsi_14` vb. 0–100 ölçeğindedir. EMA close/EMA−1, ATR ATR/close, Bollinger konumu alt bantta 0 ve üst bantta 1'dir. Eksik indikatör değerleri doldurulmaz.

Ön hesaplama sadece nedensel indikatörler içindir. Ölçekleme/model öğrenimi eğitim bölümlerinde yapılır. Cache `data/platform/feature_cache` altında sayısal NPZ dosyalarıdır; anahtar veri, indikatör kodu ve pandas sürümünü içerir. Aday optimizasyonuna final test verilmez.

API: `POST /api/v1/backtest-preview` bir ExperimentSpec kabul eder ve kullanılabilir özelliklerin geçerli bar sayılarını döndürür. Aynı spec normal deney oluşturma endpoint'ine gönderilir. Yeni alanlar `period`, `signal_rules`, `validation.validation_ratio`; eski deneyler varsayılanlarla uyumludur.

Bu sürüm doğal dilden strateji üretimi, bağımsız kural stratejileri, SL/TP emirleri ve Bayesian optimizasyon içermez. Notebook içindeki Python ifadeleri çalıştırılmaz; kurallar doğrulanan JSON alanlarından değerlendirilir.
