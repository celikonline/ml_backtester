"""Faz 3: GA multi-objective fitness adapter (spec bolum 9, 39).

Mevcut GA bozulmaz; bu adapter yeni fitness hesaplar.
fitness = w1*sharpe + w2*feature_quality - w3*max_drawdown - w4*turnover
Metrikler bounded normalizasyonla sinirlanir.
"""
from __future__ import annotations

DEFAULT_FITNESS_WEIGHTS = {
    "sharpe_weight": 0.50,
    "feature_quality_weight": 0.20,
    "drawdown_weight": 0.20,
    "turnover_weight": 0.10,
}


def _clip(x: float, lo: float, hi: float) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    if v != v:  # NaN
        return 0.0
    return max(lo, min(hi, v))


class QuantFitnessCalculator:
    def __init__(self, weights: dict | None = None):
        self.weights = {**DEFAULT_FITNESS_WEIGHTS, **(weights or {})}

    def normalize_sharpe(self, sharpe: float) -> float:
        # Sharpe -3..+3 araligi 0..1'e cekilir.
        return (_clip(sharpe, -3.0, 3.0) + 3.0) / 6.0

    def normalize_drawdown(self, max_drawdown: float) -> float:
        # max_drawdown <= 0; buyuk kayip -> buyuk ceza (0..1).
        return _clip(abs(max_drawdown), 0.0, 1.0)

    def normalize_turnover(self, turnover: float) -> float:
        return _clip(turnover, 0.0, 100.0) / 100.0

    def breakdown(self, sharpe: float, feature_quality: float,
                  max_drawdown: float, turnover: float) -> dict:
        w = self.weights
        return {
            "sharpe_contribution": w["sharpe_weight"] * self.normalize_sharpe(sharpe),
            "feature_quality_contribution": w["feature_quality_weight"] * _clip(feature_quality, 0.0, 1.0),
            "drawdown_penalty": w["drawdown_weight"] * self.normalize_drawdown(max_drawdown),
            "turnover_penalty": w["turnover_weight"] * self.normalize_turnover(turnover),
        }

    def calculate(self, sharpe: float, feature_quality: float,
                  max_drawdown: float, turnover: float) -> float:
        parts = self.breakdown(sharpe, feature_quality, max_drawdown, turnover)
        return (parts["sharpe_contribution"] + parts["feature_quality_contribution"]
                - parts["drawdown_penalty"] - parts["turnover_penalty"])
