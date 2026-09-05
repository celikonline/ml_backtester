"""Minimal TR->EN localization for user-facing API error messages.

The UI sends `Accept-Language: tr|en`. Stored artifacts (run logs, notes,
computed result texts) keep the language they were created with; only
request-scoped error responses are translated here.
"""
from __future__ import annotations

EXACT = {
    "Kayıt bulunamadı.": "Record not found.",
    "Veri seti bulunamadı.": "Dataset not found.",
    "Deney bulunamadı.": "Experiment not found.",
    "En fazla 25 MB CSV yükleyebilirsiniz.": "You can upload at most a 25 MB CSV.",
    "Çalıştırma iptal edildi.": "Run cancelled.",
    "Deney tamamlandı": "Experiment completed",
    "Çalıştırma hazırlanıyor": "Preparing run",
    "Zaten çalışan bir deney var. Tamamlanmasını bekleyin veya iptal edin.": "An experiment is already running. Wait for it to finish or cancel it.",
    "Bu deney şu anda çalışmıyor.": "This experiment is not running right now.",
    "Mevcut eğitim adımından sonra iptal edilecek": "Will cancel after the current training step",
    "Önce deney tamamlanmalı.": "The experiment must complete first.",
    "API anahtarı gerekli.": "API key required.",
    "Yerel mod yalnızca localhost istemcilerine açıktır.": "Local mode only accepts localhost clients.",
    "Bu Origin izinli değil.": "This Origin is not allowed.",
    "Geçersiz event cursor.": "Invalid event cursor.",
    "Artifact bulunamadı.": "Artifact not found.",
    "Snapshot bulunamadı.": "Snapshot not found.",
    "Snapshot hash doğrulaması başarısız.": "Snapshot hash verification failed.",
    "Geçersiz artifact yolu.": "Invalid artifact path.",
    "Araştırma bütçesi/multiple-testing riski politika sınırını aşıyor.": "Research budget / multiple-testing risk exceeds the policy limit.",
    "Bilinmeyen özellik adı.": "Unknown feature name.",
    "Klon aynı snapshot'ı kullanır. Başka veri için yeni deney oluşturun.": "A clone reuses the same snapshot. Create a new experiment for different data.",
    "Çalıştırılmış deney sabittir; klon oluşturun.": "An experiment that has run is frozen; clone it.",
    "Veri değişikliği yeni deney gerektirir.": "A data change requires a new experiment.",
    "Deney çalıştırılmaya başlandı.": "The experiment has started running.",
    "Aynı anahtar başka bir deneyde kullanılmış.": "The same key was already used on another experiment.",
    "Sıraya alındı": "Queued",
    "İş kuyruğu dolu.": "Job queue is full.",
    "Her deney bir kez çalıştırılır. Yeni çalışma için klonlayın.": "Each experiment runs once. Clone it for a new run.",
    "Çalıştırma zaten kaydedilmiş.": "Run already recorded.",
    "Çalıştırma durduruldu.": "Run stopped.",
    "Geçersiz durum geçişi.": "Invalid state transition.",
    "Aktif çalışma yok.": "No active run.",
    "İptal istendi": "Cancellation requested",
    "Sonuç henüz hazır değil.": "Result is not ready yet.",
    "2–5 farklı deney seçin.": "Select 2–5 different experiments.",
    "Sunucu yeniden başladı; önceki çalışma kesildi. Klon ile yeniden çalıştırın.": "Server restarted; the previous run was interrupted. Re-run via a clone.",
    "Worker başlıyor": "Worker starting",
    "İptal edildi": "Cancelled",
    "Çalışma süresi sınırı aşıldı": "Runtime limit exceeded",
    "Worker sonuç kaydetmeden kapandı.": "Worker exited without saving results.",
    "Elitizm popülasyondan küçük; minimum özellik maksimumdan küçük/eşit olmalı.": "Elitism must be smaller than the population; min features must be <= max features.",
    "Deney adı boş olamaz.": "Experiment name cannot be empty.",
    "Doğrulama düşüş sınırını sağlayan aday yok. Test açılmadı.": "No candidate satisfies the validation drawdown bound. Test was not opened.",
    "Test seal'i geçersiz kılınmış; yeni temporal holdout oluşturun.": "Test seal was invalidated; create a new temporal holdout.",
    "CSV okunamadı. UTF-8 ve virgülle ayrılmış dosya kullanın.": "CSV could not be read. Use a UTF-8, comma-separated file.",
    "Tekrarlanan sütun adları var.": "Duplicate column names found.",
    "Geçersiz tarih, eksik veya sonsuz fiyat bulundu. Dosyayı temizleyin.": "Invalid dates, missing or infinite prices found. Clean the file.",
    "Tüm fiyatlar sıfırdan büyük olmalı.": "All prices must be greater than zero.",
    "OHLC tutarsız: High en yüksek, Low en düşük fiyat olmalı.": "Inconsistent OHLC: High must be the highest and Low the lowest price.",
    "Tekrarlanan zaman damgaları var.": "Duplicate timestamps found.",
    "CSV 400 ile 200.000 satır arasında olmalı.": "CSV must have between 400 and 200,000 rows.",
    "Seçilen periyot kaynak veriden daha küçük olamaz.": "The selected period cannot be smaller than the source data.",
    "Periyot dönüşümünden sonra en az 400 bar gerekli.": "At least 400 bars are required after period conversion.",
    "Açılış fiyatlarında tek barda %100 veya üzeri değişim var. EUR/USD verisini kontrol edin.": "Open prices move by 100% or more in a single bar. Check the EUR/USD data.",
    "Eğitim, doğrulama ve test bölümleri için yeterli bar yok.": "Not enough bars for the train, validation and test splits.",
    "Kaynak periyodundan küçük aralık seçilemez.": "Cannot select an interval smaller than the native period.",
    "Özellik seçimi geçersiz.": "Invalid feature selection.",
    "Hedef getiriler geçersiz veya tek barda %100 üzerinde.": "Target returns are invalid or exceed 100% in a single bar.",
    "Dönüşümden sonra yeterli eğitim/test barı yok (en az 160/40).": "Not enough train/test bars after conversion (at least 160/40).",
    "Desteklenmeyen model adapter'ı.": "Unsupported model adapter.",
    "Idempotency-Key başlığı gerekli (1–120 karakter).": "Idempotency-Key header is required (1–120 characters).",
}

PREFIX = {
    "Eksik sütunlar:": "Missing columns:",
    "Hesaplama sınırı:": "Compute limit:",
}


def wants_english(lang: str | None) -> bool:
    if not lang:
        return False
    return lang.split(",")[0].strip().lower().startswith("en")


def translate(message: str, lang: str | None) -> str:
    if not wants_english(lang) or not isinstance(message, str):
        return message
    if message in EXACT:
        return EXACT[message]
    for tr_prefix, en_prefix in PREFIX.items():
        if message.startswith(tr_prefix):
            return en_prefix + message[len(tr_prefix):]
    return message
