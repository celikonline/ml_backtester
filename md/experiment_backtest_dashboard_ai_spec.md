# Experiment & Backtest Results Dashboard
## AI Implementation Specification

> Amaç: Mevcut finansal ML / quant araştırma platformuna, QuantConnect benzeri fakat doğrudan kopya olmayan, ML/AI odaklı bir **Experiment & Backtest Results Dashboard** eklemek.
>
> Bu doküman, bir yazılım geliştirme AI ajanına doğrudan verilebilecek şekilde hazırlanmıştır. Ek açıklama istemeden, mevcut projeye uyarlanabilir bir uygulama planı ve UI/UX spesifikasyonu içerir.

---

# 1. Hedef

Platformda oluşturulan her deneyin ve backtest koşusunun sonucunu tek bir ekranda anlaşılır şekilde göstermek.

Dashboard aşağıdaki sorulara mümkün olduğunca hızlı cevap vermelidir:

1. Strateji para kazandırıyor mu?
2. Risk seviyesi nedir?
3. Sharpe / PSR / Drawdown değerleri kabul edilebilir mi?
4. Validation ile Test arasında performans bozulması var mı?
5. Hangi model daha iyi?
6. Hangi feature'lar sonucu etkiliyor?
7. Genetik algoritma optimizasyonu gerçekten iyileştirme sağladı mı?
8. Hangi asset'lerde pozisyon alındı?
9. Long / Short exposure ne durumda?
10. Model sinyal verdiğinde confidence neydi?
11. Backtest içindeki trade'ler neden açıldı?
12. Overfitting ihtimali var mı?

---

# 2. Dashboard'ın Platformdaki Yeri

Önerilen ana navigasyon:

```text
Projects
 └── Project
      ├── Data
      ├── Cleaning
      ├── Feature Engineering
      ├── Models
      ├── Experiments
      │    ├── Runs
      │    ├── Optimization
      │    └── Compare
      ├── Backtests
      │    ├── Results   <-- BU EKRAN
      │    └── Trades
      └── Reports
```

Alternatif olarak:

```text
Experiment Detail
 ├── Overview
 ├── Metrics
 ├── Equity
 ├── Risk
 ├── Features
 ├── Optimization
 ├── Trades
 └── Logs
```

Dashboard, bir `experiment_run_id` veya `backtest_run_id` ile açılmalıdır.

Örnek route:

```text
/projects/{projectId}/experiments/{experimentId}/results
```

veya:

```text
/backtests/{backtestRunId}
```

---

# 3. Temel Tasarım Prensibi

QuantConnect'teki dashboard mantığı referans alınabilir fakat birebir kopyalanmamalıdır.

UI karakteri:

- Minimal
- Profesyonel
- Finans / quant odaklı
- Beyaz veya açık gri arka plan
- Kart bazlı yapı
- Fazla renk kullanılmamalı
- Yeşil: pozitif
- Kırmızı: negatif
- Mavi / nötr tonlar: bilgi ve grafik
- Kritik risk: turuncu / kırmızı
- Sayısal metriklerde güçlü tipografi
- Grafik alanları ferah olmalı
- Çok fazla border kullanılmamalı
- Tooltip ve hover etkileşimi güçlü olmalı

---

# 4. Sayfa Genel Layout'u

Desktop için önerilen yapı:

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Experiment Header                                                    │
├──────────────────────────────────────────────────────────────────────┤
│ Portfolio │ Return │ Sharpe │ Max DD │ PSR │ Win Rate │ Trades      │
├────────────────────────────────────────────┬─────────────────────────┤
│                                            │                         │
│               EQUITY CURVE                 │   PORTFOLIO ALLOCATION  │
│                                            │                         │
├───────────────────────┬────────────────────┬─────────────────────────┤
│ DRAWDOWN              │ EXPOSURE           │ SIGNAL CONFIDENCE       │
├───────────────────────┴────────────────────┴─────────────────────────┤
│ MODEL PERFORMANCE                                                    │
├──────────────────────────────────────┬───────────────────────────────┤
│ FEATURE IMPORTANCE                   │ GENETIC OPTIMIZATION          │
├──────────────────────────────────────┴───────────────────────────────┤
│ TRADES                                                               │
└──────────────────────────────────────────────────────────────────────┘
```

---

# 5. Experiment Header

Sayfanın üst kısmında koşu bilgileri gösterilmelidir.

Örnek:

```text
Experiment #EXP-028

