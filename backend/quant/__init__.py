"""Quant research extensions (Dusuk_Guclu plan).

Mevcut pipeline bozulmadan eklenen yeni moduller.
Her modul kucuk tutulur; ortak kurallar:
- scaler/selector yalnizca train uzerinde fit edilir (bu paket saf fonksiyondur),
- final holdout verisi bu fonksiyonlara asla gecirilmemelidir (caller sorumlulugu).
"""
from .ic import (
    calculate_ic,
    calculate_feature_ic,
    calculate_ic_decay,
    calculate_sign_consistency,
    sign_consistency_report,
    feature_quality_score,
    feature_quality_report,
    DEFAULT_IC_DECAY_HORIZONS,
)
from .clustering import cluster_features, prune_redundant_features
from .validation import PurgedKFold, rolling_splits, anchored_splits, nested_search
from .ablation import ablation_report, shap_stability_report
from .fitness import QuantFitnessCalculator, DEFAULT_FITNESS_WEIGHTS
from .calibration import calibrate_probabilities, calibration_metrics, QuantilePredictor
from .stress import slippage_stress, latency_stress, cost_stress_matrix, systematic_stress
from .dimensionality import apply_pca, apply_pls, apply_transformations

__all__ = [
    "calculate_ic", "calculate_feature_ic", "calculate_ic_decay",
    "calculate_sign_consistency", "sign_consistency_report",
    "feature_quality_score", "feature_quality_report", "DEFAULT_IC_DECAY_HORIZONS",
    "cluster_features", "prune_redundant_features",
    "PurgedKFold", "rolling_splits", "anchored_splits", "nested_search",
    "ablation_report", "shap_stability_report",
    "QuantFitnessCalculator", "DEFAULT_FITNESS_WEIGHTS",
    "calibrate_probabilities", "calibration_metrics", "QuantilePredictor",
    "slippage_stress", "latency_stress", "cost_stress_matrix", "systematic_stress",
    "apply_pca", "apply_pls", "apply_transformations",
]
