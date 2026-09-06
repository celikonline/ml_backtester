# PROJECT CONTEXT

## Proje Amacı

Bu proje, finansal zaman serileri üzerinde uçtan uca araştırma, feature üretimi, modelleme, validasyon, optimizasyon, backtest, stres testi ve deney yönetimi yapan bir **Quant Research & Strategy Validation Platform** geliştirmeyi amaçlar.

Sistem düşük güçlü / küçük bir yapay zekâ modeli tarafından adım adım geliştirilecektir. Bu nedenle tüm görevler küçük, bağımsız ve test edilebilir parçalara ayrılmalıdır.

---

## Mevcut Kabiliyetler

Kaynak envantere göre sistemde aşağıdaki yetenekler vardır veya kısmen vardır:

### Veri Yönetimi
- CSV veri yükleme
- OHLC, makro, FX, faiz ve cross-asset verileri
- Point-in-time yaklaşımı (`available_at`)
- Dataset snapshot
- SHA-256 hash
- Kısmi timezone / DST kontrolü

### Feature Engineering
- Lag
- Delta
- Return
- Rolling volatility
- Rolling correlation
- Rolling beta
- Kısmi feature clustering / pruning

### Rejim Analizi
- Gaussian HMM

### Modelleme
- Ridge
- Random Forest
- Histogram Gradient Boosting
- XGBoost
- LightGBM
- Kısmi stacking / blending

### Validasyon
- Walk-forward analysis
- Kısmi nested time-series CV

### Backtest
- Transaction cost
- Kısmi slippage / latency sensitivity
- Final holdout

### Optimizasyon
- Genetic Algorithm
- Kısmi hyperparameter optimization

### Risk / Açıklanabilirlik
- Kısmi stress testing
- Kısmi SHAP / permutation importance

### Deney Yönetimi
- Experiment registry
- Workspace izolasyonu

---

## Eksik Ama Öncelikli Özellikler

İlk geliştirme fazında yeni veri sağlayıcısı gerektirmeyen özellikler ele alınacaktır:

1. Information Coefficient
2. IC Decay
3. Feature Sign Consistency
4. Feature Stability Report
5. Feature Clustering
6. Redundancy Pruning
7. Purged K-Fold
8. Embargo
9. Feature Ablation
10. SHAP Stability
11. Multi-objective Genetic Algorithm fitness
12. Rolling Retraining
13. Anchored Retraining
14. Probability Calibration
15. Quantile Regression
16. Slippage Stress Test
17. Latency Stress Test
18. Systematic Stress Testing

---

## Şimdilik Ertelenecek Özellikler

Aşağıdakiler veri kaynağı ve ek altyapı gerektirdiği için ilk fazda yapılmayacaktır:

- FX Option IV Surface
- Forward Points
- FX Swaps
- OIS Curve
- Cross-Currency Basis
- CFTC Positioning
- Dealer Positioning
- Tick data
- Order flow
- Order book / microstructure
- ALFRED vintage macro entegrasyonu
- Online / incremental learning
- Distributional forecasting

---

## Temel Pipeline

```text
Data Ingestion
      ↓
Point-in-Time Validation
      ↓
Feature Engineering
      ↓
Feature Quality
      ↓
Feature Selection
      ↓
Regime Detection
      ↓
Genetic Optimization
      ↓
Model Training
      ↓
Leakage-Safe Validation
      ↓
Walk Forward
      ↓
Backtest
      ↓
Stress Testing
      ↓
Final Holdout
      ↓
Experiment Registry
```

---

## Ana Başarı Metrikleri

### Strateji Performansı
- Sharpe Ratio
- Total Return
- Annualized Return
- Max Drawdown
- Sortino Ratio
- Calmar Ratio
- Turnover
- Trade Count
- Hit Ratio
- Profit Factor

### Feature Kalitesi
- IC
- IC IR
- IC Decay
- Sign Consistency
- SHAP Stability
- Feature Redundancy
- Fold Stability

### Robustness
- Worst Stress Sharpe
- Worst Stress Drawdown
- Cost Sensitivity
- Slippage Sensitivity
- Latency Sensitivity

---

## Düşük Güçlü AI İçin Zorunlu Kurallar

1. Aynı anda yalnızca bir görev üzerinde çalış.
2. Büyük refactor yapma.
3. Çalışan API sözleşmelerini bozma.
4. Yeni dependency eklemeden önce mevcut dependency'leri kontrol et.
5. Her feature için unit test yaz.
6. Mevcut testler başarısızsa bir sonraki göreve geçme.
7. Final holdout verisini feature selection, HPO veya GA fitness içinde kullanma.
8. Scaler, PCA, clustering ve selector gibi nesneleri yalnızca training verisinde fit et.
9. Time-series sırasını bozma.
10. Her tamamlanan görev için kısa CHANGELOG kaydı ekle.

---

## Hedef Mimari Prensip

Sistem yalnızca:

```text
Train → Backtest
```

yapan bir yapı olmamalıdır.

Hedef:

```text
Research
→ Stability
→ Leakage Control
→ Optimization
→ Validation
→ Stress Testing
→ Final Holdout
→ Reproducible Experiment
```

zincirini kurmaktır.