Dataset: FX-Macro-v7
Target: EURUSD Next-Day Return
Model: TFT + XGBoost + LightGBM
Optimizer: Genetic Algorithm
Status: Completed
Started: 2026-09-05 14:31
Duration: 18m 42s
```

Sağ tarafta aksiyonlar:

```text
[ Compare ]
[ Export Report ]
[ Re-run ]
[ Clone Experiment ]
```

Opsiyonel:

```text
[ Promote Model ]
```

---

# 6. KPI Summary Cards

Üst bölümde ilk bakışta okunabilecek 6-8 KPI gösterilmeli.

Önerilen metrikler:

```text
Portfolio Value
Total Return
Annualized Return
Sharpe Ratio
PSR
Max Drawdown
Win Rate
Total Trades
```

Örnek:

```text
Portfolio Value       $271,024
Total Return          +67.3%
Annualized Return     +24.8%
Sharpe Ratio           2.08
PSR                    92.4%
Max Drawdown           -7.6%
Win Rate               63.2%
Trades                  184
```

## 6.1 KPI Durum Kuralları

Örnek:

```text
Return > 0       → positive
Return < 0       → negative

Sharpe >= 2      → strong
Sharpe 1-2       → acceptable
Sharpe < 1       → weak

Max DD > -10%    → acceptable
Max DD -10%-20%  → warning
Max DD < -20%    → critical
```

Bu eşikler hard-code edilmemeli.

Config üzerinden değiştirilebilir olmalı.

---

# 7. Equity Curve

Dashboard'ın en büyük grafiği olmalıdır.

Grafikte aynı anda gösterilebilecek seriler:

```text
Strategy
Benchmark
Buy & Hold
```

Kullanıcı checkbox ile serileri açıp kapatabilmelidir.

Örnek:

```text
[x] Strategy
[x] Benchmark
[ ] Buy & Hold
```

## 7.1 Train / Validation / Test Ayrımı

Grafikte dataset dönemleri görsel olarak ayrılmalıdır.

```text
|------ TRAIN ------|--- VALIDATION ---|------ TEST ------|
```

Arka plan çok hafif ton farkıyla gösterilebilir.

Tooltip:

```text
Date: 2026-03-14
Strategy Equity: $184,241
Benchmark Equity: $159,882
Period: Validation
Daily Return: +0.84%
```

## 7.2 Equity Chart Kontrolleri

```text
1D
1W
1M
3M
6M
YTD
1Y
ALL
```

Ek seçenek:

```text
[ Absolute ] [ Normalized ]
```

Normalized mod:

```text
Initial value = 100
```

Bu mod benchmark karşılaştırması için faydalıdır.

---

# 8. Drawdown Panel

Gösterilecek alanlar:

```text
Current Drawdown
Max Drawdown
Longest Drawdown
Recovery Time
Average Drawdown
```

Örnek:

```text
Current DD       -1.8%
Max DD           -7.6%
Longest DD       61 days
Recovery         23 days
Average DD       -2.4%
```

Grafik:

```text
0%
────────────────────────────
   \_
     \____
          \____ -7.6%
