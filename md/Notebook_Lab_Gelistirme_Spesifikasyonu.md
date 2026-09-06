# Notebook Lab Geliştirme Spesifikasyonu

## 1. Amaç

Bu doküman, mevcut **Notebook Lab** ekranını yalnızca notebook kaydı yöneten bir ekrandan çıkarıp, yüklenen `.ipynb` dosyasının gerçekten görüntülenebildiği, incelenebildiği, çalıştırılabildiği ve daha sonra platform içindeki experiment pipeline'ına dönüştürülebildiği bir çalışma alanına çevirmek için hazırlanmıştır.

Hedef akış:

```text
Notebook Upload
      ↓
Notebook Viewer
      ↓
Cell / Output Inspection
      ↓
Static Analysis
      ↓
Run / Version / Artifact Management
      ↓
Notebook → Experiment
      ↓
Quant Research Pipeline
```

Bu geliştirme düşük güçlü / local AI tarafından küçük task'lar halinde uygulanmalıdır.

---

# 2. Mevcut Ekrandaki Sorun

Mevcut Notebook Lab ekranında kullanıcı notebook adı, kodu, versiyonu, dosya adı, durum, oluşturma/güncelleme tarihi, çalıştırma, yeni versiyon, arşiv, çalıştırmalar, versiyonlar ve artifacts bilgilerini görebiliyor.

Ancak kullanıcı yüklenen `.ipynb` dosyasının gerçek içeriğini göremiyor.

Eksik olan ana özellik:

```text
Notebook'un kendisini görüntüleme
```

Kullanıcı `auto_clean.ipynb` dosyasını görüyor ama:

- Markdown hücrelerini
- Code hücrelerini
- Output'ları
- Grafikleri
- DataFrame sonuçlarını
- Error çıktılarını
- Execution count bilgisini

göremiyor.

---

# 3. Hedef Notebook Lab Navigasyonu

Mevcut sekmeler:

```text
Genel Bakış
Çalıştırmalar
Versiyonlar
Artifacts
```

şu hale getirilmelidir:

```text
Notebook
Genel Bakış
Çalıştırmalar
Versiyonlar
Artifacts
```

Varsayılan sekme `Notebook` olmalıdır.

---

# 4. Notebook Viewer

## Amaç

Yüklenen `.ipynb` dosyasındaki hücreleri sırayla görüntülemek.

Notebook formatı JSON'dur. Backend `.ipynb` dosyasını okuyarak:

```python
notebook["cells"]
```

alanını parse etmelidir.

İlk sürümde desteklenecek cell tipleri:

```text
code
markdown
raw
```

Örnek cell:

```json
{
  "cell_type": "code",
  "execution_count": 1,
  "metadata": {},
  "source": [
    "import pandas as pd\n",
    "df = pd.read_csv('eurusd.csv')"
  ],
  "outputs": []
}
```

---

# 5. Notebook Viewer Arayüzü

Örnek:

```text
┌───────────────────────────────────────────────────────────────┐
│ auto_clean.ipynb                     v1       ACTIVE          │
│                                              ▶ Çalıştır       │
├───────────────────────────────────────────────────────────────┤
│ CELL 1                                          MARKDOWN      │
│ # Data Preparation                                            │
│ EUR/USD dataset is loaded and normalized.                     │
├───────────────────────────────────────────────────────────────┤
│ CELL 2                                          CODE          │
│ [1] import pandas as pd                                       │
│     import numpy as np                                        │
│     df = pd.read_csv("eurusd.csv")                            │
│                                      ▶ Hücreyi Çalıştır       │
├───────────────────────────────────────────────────────────────┤
│ OUTPUT                                                        │
│ rows: 42183                                                   │
│ columns: 57                                                   │
├───────────────────────────────────────────────────────────────┤
│ CELL 3                                          CODE          │
│ df["return"] = df["close"].pct_change()                       │
└───────────────────────────────────────────────────────────────┘
```

---

# 6. Notebook Görüntüleme Modları

Notebook ekranında üç mod bulunmalıdır:

```text
Görüntüle
Düzenle
Çalıştır
```

## Görüntüle

Read-only.

Göster:

- Markdown
- Code
- Outputs
- Execution Count
- Cell Type

## Düzenle

İkinci fazda:

- Cell edit
- Cell add
- Cell delete
- Cell move up
- Cell move down
- Markdown edit
- Code edit

## Çalıştır

İkinci fazda:

- Run Cell
- Run All
- Run From Here
- Restart & Run All

---

# 7. Notebook Outline

Notebook'un sol tarafında navigation panel bulunmalıdır.

Örnek:

```text
NOTEBOOK

01  Data Loading
02  Data Cleaning
03  Feature Engineering
04  HMM Regime Detection
05  Model Training
06  Genetic Optimization
07  Walk Forward
08  Backtest
09  Metrics
10  Final Results
```

Outline öncelikle Markdown heading'lerden oluşturulmalıdır.

Notebook içinde ilgili cell'e scroll yapılmalıdır.

---

# 8. Cell Metadata

Her cell için frontend'e şu bilgiler gönderilebilir:

```json
{
  "cell_id": "cell-001",
  "index": 1,
  "cell_type": "code",
  "execution_count": 3,
  "source": "...",
  "output_count": 2,
  "tags": []
}
```

---

# 9. Quant Cell Classification

Notebook cell'leri platform tarafından sınıflandırılabilir.

İlk sürümde rule-based yaklaşım yeterlidir.

Kategoriler:

```text
DATA
FEATURE
MODEL
VALIDATION
BACKTEST
PLOT
OTHER
```

Örnek:

```text
CELL 17
FEATURE ENGINEERING
```

Sınıflandırma için AI şart değildir. İlk sürümde AST + regex + import/function detection yeterlidir.

---

# 10. Static Notebook Analysis

Notebook açıldığında backend statik analiz yapmalıdır.

Gösterilecek bilgiler:

```text
Total Cells
Code Cells
Markdown Cells
Raw Cells
Output Count
Detected Datasets
Detected Features
Detected Models
Detected Validation Methods
Detected Backtest Components
```

Örnek:

```text
NOTEBOOK ANALYSIS

Cells                 48
Code Cells             31
Markdown               17

Detected Datasets       3
Detected Features      57
Detected Models         4

Models
✓ XGBoost
✓ Random Forest
✓ Ridge
✓ HMM

Validation
✓ Walk Forward
⚠ Purged K-Fold bulunamadı
⚠ Embargo bulunamadı

Backtest
✓ Sharpe
✓ Return
✓ Drawdown
```

---

# 11. Python AST Analizi

Notebook code cell'leri tek tek analiz edilmelidir.

AST ile yakalanabilecek örnekler:

```python
XGBRegressor(...)
RandomForestRegressor(...)
Ridge(...)
StandardScaler(...)
train_test_split(...)
TimeSeriesSplit(...)
```

Import detection:

```python
import pandas
import numpy
import sklearn
import xgboost
import lightgbm
import shap
```

---

# 12. Output Renderer

Notebook içindeki mevcut output'lar render edilmelidir.

İlk sürümde destek:

```text
stream
text/plain
text/html
image/png
image/jpeg
application/json
error
execute_result
display_data
```

### Text Output

```text
OUTPUT

Rows: 42183
Columns: 57
Missing: 0.72%
```

### DataFrame Output

HTML table ise sanitize edilerek render edilmelidir.

Raw HTML doğrudan DOM'a basılmamalıdır.

### Image Output

Base64 `image/png` ve `image/jpeg` render edilmelidir.

Örnek:
- Equity curve
- Drawdown chart
- Feature importance
- Correlation heatmap

### Error Output

```text
CELL 27 — FAILED

ValueError
Input contains NaN

[ Hücreye Git ]
```

Traceback expand/collapse yapılabilir.

---

# 13. Notebook Run Butonu

Mevcut ekrandaki iki farklı `Çalıştır` butonu sadeleştirilmelidir.

Üst buton:

```text
▶ Notebook'u Çalıştır
```

Cell içinde:

```text
▶
```

Dropdown:

```text
Tümünü Çalıştır
Seçili Hücreyi Çalıştır
Buradan İtibaren Çalıştır
Kernel'i Yeniden Başlat ve Tümünü Çalıştır
```

---

# 14. Execution Fazı

Notebook execution ilk viewer fazından sonra yapılmalıdır.

İlk sprintte notebook execute etmek zorunlu değildir.

Öncelik:

```text
View
↓
Parse
↓
Render
↓
Analyze
```

Execution sonraki sprintte eklenmelidir.

---

# 15. Çalıştırmalar Sekmesi

Her notebook run kayıt altına alınmalıdır.

Örnek:

```text
RUN #28
SUCCESS

Started        16:04:13
Finished       16:04:51
Duration       38 sec

Cells          48 / 48

Dataset        EURUSD_v4
Notebook       v3

Sharpe         1.78
Return         21.9%
Drawdown       -7.4%

[ Çıktıyı Gör ]
```

Notebook çalışırken progress:

```text
RUNNING

Cell 24 / 48
████████████░░░░░░░

Duration
00:00:21
```

Başarısız run:

```text
FAILED

Cell 27

ValueError:
Input contains NaN

[ Hücreye Git ]
```

---

# 16. Versiyonlar Sekmesi

Her notebook versiyonu saklanmalıdır.

Actions:

```text
Aç
Karşılaştır
Bu Versiyona Dön
Archive
```

Minimum diff:

```text
Added Cells
Removed Cells
Changed Cells
```

İleri sürüm:

```text
+ momentum_50
+ volatility_20
- rsi_7

XGBoost
max_depth: 4 → 6

Walk Forward
window: 500 → 750
```

---

# 17. Artifacts Sekmesi

Notebook çalıştırması tarafından oluşturulan dosyalar burada listelenmelidir.

```text
Models
├── xgboost.pkl
├── hmm.pkl
└── scaler.pkl

Reports
├── feature_ic.csv
├── backtest.json
└── metrics.json

Charts
├── equity_curve.png
├── drawdown.png
└── ic_decay.png

Data
└── selected_features.json
```

---

# 18. Notebook → Experiment

Buton:

```text
Deneye Dönüştür
```

Notebook statik analiz edilerek şu bileşenler bulunmalıdır:

```text
Dataset
Target
Features
Models
Model Parameters
Regime Model
Validation
Backtest
Metrics
```

Örnek preview:

```text
NOTEBOOK → EXPERIMENT

Dataset
EURUSD

Target
return_1d

Features
47 detected

Models
XGBoost
Random Forest

Regime
Gaussian HMM

Validation
Walk Forward

Backtest
Enabled

[ DENEY OLUŞTUR ]
```

Kullanıcı onaylamadan experiment oluşturulmamalıdır.

---

# 19. Notebook Analysis Uyarıları

Static analyzer şu uyarıları üretebilir:

```text
Purged K-Fold bulunamadı
Embargo bulunamadı
Random split kullanılıyor
Scaler tüm dataset üzerinde fit edilmiş olabilir
Final holdout bulunamadı
Transaction cost bulunamadı
Slippage bulunamadı
```

Bu kontroller rule-based olabilir.

---

# 20. Leakage Detection

İlk sürümde basit pattern detection yapılmalıdır.

Örneğin:

```python
scaler.fit_transform(df)
```

train split öncesinde kullanılmışsa:

```text
Potential Leakage
```

uyarısı verilebilir.

Aynı şekilde:

```python
train_test_split(..., shuffle=True)
```

finansal zaman serilerinde warning oluşturmalıdır.

---

# 21. Backend API Önerisi

Mevcut API convention'ı varsa ona uyulmalıdır.

```text
GET  /api/notebooks/{id}
GET  /api/notebooks/{id}/cells
GET  /api/notebooks/{id}/analysis

POST /api/notebooks/{id}/run
POST /api/notebooks/{id}/cells/{cell_id}/run

GET  /api/notebooks/{id}/runs
GET  /api/notebooks/{id}/versions
GET  /api/notebooks/{id}/artifacts

POST /api/notebooks/{id}/convert-to-experiment
```

