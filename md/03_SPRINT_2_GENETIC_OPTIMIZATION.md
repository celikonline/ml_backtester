# SPRINT 2 — GENETIC OPTIMIZATION

## Sprint Hedefi

Mevcut Genetic Algorithm yapısını bozmadan, yalnızca Sharpe'a bağımlı optimizasyondan daha sağlam multi-objective fitness yaklaşımına geçmek.

---

## 1. Mevcut GA'ya Dokunma Prensibi

Mevcut:
- Population
- Selection
- Crossover
- Mutation
- Evaluation

çalışıyorsa yeniden yazma.

Yeni bir fitness adapter ekle.

---

## 2. Fitness Calculator

Önerilen interface:

```python
class QuantFitnessCalculator:

    def calculate(
        self,
        sharpe: float,
        feature_quality: float,
        max_drawdown: float,
        turnover: float
    ) -> float:
        ...
```

---

## 3. Default Fitness

```text
fitness =
  0.50 * normalized_sharpe
+ 0.20 * normalized_feature_quality
- 0.20 * normalized_drawdown
- 0.10 * normalized_turnover
```

Config:

```yaml
genetic_algorithm:
  fitness:
    sharpe_weight: 0.50
    feature_quality_weight: 0.20
    drawdown_weight: 0.20
    turnover_weight: 0.10
```

---

## 4. Kritik Kural

Aşağıdaki veriler GA fitness için KULLANILMAMALIDIR:

```text
Final Holdout
Future Data
Test Set
```

Fitness yalnızca training + validation sonuçlarından üretilmelidir.

---

## 5. Feature Quality Entegrasyonu

Sprint 1 çıktısı kullanılmalıdır:

```text
IC
IC Decay
Sign Consistency
Cluster Quality
Selected Feature Set
```

Öneri:

```text
feature_quality =
0.50 * abs_ic_score
+ 0.30 * sign_consistency
+ 0.20 * stability
```

---

## 6. Fitness Breakdown Artifact

Her candidate için:

```json
{
  "candidate_id": "...",
  "generation": 12,
  "sharpe": 1.72,
  "feature_quality": 0.81,
  "max_drawdown": 0.09,
  "turnover": 1.4,
  "fitness": 0.73
}
```

---

## 7. Feature Count Kontrolü

Çok fazla feature seçimini önlemek için opsiyonel penalty:

```text
feature_count_penalty
```

Config:

```yaml
genetic_algorithm:
  feature_count_penalty:
    enabled: false
    max_features: 40
    penalty_weight: 0.05
```

İlk sürümde kapalı olabilir.

---

## 8. Reproducibility

Her GA run için kaydet:

```text
random_seed
population_size
generation_count
mutation_rate
crossover_rate
fitness_weights
dataset_hash
feature_universe
```

---

## 9. Tests

```text
test_fitness_increases_with_sharpe
test_fitness_decreases_with_drawdown
test_fitness_decreases_with_turnover
test_feature_quality_affects_fitness
test_final_holdout_not_used
test_same_seed_same_initial_population
```

---

## 10. Definition of Done

```text
[ ] Fitness adapter eklendi
[ ] Eski GA davranışı korunuyor
[ ] Config ile ağırlık değişiyor
[ ] Feature quality fitness'e giriyor
[ ] Drawdown penalty çalışıyor
[ ] Turnover penalty çalışıyor
[ ] Final holdout kullanılmıyor
[ ] Fitness breakdown kaydediliyor
[ ] Testler geçiyor
```