```

Tooltip:

```text
Date
Drawdown %
Peak Equity
Current Equity
Underwater Days
```

---

# 9. Portfolio Allocation Treemap

QuantConnect'teki `Asset Volume` yerine daha kullanışlı bir:

```text
Portfolio Allocation
```

bölümü eklenmelidir.

Örnek:

```text
SPY       29.0%
NVDA      18.9%
AAPL      14.2%
QQQ       12.7%
AMD        7.9%
TSLA       6.1%
GLD        4.3%
Cash       6.9%
```

Treemap içinde asset ağırlıkları gösterilmeli.

## 9.1 Kullanıcı Etkileşimi

Asset'e tıklanınca:

```text
Asset Detail Drawer
```

açılmalı.

İçerik:

```text
Symbol
Current Weight
Average Weight
Max Weight
PnL
Trades
Win Rate
Exposure
Contribution to Return
Contribution to Risk
```

---

# 10. Exposure Panel

Gösterilecek metrikler:

```text
Gross Exposure
Net Exposure
Long Exposure
Short Exposure
Cash
Leverage
```

Örnek:

```text
Long        72%
Short       28%
Gross      118%
Net         44%
Cash        18%
Leverage   1.18x
```

Asset bazında exposure breakdown opsiyonel olarak gösterilebilir.

---

# 11. Signal Confidence Panel

QuantConnect'teki Capacity alanı yerine ilk sürümde:

```text
Signal Confidence
```

kullanılmalıdır.

Örnek:

| Model | Signal | Confidence |
|---|---|---:|
| TFT | LONG | 82% |
| XGBoost | LONG | 71% |
| LightGBM | NEUTRAL | 54% |
| Ensemble | LONG | 79% |

## 11.1 Signal Type

Desteklenecek sinyaller:

```text
STRONG_LONG
LONG
NEUTRAL
SHORT
STRONG_SHORT
```

Alternatif daha basit yapı:

```text
LONG
NEUTRAL
SHORT
```

## 11.2 Confidence

Confidence değerinin kaynağı backend tarafından hesaplanmalıdır.

Örneğin:

- Model probability
- Calibrated probability
- Ensemble agreement
- Weighted voting confidence

UI kendi başına confidence üretmemelidir.

---

# 12. Model Performance

Bu alan sistemin en önemli farklarından biridir.

Birden fazla model karşılaştırılabilmelidir.

Örnek:

| Model | Sharpe | Return | Max DD | PSR | Win Rate |
|---|---:|---:|---:|---:|---:|
| TFT | 1.82 | 34% | -8% | 84% | 59% |
| XGBoost | 1.71 | 31% | -6% | 81% | 61% |
| LightGBM | 1.58 | 25% | -6% | 77% | 58% |
| Ensemble | 2.08 | 42% | -7% | 92% | 63% |

Default sorting:

```text
Sharpe DESC
```

Ama kullanıcı kolonlara göre sıralayabilmelidir.

---

# 13. Train / Validation / Test Model Comparison

Overfitting kontrolü için metrikler split bazında da gösterilmelidir.

Örnek:

| Metric | Train | Validation | Test |
|---|---:|---:|---:|
| Sharpe | 2.84 | 2.31 | 2.08 |
| Return | 62% | 47% | 42% |
| Max DD | -5.2% | -6.8% | -7.6% |
| Win Rate | 69% | 65% | 63% |

Ayrıca:

```text
Validation → Test Sharpe Degradation: -9.9%
```

gösterilmelidir.

## 13.1 Overfitting Warning

Örnek kural:

```text
Train Sharpe >> Validation Sharpe
Validation Sharpe >> Test Sharpe
```

ise:

```text
⚠ Potential Overfitting
```

uyarısı göster.

Bu uyarı sadece bilgi amaçlı olmalı.

---

# 14. Feature Importance

Feature importance bölümünde minimum:

```text
Feature
Importance
Rank
```

gösterilmelidir.

Örnek:

```text
DXY                  18%
VIX                  15%
Yield Spread         13%
RSI                    9%
CFTC Positioning       8%
```

Grafik tipi:

```text
Horizontal Bar Chart
```

## 14.1 Desteklenecek Importance Türleri

Backend'e göre:

```text
Model Native Importance
Permutation Importance
SHAP
Gain
Split Importance
```

UI'da selector olabilir:

```text
Importance Method:
[ SHAP ▼ ]
```

---

# 15. Feature Stability

Projenin finansal ML karakteri nedeniyle Feature Importance tek başına yeterli değildir.

Ayrıca aşağıdaki değerler gösterilebilir:

```text
IC
IC Decay
Sign Consistency
Rolling Stability
Missing Rate
Drift Score
```

Örnek:

| Feature | Importance | IC | Stability | Drift |
|---|---:|---:|---:|---:|
| DXY | 0.18 | 0.12 | 0.91 | Low |
| VIX | 0.15 | 0.10 | 0.88 | Low |
| RSI | 0.09 | 0.04 | 0.63 | Medium |

---

# 16. Genetic Algorithm Optimization

Bu alan sistem için kritik olmalıdır.

Grafik:

```text
Generation → Best Fitness
```

Örnek:

```text
Generation 1     Sharpe 0.91
Generation 10    Sharpe 1.31
Generation 20    Sharpe 1.68
Generation 30    Sharpe 1.91
Generation 40    Sharpe 2.08
```

Grafikte:

```text
Best Fitness
Average Fitness
Median Fitness
```

ayrı seriler olarak gösterilebilir.

---

# 17. Genetic Optimization Summary

Gösterilecek metrikler:

```text
Generations
Population Size
Best Fitness
Best Validation Sharpe
Test Sharpe
Selected Features
Mutation Rate
Crossover Rate
Early Stopping
Duration
```

Örnek:

```text
Generations            40
Population             120
Best Fitness           2.31
Validation Sharpe      2.31
Test Sharpe            2.08
Selected Features      43 / 187
Mutation Rate          0.12
Crossover Rate         0.80
Duration               7m 21s
```

---

# 18. Selected Feature Set

Genetik algoritmanın seçtiği feature'lar ayrı görüntülenebilmelidir.

Örnek:

```text
Selected Features: 43 / 187
```

Buton:

```text
[ View Selected Features ]
```

Drawer içinde:

```text
DXY
VIX
US10Y
US02Y
YieldSpread
RSI_14
ATR_14
MACD
CFTC_Net_Position
...
```

Opsiyonel:

```text
[ Export JSON ]
```

---

# 19. Trades Table

Orders yerine daha gelişmiş:

```text
Trades
```

tablosu kullanılmalıdır.

Kolonlar:

```text
Time
Symbol
Side
Entry
Exit
Quantity
PnL
PnL %
Model
Signal
Confidence
Duration
Strategy
```

Örnek:

| Symbol | Side | Entry | Exit | PnL | Model | Confidence |
|---|---|---:|---:|---:|---|---:|
| NVDA | LONG | 182.30 | 196.80 | +7.95% | TFT | 86% |
| SPY | SHORT | 611.20 | 604.10 | +1.16% | XGBoost | 73% |
| GLD | LONG | 319.50 | 325.80 | +1.97% | Ensemble | 81% |

---

# 20. Trade Detail Drawer

Trade satırına tıklanınca sağ taraftan drawer açılmalı.

İçerik:

```text
Trade ID
Symbol
Entry Time
Exit Time
Direction
Entry Price
Exit Price
Quantity
PnL
PnL %
Holding Period
Transaction Cost
Slippage
```

AI / model bilgileri:

```text
Signal
Confidence
Model
Model Version
Feature Snapshot
Prediction
Expected Return
Stop Loss
Take Profit
```

Ek olarak:

```text
Why was this trade opened?
```

bölümü gelecekte AI açıklaması için kullanılabilir.

Örnek:

```text
Primary factors:
- DXY momentum weakened
- Yield spread improved
- RSI exited oversold region
- Ensemble agreement: 4/5 models
```

---

# 21. Benchmark Comparison

Benchmark seçimi desteklenmelidir.

Örnek benchmark'lar:

```text
SPY
QQQ
BIST100
NASDAQ
S&P 500
BTC
Gold
USDTRY
Custom
```

Dataset / asset class'a göre uygun benchmark seçilmelidir.

Kullanıcı dropdown'dan değiştirebilir.

---

# 22. Risk Metrics

Gelişmiş panel veya tab içerisinde:

```text
Sharpe Ratio
Sortino Ratio
Calmar Ratio
Omega Ratio
PSR
VaR
CVaR
Volatility
Beta
Alpha
Max Drawdown
Ulcer Index
Profit Factor
Expectancy
```

MVP'de minimum:

```text
Sharpe
Sortino
Max DD
Volatility
PSR
Profit Factor
```

---

# 23. Return Metrics

```text
Total Return
Annualized Return
Monthly Return
Best Day
Worst Day
Best Month
Worst Month
Average Trade Return
Median Trade Return
```

---

# 24. Rolling Metrics

Finansal ML açısından çok faydalı olacak.

Grafik seçenekleri:

```text
Rolling Sharpe
Rolling Volatility
Rolling Drawdown
Rolling Beta
Rolling Alpha
```

Default:

```text
Rolling Sharpe 30D
```

Dropdown:

```text
Window:
30D
60D
90D
180D
```

---

# 25. Monthly Returns Heatmap

Opsiyonel fakat önerilir.

Örnek:

```text
       Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec
2024    +2  +1  -1  +4  +3  +2  ...
2025    +1  +5  +2  -2  +4  ...
2026    +3  +2  +4
```

Bu grafik strategy consistency görmek için faydalıdır.

---

# 26. Model Ensemble Breakdown

Stacked / ensemble model kullanılıyorsa:

```text
Ensemble Composition
```

gösterilmeli.

Örnek:

```text
TFT          35%
XGBoost      25%
LightGBM     20%
LSTM         10%
Linear        10%
```

Ek olarak:

```text
Model Agreement
```

değeri:

```text
4 / 5 models agree LONG
```

---

# 27. Backtest Metadata

Kullanıcı aşağıdaki bilgileri her zaman görebilmeli:

```text
Run ID
Project ID
Dataset Version
Feature Set Version
Model Version
Strategy Version
Code Commit
Start Date
End Date
Initial Capital
Transaction Cost Model
Slippage Model
Benchmark
Timezone
```

Örnek:

```text
Run: BT-2026-0082
Dataset: fx_macro_v7
Feature Set: fs_043
Model: ensemble_v12
Commit: 8af3e2c
Initial Capital: $100,000
Slippage: Fixed 2 bps
Fees: Interactive Brokers
```

---

# 28. Reproducibility

Her experiment tekrar üretilebilir olmalıdır.

Bu nedenle backend aşağıdaki bilgileri saklamalı:

```text
random_seed
dataset_version
feature_set_version
model_config
optimizer_config
strategy_config
transaction_cost_config
slippage_config
code_commit
environment_version
```

---

# 29. API Önerisi

## 29.1 Experiment Overview

```http
GET /api/experiments/{experimentId}/overview
```

Örnek response:

```json
{
  "experimentId": "EXP-028",
  "status": "completed",
  "dataset": {
    "id": "fx_macro_v7",
    "name": "FX Macro v7"
  },
  "target": "EURUSD_NEXT_DAY_RETURN",
  "optimizer": "genetic_algorithm",
  "startedAt": "2026-09-05T14:31:00Z",
  "completedAt": "2026-09-05T14:49:42Z",
  "metrics": {
    "portfolioValue": 271024,
    "totalReturn": 0.673,
    "annualizedReturn": 0.248,
    "sharpe": 2.08,
    "psr": 0.924,
    "maxDrawdown": -0.076,
    "winRate": 0.632,
    "totalTrades": 184
  }
}
```

---

# 30. Equity API

```http
GET /api/experiments/{experimentId}/equity
```

Response:

```json
{
  "series": [
    {
      "date": "2026-01-01",
      "strategy": 100000,
      "benchmark": 100000,
      "period": "train"
    },
    {
      "date": "2026-01-02",
      "strategy": 100840,
      "benchmark": 100210,
      "period": "train"
    }
  ]
}
```

---

# 31. Drawdown API

```http
GET /api/experiments/{experimentId}/drawdown
```

Response:

```json
{
  "summary": {
    "current": -0.018,
    "max": -0.076,
    "average": -0.024,
    "longestDays": 61,
    "recoveryDays": 23
  },
  "series": [
    {
      "date": "2026-01-01",
      "drawdown": 0
    }
  ]
}
```

---

# 32. Allocation API

```http
GET /api/experiments/{experimentId}/allocation
```

```json
{
  "assets": [
    {
      "symbol": "SPY",
      "weight": 0.29,
      "pnl": 12120,
      "contribution": 0.18
    }
  ]
}
```

---

# 33. Exposure API

```http
GET /api/experiments/{experimentId}/exposure
```

```json
{
  "long": 0.72,
  "short": 0.28,
  "gross": 1.18,
  "net": 0.44,
  "cash": 0.18,
  "leverage": 1.18
}
```

---

# 34. Models API

```http
GET /api/experiments/{experimentId}/models
```

```json
{
  "models": [
    {
      "name": "TFT",
      "version": "v3",
      "metrics": {
        "sharpe": 1.82,
        "return": 0.34,
        "maxDrawdown": -0.08,
        "psr": 0.84,
        "winRate": 0.59
      }
    }
  ]
}
```

---

# 35. Feature Importance API

```http
GET /api/experiments/{experimentId}/features/importance
```

```json
{
  "method": "shap",
  "features": [
    {
      "name": "DXY",
      "importance": 0.18,
      "rank": 1
    }
  ]
}
```

---

# 36. Genetic Optimization API

```http
GET /api/experiments/{experimentId}/optimization/genetic
```

```json
{
  "config": {
    "populationSize": 120,
    "generations": 40,
    "mutationRate": 0.12,
    "crossoverRate": 0.8
  },
  "best": {
    "fitness": 2.31,
    "validationSharpe": 2.31,
    "testSharpe": 2.08,
    "selectedFeatureCount": 43
  },
  "history": [
    {
      "generation": 1,
      "bestFitness": 0.91,
      "averageFitness": 0.63
    }
  ]
}
```

---

# 37. Trades API

```http
GET /api/experiments/{experimentId}/trades
```

Query:

```text
?page=1
&pageSize=50
&symbol=NVDA
&side=LONG
&model=TFT
```

Response:

```json
{
  "items": [
    {
      "tradeId": "TR-001",
      "symbol": "NVDA",
      "side": "LONG",
      "entryTime": "2026-04-01T10:30:00Z",
      "exitTime": "2026-04-04T15:00:00Z",
      "entryPrice": 182.30,
      "exitPrice": 196.80,
      "quantity": 100,
      "pnl": 1450,
      "pnlPct": 0.0795,
      "model": "TFT",
      "signal": "LONG",
      "confidence": 0.86
    }
  ],
  "page": 1,
  "pageSize": 50,
  "total": 184
}
```

---

# 38. Frontend Component Yapısı

Önerilen React component tree:

```text
ExperimentResultsPage

 ├── ExperimentHeader
 ├── MetricsSummary
 │    └── MetricCard
 │
 ├── EquitySection
 │    ├── EquityChart
 │    └── EquityControls
 │
 ├── AllocationTreemap
 │
 ├── RiskRow
 │    ├── DrawdownChart
 │    ├── ExposureChart
 │    └── SignalConfidenceCard
 │
 ├── ModelPerformanceTable
 │
 ├── FeatureSection
 │    ├── FeatureImportanceChart
 │    └── FeatureStabilityTable
 │
 ├── GeneticOptimizationSection
 │    ├── GeneticFitnessChart
 │    └── GeneticSummary
 │
 ├── TradesTable
 │
 └── TradeDetailDrawer