---

# 22. Notebook Detail Response

```json
{
  "id": "NB-2B6C8E91",
  "name": "Auto Sanitized Notebook",
  "filename": "auto_clean.ipynb",
  "version": "v1",
  "status": "ACTIVE",
  "cell_count": 48,
  "code_cell_count": 31,
  "markdown_cell_count": 17
}
```

---

# 23. Cell Response

```json
{
  "cells": [
    {
      "id": "cell-001",
      "index": 0,
      "type": "markdown",
      "source": "# Data Preparation",
      "execution_count": null,
      "outputs": []
    },
    {
      "id": "cell-002",
      "index": 1,
      "type": "code",
      "source": "import pandas as pd",
      "execution_count": 1,
      "outputs": []
    }
  ]
}
```

---

# 24. Notebook Parser

Önerilen backend modülü:

```text
notebooks/
├── parser.py
├── analyzer.py
├── renderer.py
├── execution.py
├── versions.py
└── artifacts.py
```

Mevcut proje klasör yapısı farklıysa bu yapı zorla uygulanmamalıdır.

Önerilen interface:

```python
class NotebookParser:

    def parse(self, path: str) -> ParsedNotebook:
        ...

    def get_cells(self, notebook) -> list[NotebookCell]:
        ...

    def get_metadata(self, notebook) -> dict:
        ...
```

---

# 25. Güvenlik

Notebook güvenilmeyen kod içerebilir.

Bu nedenle:

```text
Notebook yüklemek
≠
Notebook kodunu çalıştırmak
```

olmalıdır.

Notebook görüntülenirken hiçbir code cell otomatik çalıştırılmamalıdır.

Notebook HTML output'u sanitize edilmeden render edilmemelidir.

Script tag'leri çalıştırılmamalıdır.

Execution eklendiğinde mümkünse:

```text
isolated process
working directory isolation
execution timeout
memory limit
output size limit
```

kullanılmalıdır.

---

# 26. Büyük Notebook Performansı

Notebook 500+ cell olabilir.

Frontend mümkünse:

```text
lazy rendering
virtualized cells
collapsed output
```

desteklemelidir.

İlk sürümde en az output collapse olmalıdır.

---

# 27. UI Layout Önerisi

```text
┌──────────────┬───────────────────────────────────┬───────────────┐
│   OUTLINE    │             NOTEBOOK              │   ANALYSIS    │
│              │                                   │               │
│ Data         │ CELL 1                            │ Cells 48      │
│ Features     │ CELL 2                            │ Models 4      │
│ Models       │ CELL 3                            │ Features 57   │
│ Validation   │ ...                               │ Warnings 2    │
│ Backtest     │                                   │               │
└──────────────┴───────────────────────────────────┴───────────────┘
```

Desktop'ta üç kolon.

Dar ekranda analysis panel collapse edilebilir.

---

# 28. Sprint 1 — Notebook Viewer

İlk sprint sadece notebook'u görünür hale getirmelidir.

```text
1. .ipynb JSON parser
2. Notebook sekmesi
3. Markdown cell renderer
4. Code cell renderer
5. Existing output renderer
6. Notebook outline
7. Basic notebook statistics
```

Execution yapılmamalıdır.

## Sprint 1 Task Listesi

```text
[ ] NB001 Notebook API mevcut yapısını analiz et
[ ] NB002 .ipynb parser implement et
[ ] NB003 Notebook metadata model oluştur
[ ] NB004 Notebook cell DTO/model oluştur
[ ] NB005 GET notebook cells endpoint'i ekle
[ ] NB006 Notebook tab'ını frontend'e ekle
[ ] NB007 Markdown renderer ekle
[ ] NB008 Code renderer ekle
[ ] NB009 text/plain output renderer ekle
[ ] NB010 image/png output renderer ekle
[ ] NB011 HTML output sanitizer ekle
[ ] NB012 Notebook outline oluştur
[ ] NB013 Cell click → scroll navigation ekle
[ ] NB014 Basic notebook statistics ekle
[ ] NB015 Loading state ekle
[ ] NB016 Error state ekle
[ ] NB017 Unit testleri yaz
[ ] NB018 Frontend testlerini çalıştır
[ ] NB019 Backend testlerini çalıştır
```

