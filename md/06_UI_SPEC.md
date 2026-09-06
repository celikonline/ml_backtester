# UI SPEC — QUANT RESEARCH DASHBOARD

## Tasarım Hedefi

Koyu temalı, yoğun fakat okunabilir, AlgoSense benzeri bir quant research interface.

Ana amaç:
- Veri akışını görünür yapmak
- Experiment sonuçlarını karşılaştırmak
- Feature kalitesini göstermek
- Validation leakage kontrollerini görünür yapmak
- GA optimizasyonunu izlemek
- Stress test sonuçlarını tek ekranda sunmak

---

# 1. Ana Navigasyon

```text
Overview
Data
Features
Models
Validation
Optimization
Backtest
Stress Tests
Experiments
```

---

# 2. Overview

Üst KPI kartları:

```text
Best Sharpe
Best Return
Lowest Max Drawdown
Selected Features
Active Experiment
Dataset Hash
```

Ana grafik:
- Equity Curve
- Drawdown overlay
- Benchmark opsiyonel

Alt alan:
- Son experiment'lar
- Pipeline durumu
- Warning / leakage uyarıları

---

# 3. Data Ekranı

Göster:

```text
Dataset Name
Row Count
Date Range
Frequency
Snapshot Hash
Point-in-Time Status
Timezone Status
Missing Ratio
```

Data family kartları:

```text
OHLC
Macro
FX
Rates
Cross Asset
```

---

# 4. Features Ekranı

Ana tablo:

| Feature | IC | IC IR | Sign Consistency | Stability | Cluster | Selected |
|---|---:|---:|---:|---:|---:|---|

Filtreler:

```text
Minimum IC
Minimum Stability
Cluster
Selected Only
Search
```

Grafikler:

```text
IC Bar Chart
IC Decay Curve
Correlation Heatmap
Cluster View
```

---

# 5. Models Ekranı

Model kartları:

```text
Ridge
Random Forest
Histogram Gradient Boosting
XGBoost
LightGBM
Stacking
```

Kart içeriği:

```text
Status
Validation Sharpe
Return
Max Drawdown
Training Time
Feature Count
```

---

# 6. Validation Ekranı

Tabs:

```text
Walk Forward
Purged K-Fold
Rolling
Anchored
```

Fold timeline:

```text
TRAIN    PURGE    VALIDATION    EMBARGO
██████   ░░       ████          ░
```

Fold tablosu:

```text
Fold
Train Range
Validation Range
Purged Samples
Embargo Samples
Sharpe
Return
Drawdown
```

---

# 7. Optimization Ekranı

GA KPI:

```text
Generation
Best Fitness
Best Sharpe
Best Drawdown
Feature Count
Population Size
```

Fitness Breakdown:

```text
Sharpe Contribution
Feature Quality Contribution
Drawdown Penalty
Turnover Penalty
```

Grafikler:

```text
Best Fitness by Generation
Average Fitness by Generation
Feature Selection Frequency
```

---

# 8. Backtest Ekranı

Üst KPI:

```text
Sharpe
Return
Annualized Return
Max Drawdown
Sortino
Calmar
Trade Count
Win Rate
Profit Factor
```

Grafikler:

```text
Equity Curve
Drawdown
Monthly Returns
Trade Distribution
```

---

# 9. Stress Tests Ekranı

Kartlar:

```text
Base Sharpe
Worst Sharpe
Base Return
Worst Return
Base Drawdown
Worst Drawdown
```

Ana görseller:

```text
Commission × Slippage Heatmap
Latency Bars → Sharpe Curve
Scenario Comparison Bar Chart
```

---

# 10. Experiments Ekranı

Tablo:

```text
Experiment ID
Created At
Dataset
Model
Validation
Feature Count
Sharpe
Return
Drawdown
Status
```

Actions:

```text
Open
Compare
Clone Config
Export
```

---

# 11. Renk Mantığı

Önerilen semantik kullanım:

```text
Green  → Positive / selected / passed
Red    → Risk / failed / negative
Cyan   → Neutral metrics / system state
Amber  → Warning / partial / attention
Gray   → Disabled / unavailable
```

Renklerin tek başına anlam taşımamasına dikkat et; ikon veya label ile destekle.

---

# 12. Responsive Davranış

Desktop öncelikli.

Minimum:

```text
1920x1080
1440x900
1366x768
```

Dashboard yoğun olduğu için mobil ilk fazda öncelik değildir.

---

# 13. UI Performans Kuralları

- Büyük raw dataset'i frontend'e gönderme.
- Grafik verisini downsample et.
- Heatmap matrislerini server-side hazırla.
- Pagination kullan.
- 1000+ satırlık feature tablolarında virtualized list kullan.
- Polling yerine mevcut websocket altyapısı varsa onu tercih et.
- Uzun job'larda progress state göster.

---

# 14. Durum Etiketleri

```text
READY
RUNNING
FAILED
PARTIAL
NOT_AVAILABLE
```

---

# 15. İlk UI Definition of Done

```text
[ ] Main navigation
[ ] Overview KPIs
[ ] Feature Quality table
[ ] IC chart
[ ] Validation fold timeline
[ ] GA generation chart
[ ] Backtest KPI panel
[ ] Stress test heatmap
[ ] Experiment list
```
