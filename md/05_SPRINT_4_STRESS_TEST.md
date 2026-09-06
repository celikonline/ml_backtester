# SPRINT 4 — STRESS TESTING

## Sprint Hedefi

Backtest sonucunun işlem maliyetleri, slippage, latency ve zor piyasa koşullarına karşı dayanıklılığını ölçmek.

---

# 1. Ana Prensip

Yeni backtest engine yazma.

Mevcut backtest engine'e farklı parametrelerle tekrar tekrar çağrı yap.

---

# 2. Slippage Stress

Default senaryolar:

```python
slippage_bps = [0, 1, 2, 5, 10, 20]
```

Output:

```text
slippage_bps
total_return
sharpe
max_drawdown
trade_count
```

---

# 3. Latency Stress

İlk sürümde latency bar gecikmesi olarak uygulanabilir.

```python
latency_bars = [0, 1, 2, 3, 5]
```

Signal execution:

```python
executed_signal = signal.shift(latency_bars)
```

---

# 4. Commission Stress

Default:

```python
commission_bps = [0, 1, 2, 5, 10]
```

---

# 5. Cost Stress Matrix

İki boyutlu kombinasyon:

```text
             Slippage
             0   2   5   10
Commission
0
2
5
10
```

Her hücrede minimum:

```text
Sharpe
```

Ayrıca artifact:

```text
Return
Max Drawdown
Trade Count
```

---

# 6. Sistematik Senaryolar

İlk sürüm:

```text
BASE
HIGH_COST
HIGH_SLIPPAGE
LATENCY_1_BAR
LATENCY_3_BAR
HIGH_VOLATILITY
LOW_LIQUIDITY_PROXY
```

---

# 7. Robustness Score

İlk sürüm için opsiyonel:

```text
robustness_score =
0.40 * normalized_base_sharpe
+ 0.30 * normalized_worst_stress_sharpe
- 0.30 * normalized_worst_drawdown
```

Bu skor ilk aşamada sadece raporlama için kullanılmalı; GA fitness'e hemen bağlanmamalıdır.

---

# 8. API

```text
POST /api/backtest/stress
POST /api/backtest/slippage-stress
POST /api/backtest/latency-stress
GET  /api/backtest/stress/{experiment_id}
```

---

# 9. Artifact

```text
stress_test_report
slippage_matrix
latency_curve
cost_matrix
worst_case_summary
```

---

# 10. Minimum Testler

```text
test_zero_cost_matches_base
test_higher_cost_not_better_due_to_cost_only
test_latency_shift
test_scenario_count
test_worst_case_selected
test_artifact_created
```

---

# 11. Definition of Done

```text
[ ] Slippage stress çalışıyor
[ ] Latency stress çalışıyor
[ ] Commission stress çalışıyor
[ ] Cost matrix oluşuyor
[ ] Worst-case summary oluşuyor
[ ] Backtest engine kopyalanmadı
[ ] API çalışıyor
[ ] Artifact kaydediliyor
[ ] Testler geçiyor
```