```

---

# 39. Frontend Dosya Önerisi

```text
src/
 └── features/
      └── experiments/
           ├── pages/
           │    └── ExperimentResultsPage.tsx
           │
           ├── components/
           │    ├── ExperimentHeader.tsx
           │    ├── MetricCard.tsx
           │    ├── MetricsSummary.tsx
           │    ├── EquityChart.tsx
           │    ├── AllocationTreemap.tsx
           │    ├── DrawdownChart.tsx
           │    ├── ExposureChart.tsx
           │    ├── SignalConfidence.tsx
           │    ├── ModelPerformanceTable.tsx
           │    ├── FeatureImportanceChart.tsx
           │    ├── GeneticFitnessChart.tsx
           │    ├── GeneticSummary.tsx
           │    ├── TradesTable.tsx
           │    └── TradeDetailDrawer.tsx
           │
           ├── api/
           │    └── experimentResultsApi.ts
           │
           ├── hooks/
           │    └── useExperimentResults.ts
           │
           └── types/
                └── experimentResults.ts
```

---

# 40. Önerilen Frontend Teknolojileri

Mevcut React stack korunmalı.

Öneriler:

```text
React
TypeScript
TanStack Query
TanStack Table
ECharts veya Recharts
React Router
Zustand / mevcut state management
```

Chart tercihi:

```text
ECharts
```

Özellikle:

- Treemap
- Heatmap
- Multiple series
- Tooltip
- Zoom
- Large dataset

gereksinimleri nedeniyle avantajlıdır.

Mevcut projede başka chart library kullanılıyorsa değiştirmeyin.

---

# 41. Loading State

Her kart bağımsız yüklenebilmelidir.

Örnek:

```text
Metric Cards → skeleton
Equity Chart → chart skeleton
Trades → table skeleton
```

Tüm sayfa tek API response'unu beklememelidir.

---

# 42. Error Handling

Bir widget API hatası alırsa tüm dashboard çökmemeli.

Örnek:

```text
Feature Importance could not be loaded.

