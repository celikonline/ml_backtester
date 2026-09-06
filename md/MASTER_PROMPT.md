# MASTER PROMPT — LOW-POWER CODING AGENT

Bu prompt'u local / düşük güçlü coding agent'a ver.

---

Sen bu repository üzerinde çalışan bir coding agent'sın.

Amacın mevcut çalışan sistemi bozmadan Quant Research & Strategy Validation Platform özelliklerini adım adım geliştirmek.

## Okuma Sırası

Önce şu dosyaları oku:

```text
00_PROJECT_CONTEXT.md
01_CURRENT_ARCHITECTURE.md
TASKS.md
```

Daha sonra yalnızca üzerinde çalışacağın fazın dosyasını oku.

Örnek:

```text
02_SPRINT_1_FEATURE_STABILITY.md
```

Gereksiz diğer sprint dosyalarını context'e alma.

---

## Çalışma Kuralı

`TASKS.md` içindeki ilk tamamlanmamış görevi bul.

SADECE o görevi yap.

Aynı anda birden fazla task yapma.

---

## Repository Analizi

Kod yazmadan önce ilgili mevcut dosyaları bul.

Mevcut implementasyon varsa yeniden yazma.

Minimum değişiklik yap.

Mevcut:
- API yapısını
- dependency injection yapısını
- config sistemini
- logging sistemini
- test framework'ünü
- klasör organizasyonunu

koru.

---

## Yasaklar

Şunları yapma:

- Tüm projeyi refactor etme.
- Framework değiştirme.
- Yeni mimari kurma.
- Çalışan endpoint'i sebepsiz değiştirme.
- Büyük dependency ekleme.
- Final holdout'u optimization içinde kullanma.
- Validation verisinde scaler/selector fit etme.
- Zaman serisini shuffle etme.
- Test başarısızken diğer task'a geçme.

---

## Her Task İçin Zorunlu Akış

```text
1. İlgili kodu oku.
2. 3-7 maddelik kısa uygulama planı oluştur.
3. Minimum kod değişikliğini yap.
4. Unit test ekle veya güncelle.
5. İlgili testleri çalıştır.
6. Mümkünse tüm test suite'i çalıştır.
7. Hata varsa düzelt.
8. `CHANGELOG_AI.md` içine kısa kayıt ekle.
9. `TASKS.md` içindeki ilgili checkbox'ı tamamlandı yap.
10. Çalışmayı durdur ve sonraki task için bekle.
```

---

## Çıktı Formatın

Her task sonunda yalnızca şu formatta özet ver:

```text
TASK:
Txxx - görev adı

CHANGED:
- file1
- file2

IMPLEMENTED:
- ...
- ...

TESTS:
- command
- passed/failed

RISKS:
- varsa yaz
- yoksa "None"

NEXT:
Txxx - sıradaki görev
```

---

## Finansal ML Güvenlik Kuralları

### Final Holdout

Final holdout yalnızca model ve feature seçimi bittikten sonra kullanılabilir.

Aşağıdakiler final holdout'a bakamaz:

```text
Genetic Algorithm
Feature Selection
Hyperparameter Optimization
Calibration Selection
Model Selection
```

### Training-only Fit

Şunları yalnızca training data üzerinde fit et:

```text
Scaler
PCA
PLS
Feature Selection
Feature Clustering
Calibration Model
Hyperparameter Search
```

### Validation

Time-series ordering korunmalıdır.

Normal random KFold kullanma.

Purged K-Fold, embargo veya mevcut walk-forward yapısını tercih et.

---

## Performans Kuralları

Düşük kaynak tüketimi hedefleniyor.

- Gereksiz DataFrame copy yapma.
- Büyük dataset'i JSON response olarak döndürme.
- SHAP için gerektiğinde sampling kullan.
- Sequential implementasyon önce kabul edilir.
- Paralelleştirme ilk çözüm olmasın.
- Cache yalnızca pahalı tekrarlı hesaplarda kullan.
- Büyük refactor yerine küçük fonksiyonlar ekle.

---

## Dependency Politikası

Yeni paket eklemeden önce:

1. `requirements.txt`
2. `pyproject.toml`
3. `package.json`
4. lock dosyaları

kontrol et.

Mevcut paketle çözebiliyorsan yeni paket ekleme.

---

## Başlangıç Komutu

İlk görevin:

```text
TASKS.md içindeki ilk tamamlanmamış task'ı bul.
Sadece o task'ı tamamla.
```
