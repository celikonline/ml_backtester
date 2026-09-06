"""Quant modulleri icin varsayilan konfigurasyon (spec bolum 43).

Tum yeni ozellikler config uzerinden acilip kapatilabilir.
"""
from __future__ import annotations

DEFAULT_QUANT_CONFIG = {
    "feature_analysis": {
        "ic": {"enabled": True},
        "ic_decay": {"enabled": True, "horizons": [1, 2, 3, 5, 10, 20]},
        "clustering": {"enabled": True, "correlation_threshold": 0.85},
        "quality_weights": {"ic": 0.50, "sign_consistency": 0.30, "stability": 0.20},
    },
    "validation": {
        "purged_kfold": {"enabled": True, "n_splits": 5, "purge_window": 5, "embargo_pct": 0.01},
        "embargo_bars": None,
    },
    "retraining": {"mode": "rolling", "train_window": 500, "test_window": 50,
                   "step": 50, "initial_train_window": 500},
    "genetic_algorithm": {"fitness": {"sharpe_weight": 0.50, "feature_quality_weight": 0.20,
                                      "drawdown_weight": 0.20, "turnover_weight": 0.10}},
    "calibration": {"enabled": False, "method": "isotonic"},
    "quantile": {"enabled": False, "quantiles": [0.1, 0.5, 0.9]},
    "pca": {"enabled": False, "variance_threshold": 0.95},
    "pls": {"enabled": False, "n_components": 5},
    "transformations": {"tanh": False, "sigmoid": False,
                        "winsorize": {"enabled": True, "lower": 0.01, "upper": 0.99}},
    "stress_test": {"slippage_bps": [0, 1, 2, 5, 10, 20], "latency_bars": [0, 1, 2, 3, 5]},
}

#: Registry'de saklanan yeni artifact tipleri (spec bolum 30).
QUANT_ARTIFACT_TYPES = ["ic_report", "ic_decay_report", "feature_stability_report",
                        "feature_cluster_report", "ablation_report", "shap_stability_report",
                        "purged_cv_report", "calibration_report", "stress_test_report"]


def get_quant_config(overrides: dict | None = None) -> dict:
    """Varsayilan config + derin olmayan override birlesimi."""
    import copy
    cfg = copy.deepcopy(DEFAULT_QUANT_CONFIG)
    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key] = {**cfg[key], **value}
        else:
            cfg[key] = value
    return cfg