[ Retry ]
```

Equity curve çalışmaya devam etmelidir.

---

# 43. Empty State

Örnek:

```text
No trades were generated for this experiment.
```

veya:

```text
Feature importance is not available for this model.
```

---

# 44. Responsive Tasarım

Desktop:

```text
Equity: 2/3
Treemap: 1/3
```

Tablet:

```text
Equity: full width
Treemap: full width
```

Mobile:

```text
Tek kolon
```

Metrics yatay scroll veya 2 kolon olabilir.

---

# 45. Performance

Equity / trades dataset'leri büyük olabilir.

Bu nedenle:

```text
virtualized tables
downsampled chart series
server-side pagination
lazy loading
memoization
```

kullanılmalıdır.

Özellikle milyonlarca data point doğrudan browser'a gönderilmemelidir.

---

# 46. Time Series Downsampling

Backend veya frontend:

```text
LTTB
Largest Triangle Three Buckets
```

benzeri downsampling kullanabilir.

Örneğin:

```text
1,000,000 points
↓
5,000 display points
```

Raw dataset gerektiğinde zoom ile fetch edilebilir.

---

# 47. Currency / Number Formatting

Tek standard kullanılmalı.

Örnek:

```text
$271,024
+67.3%
-7.6%
2.08
1.18x
```

Percentage backend'de:

```text
0.673
```

olarak tutulabilir.

UI:

```text
67.3%
```

olarak göstermelidir.

---

# 48. Dark Mode

Platform dark mode destekliyorsa dashboard tamamen uyumlu olmalı.

Chart library hard-coded background kullanmamalı.

CSS variables üzerinden:

```text
--background
--surface
--border
--text-primary
--text-secondary
--positive
--negative
--warning
```

kullanılmalı.

---

# 49. Accessibility

Minimum:

```text
keyboard navigation
aria-label
sufficient contrast
tooltips keyboard accessible
color-only indicators avoided
```

Pozitif / negatif sadece renk ile gösterilmemeli.

Örneğin:

```text
▲ +4.3%
▼ -2.1%
```

---

# 50. MVP

İlk sürümde MUTLAKA uygulanacaklar:

```text
1. Experiment Header
2. KPI Summary
3. Equity Curve
4. Benchmark
5. Train / Validation / Test regions
6. Drawdown
7. Portfolio Allocation
8. Exposure
9. Model Performance
10. Feature Importance
11. Genetic Optimization Progress
12. Trades Table
13. Trade Detail Drawer
```

---

# 51. Phase 2

Sonraki geliştirmeler:

```text
Rolling Sharpe
Rolling volatility
Monthly return heatmap
Feature stability
SHAP visualization
Asset contribution
Risk contribution
Model ensemble breakdown
Transaction cost analysis
Slippage analysis
Capacity estimate
Stress testing
Scenario analysis
Monte Carlo simulation
```

---

# 52. Phase 3

İleri seviye:

```text
AI Experiment Analyst
```

Kullanıcı:

```text
Why did the test Sharpe fall?
```

diye sorabilmeli.

AI aşağıdaki verileri analiz etmeli:

```text
Train metrics
Validation metrics
Test metrics
Feature drift
Trade distribution
Drawdown
Model confidence
Asset exposure
```

ve açıklama üretmeli.

Örnek:

```text
The largest degradation occurred during the test period.