## Definition of Done

```text
✓ auto_clean.ipynb ekranda açılıyor
✓ Markdown cell'ler görünüyor
✓ Code cell'ler görünüyor
✓ Existing output'lar görünüyor
✓ Grafik çıktıları görünüyor
✓ Outline çalışıyor
✓ Notebook otomatik execute edilmiyor
✓ HTML output sanitize ediliyor
✓ Backend testleri geçiyor
✓ Frontend build başarılı
```

---

# 29. Sprint 2 — Static Analysis

```text
[ ] Python AST analyzer
[ ] Import detection
[ ] Model detection
[ ] Dataset detection
[ ] Feature detection
[ ] Validation detection
[ ] Backtest detection
[ ] Leakage warning rules
[ ] Analysis side panel
```

---

# 30. Sprint 3 — Notebook Execution

```text
[ ] Run All
[ ] Run Cell
[ ] Run From Here
[ ] Execution progress
[ ] Run history
[ ] Error cell link
[ ] Timeout
[ ] Cancel run
```

---

# 31. Sprint 4 — Editing & Versions

```text
[ ] Edit cell
[ ] Add cell
[ ] Delete cell
[ ] Move cell
[ ] Save new version
[ ] Notebook diff
[ ] Restore version
```

---

# 32. Sprint 5 — Notebook to Experiment

```text
[ ] Parse dataset
[ ] Parse target
[ ] Parse features
[ ] Parse models
[ ] Parse parameters
[ ] Parse validation
[ ] Parse backtest
[ ] Experiment preview
[ ] Create experiment
[ ] Experiment registry integration
```

---

# 33. Düşük Güçlü AI İçin Çalışma Talimatı

Local AI agent'a şu talimat verilmelidir:

```text
Notebook Lab üzerinde çalış.

Önce mevcut notebook upload, detail, version ve run kodlarını incele.

Mevcut çalışan yapıyı değiştirme.

İlk hedef notebook execution değildir.

İlk hedef yüklenen .ipynb dosyasının içeriğini ekranda göstermek.

TASK sırasını takip et.

Aynı anda yalnızca bir NBxxx task yap.

Her task için:

1. İlgili dosyaları bul.
2. Minimum değişiklik planını yaz.
3. Implement et.
4. Test ekle.
5. Testleri çalıştır.
6. Hata varsa düzelt.
7. CHANGELOG_AI.md güncelle.
8. Task'ı tamamlandı işaretle.
9. Dur.

Notebook code cell'lerini otomatik çalıştırma.

Notebook HTML output'unu sanitize et.

Existing output varsa görüntüle.

Yeni notebook execution engine yazmaya ilk sprintte çalışma.
```

---

# 34. İlk Uygulanacak Task

İlk görev:

```text
NB001
Mevcut Notebook Lab backend ve frontend yapısını analiz et.
```

Beklenen çıktı:

```text
Notebook list component:
<path>

Notebook detail component:
<path>

Notebook backend controller/router:
<path>

Notebook storage:
<path>

Run implementation:
<path>

Version implementation:
<path>

Artifact implementation:
<path>
```

Bu analiz bitmeden NB002'ye geçilmemelidir.

---

# 35. Nihai Hedef

```text
Upload Notebook
      ↓
Open Notebook
      ↓
Read Code + Markdown + Outputs
      ↓
Analyze
      ↓
Detect Features / Models / Validation
      ↓
Fix Warnings
      ↓
Run
      ↓
Inspect Results
      ↓
Version
      ↓
Convert to Experiment
      ↓
Optimization / Backtest / Stress Test
```

Notebook Lab sonunda basit bir `.ipynb` dosya yöneticisi değil, araştırma notebook'larını platformun experiment sistemine bağlayan ana çalışma alanlarından biri olmalıdır.