Main observations:

1. VIX feature IC declined from 0.11 to 0.03.
2. The strategy became more concentrated in NVDA.
3. Average holding period increased by 41%.
4. Long exposure remained above 85% during the largest drawdown.
```

---

# 53. AI Insights Card

Dashboard'ın üst tarafına opsiyonel bir kart:

```text
AI ANALYSIS
```

eklenebilir.

Örnek:

```text
Overall Strategy Quality: GOOD

✓ Sharpe remained above 2.0 in test
✓ Max drawdown stayed below 10%
✓ Validation → Test degradation is limited

⚠ Exposure concentration increased
⚠ Two features show moderate drift
```

Bu alan gerçek hesaplanan metriklere dayanmalı.

AI hiçbir metriği uydurmamalıdır.

---

# 54. Backend Domain Model

Önerilen ana objeler:

```text
Experiment
ExperimentRun
DatasetVersion
FeatureSet
ModelRun
OptimizationRun
BacktestRun
PortfolioSnapshot
Trade
Signal
RiskMetric
PerformanceMetric
```

---

# 55. Basit Entity İlişkileri

```text
Project
  |
  └── Experiment
        |
        ├── DatasetVersion
        ├── FeatureSet
        ├── ModelRun[]
        ├── OptimizationRun
        └── BacktestRun
              |
              ├── PortfolioSnapshot[]
              ├── Trade[]
              ├── RiskMetric[]
              └── PerformanceMetric[]
```

---

# 56. Veri Saklama

Time-series sonuçlar için:

```text
PostgreSQL
TimescaleDB
ClickHouse
Parquet
```

mevcut altyapıya göre seçilebilir.

MVP için PostgreSQL yeterlidir.

Ancak equity / signal gibi yüksek frekanslı veriler artarsa:

```text
ClickHouse
```

veya:

```text
TimescaleDB
```

değerlendirilebilir.

---

# 57. Cache

Dashboard verileri çoğunlukla immutable'dır.

Completed backtest için:

```text
cache aggressively
```

uygulanabilir.

Örnek:

```text
Redis
```

cache key:

```text
experiment:{id}:overview
experiment:{id}:equity
experiment:{id}:features
```

---

# 58. WebSocket

Backtest hâlâ çalışıyorsa WebSocket ile canlı ilerleme gösterilebilir.

Örnek:

```text
Experiment Running

Data Preparation     ✓
Feature Engineering  ✓
Training             ✓
Optimization         72%
Backtest             Waiting
```

Genetic chart canlı güncellenebilir.

Event:

```json
{
  "type": "GENETIC_GENERATION_COMPLETED",
  "generation": 21,
  "bestFitness": 1.72
}
```

---

# 59. Live Backtest Status

Status'lar:

```text
QUEUED
PREPARING_DATA
TRAINING
OPTIMIZING
BACKTESTING
COMPLETED
FAILED
CANCELLED
```

UI uygun badge göstermelidir.

---

# 60. Export

Kullanıcı aşağıdaki çıktıları alabilmelidir:

```text
CSV
JSON
PDF Report
```

MVP:

```text
CSV trades
JSON experiment config
```

Phase 2:

```text
PDF Report
```

---

# 61. Compare Experiments

`Compare` butonu ile kullanıcı 2-5 experiment seçebilmelidir.

Örnek:

| Experiment | Sharpe | Return | DD | Features |
|---|---:|---:|---:|---:|
| EXP-028 | 2.08 | 42% | -7.6% | 43 |
| EXP-027 | 1.82 | 38% | -6.2% | 57 |
| EXP-024 | 1.66 | 31% | -5.9% | 82 |

---

# 62. Acceptance Criteria

Dashboard tamamlanmış sayılabilmesi için:

## AC-01

Experiment açıldığında üst KPI'lar görünmelidir.

## AC-02

Equity chart strategy ve benchmark göstermelidir.

## AC-03

Train / Validation / Test alanları görsel olarak ayrılmalıdır.

## AC-04

Drawdown chart görüntülenmelidir.

## AC-05

Portfolio treemap asset ağırlıklarını göstermelidir.

## AC-06

Model karşılaştırma tablosu çalışmalıdır.

## AC-07

Genetik optimizasyon generation geçmişi gösterilmelidir.

## AC-08

Feature importance gösterilmelidir.

## AC-09

Trades server-side pagination ile çalışmalıdır.

## AC-10

Trade row click ile detail drawer açılmalıdır.

## AC-11

Bir API widget'ı hata alsa bile tüm sayfa çökmemelidir.

## AC-12

Desktop / tablet / mobile layout çalışmalıdır.

---

# 63. Kodlama Kuralları

AI ajanı aşağıdaki kurallara uymalıdır:

```text
- Existing project conventions must be respected.
- Do not replace existing architecture unnecessarily.
- Do not introduce a new state library if one already exists.
- Do not replace the existing chart library unless necessary.
- TypeScript strict typing must be used.
- Avoid any type.
- API models and UI view models should be separated where useful.
- No mock data inside production components.
- Mock data may exist only in Storybook/tests/dev fixtures.
- Components must be reusable.
- Business logic should not live inside chart rendering code.
- Formatting functions should be centralized.
- Error and loading states are mandatory.
```

---

# 64. Test Gereksinimleri

Minimum unit tests:

```text
Metric formatting
Positive / negative metric state
Trade filtering
Signal confidence formatting
Experiment status mapping
```

Component tests:

```text
Dashboard loads
Equity chart receives data
Model table sorts
Trade drawer opens
Empty state renders
Error state renders
```

E2E:

```text
Open experiment
Load results
Change benchmark
Open trade
Close drawer
Navigate to compare
```

---

# 65. Önerilen Geliştirme Sırası

AI ajanı geliştirmeyi aşağıdaki sıra ile yapmalıdır:

```text
STEP 1
Inspect existing frontend architecture.

STEP 2
Inspect existing API conventions.

STEP 3
Create experiment result types.

STEP 4
Create API client.

STEP 5
Create page shell.

STEP 6
Create KPI cards.

STEP 7
Create equity chart.

STEP 8
Add Train / Validation / Test ranges.

STEP 9
Create drawdown chart.

STEP 10
Create allocation treemap.

STEP 11
Create exposure panel.

STEP 12
Create model performance table.

STEP 13
Create feature importance.

STEP 14
Create genetic optimization chart.

STEP 15
Create trades table.

STEP 16
Create trade detail drawer.

STEP 17
Add loading / error states.

STEP 18
Add responsive layout.

STEP 19
Add tests.

STEP 20
Perform final UI polish.
```

---

# 66. AI Ajanına Ana Talimat

Aşağıdaki talimat AI ajanına doğrudan verilebilir:

```text
Implement a new Experiment & Backtest Results Dashboard in the existing project.

Do not redesign the whole application.

First inspect the existing frontend architecture, routing, design system,
API conventions, state management and chart libraries.

Reuse existing components and conventions whenever possible.

The UI should be inspired by professional quant dashboards such as
QuantConnect but must not be a visual clone.

The dashboard's primary decision metrics are:

- Sharpe Ratio
- Return
- Max Drawdown
- PSR

The system is an ML-driven quantitative research platform, therefore the
dashboard must additionally expose:

- Train / Validation / Test performance
- Model comparison
- Feature importance
- Genetic algorithm optimization
- Signal confidence
- Trade-level model information

Implement the MVP components defined in this specification.

Do not create fake backend behavior inside UI components.

If required APIs do not exist, create typed frontend service interfaces
and clearly mark backend integration points.

Preserve the existing codebase architecture.

Prefer reusable, typed, testable components.

The final dashboard should feel like a professional quantitative
research terminal rather than a generic admin dashboard.
```

---

# 67. Nihai UI Hedefi

Dashboard açıldığında kullanıcı yaklaşık 5 saniye içinde şu sorulara cevap verebilmelidir:

```text
Strategy profitable?
Risk acceptable?
Sharpe strong?
Drawdown acceptable?
Validation → Test degradation?
Best model?
Selected features?
Optimization improved performance?
Current exposure?
Which trades generated PnL?
```

Ekranın birincil odak noktası:

```text
RETURN + SHARPE + DRAWDOWN
```

olmalıdır.

ML tarafında ikinci odak:

```text
GENERALIZATION
```

yani:

```text
Train → Validation → Test
```

performansının bozulup bozulmadığıdır.

Genetik algoritma sadece Validation üzerinde optimize edilmeli;
Test set optimizasyon kararlarına dahil edilmemelidir.

Test sonucu, model ve feature seçimi tamamlandıktan sonra yalnızca
final değerlendirme için kullanılmalıdır.

---

# 68. Sonuç

Bu dashboard klasik bir backtest ekranı olmamalıdır.

Hedef yapı:

```text
Quant Backtest Dashboard
        +
ML Experiment Tracking
        +
Feature Analysis
        +
Genetic Optimization
        +
Model Comparison
        +
Trade Explainability
```

olarak tasarlanmalıdır.

Bu sayede platform yalnızca:

```text
"Strateji ne kadar kazandı?"
```

sorusuna değil,

```text
"Neden kazandı?"
"Hangi model kazandırdı?"
"Hangi feature'lar önemliydi?"
"Validation performansı testte korundu mu?"
"Optimizasyon gerçekten işe yaradı mı?"
```

sorularına da cevap verebilir.
