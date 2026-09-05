from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class FeatureSpec(Contract):
    groups: list[Literal["technical", "trend", "momentum", "volatility", "statistical", "lagged_external"]] = Field(default_factory=lambda: ["technical"], min_length=1)
    families: list[Literal["lagged_technical", "macro_lagged", "cross_asset_lagged"]] = Field(default_factory=list)
    names: list[str] = Field(default_factory=list, max_length=80)


class OptimizationSpec(Contract):
    algorithm: Literal["none", "genetic"] = "none"
    population: int = Field(8, ge=4, le=32)
    generations: int = Field(4, ge=1, le=20)
    mutation_rate: float = Field(.12, ge=0, le=1)
    crossover_rate: float = Field(.8, ge=0, le=1)
    elitism: int = Field(2, ge=1, le=8)
    min_features: int = Field(3, ge=1, le=80)
    max_features: int = Field(30, ge=1, le=80)
    hyperparameters: bool = True
    objective: Literal["sharpe", "return"] = "sharpe"
    max_drawdown: float = Field(.5, gt=0, le=1)
    thresholds_bps: list[float] = Field(default_factory=lambda:[0, .25, .5, 1, 2], min_length=1, max_length=20)

    @model_validator(mode="after")
    def coherent(self):
        if self.elitism >= self.population or self.min_features > self.max_features:
            raise ValueError("Elitizm popülasyondan küçük; minimum özellik maksimumdan küçük/eşit olmalı.")
        return self


class SearchSpaceDefinition(Contract):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field("", max_length=1000)
    feature_groups: list[str] = Field(default_factory=lambda:["technical"], min_length=1)
    features: list[str] = Field(default_factory=list, max_length=80)
    min_features: int = Field(3, ge=1, le=80)
    max_features: int = Field(30, ge=1, le=80)
    models: list[Literal["ridge", "random_forest", "hist_gradient_boosting", "xgboost", "lightgbm"]] = Field(default_factory=lambda:["ridge"], min_length=1)
    hyperparameters: bool = True
    thresholds_bps: list[float] = Field(default_factory=lambda:[0, .25, .5, 1, 2], min_length=1)
    regime_states: int = Field(3, ge=2, le=5)
    max_drawdown: float = Field(.5, gt=0, le=1)

    @model_validator(mode="after")
    def bounds(self):
        if self.min_features > self.max_features: raise ValueError("Minimum özellik maksimumdan büyük olamaz.")
        return self


class ValidationSpec(Contract):
    method: Literal["holdout", "walk_forward"] = "walk_forward"
    train_ratio: float = Field(.65, ge=.50, le=.75)
    folds: int = Field(3, ge=2, le=5)
    gap: int = Field(2, ge=2, le=30)
    locked_test: Literal[True] = True


class BacktestRealityConfig(Contract):
    """Execution assumptions; timestamps remain UTC and signals fill next-bar."""
    spread_model: Literal["fixed", "ohlc_range"] = "fixed"
    spread_bps: float = Field(.5, ge=0, le=50)
    commission_bps: float = Field(0, ge=0, le=50)
    slippage_bps: float = Field(.2, ge=0, le=50)
    rollover_bps_per_day: float = Field(0, ge=-50, le=50)
    rollover_long_bps_per_day: float | None = Field(None, ge=-50, le=50)
    rollover_short_bps_per_day: float | None = Field(None, ge=-50, le=50)
    triple_wednesday_rollover: bool = False
    timezone: str = "UTC"
    max_leverage: float = Field(1, ge=1, le=30)
    max_position_fraction: float = Field(1, gt=0, le=1)


class BacktestSpec(Contract):
    capital: float = Field(10000, ge=100, le=100000000)
    cost_bps: float = Field(.5, ge=0, le=20)
    slippage_bps: float = Field(.2, ge=0, le=20)
    spread_model: Literal["fixed", "ohlc_range"] = "fixed"
    spread_bps: float = Field(.5, ge=0, le=50)
    commission_bps: float = Field(0, ge=0, le=50)
    rollover_bps_per_day: float = Field(0, ge=-50, le=50)
    timezone: str = "UTC"
    max_leverage: float = Field(1, ge=1, le=30)
    max_position_fraction: float = Field(1, gt=0, le=1)
    reality: BacktestRealityConfig = Field(default_factory=BacktestRealityConfig)


class ExperimentSpec(Contract):
    schema_version: Literal["1.0"] = "1.0"
    name: str = Field("EURUSD araştırması", min_length=1, max_length=120)
    description: str = Field("", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=12)
    market: Literal["FX"] = "FX"
    symbol: Literal["EURUSD"] = "EURUSD"
    dataset_id: str = Field("demo", max_length=80)
    workspace_id: str | None = Field(None, max_length=36)
    timeframe: Literal["native", "10min", "1h", "4h", "1D"] = "native"
    features: FeatureSpec = Field(default_factory=FeatureSpec)
    models: list[Literal["ridge", "random_forest", "hist_gradient_boosting", "xgboost", "lightgbm"]] = Field(default_factory=lambda: ["ridge", "xgboost"], min_length=1, max_length=5)
    optimization: OptimizationSpec = Field(default_factory=OptimizationSpec)
    validation: ValidationSpec = Field(default_factory=ValidationSpec)
    backtest: BacktestSpec = Field(default_factory=BacktestSpec)
    seed: int = Field(42, ge=0, le=2147483647)
    regime_states: int = Field(3, ge=2, le=5)
    search_space_id: str | None = Field(None, max_length=36)

    @model_validator(mode="after")
    def distinct(self):
        if len(set(self.models)) != len(self.models):
            raise ValueError("Model listesinde tekrar var.")
        if not self.name.strip():
            raise ValueError("Deney adı boş olamaz.")
        return self


class CompareSpec(Contract):
    experiment_ids: list[str] = Field(min_length=2, max_length=5)


class CloneSpec(Contract):
    name: str | None = Field(None, min_length=1, max_length=120)
    specification: ExperimentSpec | None = None


class WorkspaceCreate(Contract):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field("", max_length=2000)
    market: str = Field("", max_length=16)
    base_currency: str = Field("", max_length=8)
    timezone: str = Field("UTC", max_length=40)
    owner: str | None = Field(None, max_length=120)


class WorkspacePatch(Contract):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    market: str | None = Field(None, max_length=16)
    base_currency: str | None = Field(None, max_length=8)
    timezone: str | None = Field(None, max_length=40)
    owner: str | None = Field(None, max_length=120)


class DomainError(Exception):
    def __init__(self, message, status=400, code="invalid_request"):
        super().__init__(message)
        self.status, self.code = status, code


STAGES = ["QUEUED", "DATA_PREPARATION", "FEATURE_ENGINEERING", "TRAINING", "OPTIMIZING", "VALIDATING", "TESTING", "BACKTESTING", "ANALYZING", "COMPLETED"]
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "POLICY_REJECTED"}
POLICY = {"max_population": 32, "max_generations": 20, "max_candidates": 128, "max_models": 5,
          "max_training_minutes": 10, "max_parallel_jobs": 1, "max_queued_jobs": 8, "max_rows": 50000}
RESEARCH_BUDGET = {"max_experiments": 50, "max_candidates": 2000, "max_backtests": 2500,
                   "max_sealed_test_accesses": 1, "risk_reject_at": 0.90}


def check_policy(spec, rows):
    count = spec.optimization.population * spec.optimization.generations if spec.optimization.algorithm == "genetic" else len(spec.models)
    if count > POLICY["max_candidates"] or rows > POLICY["max_rows"]:
        raise DomainError(f"Hesaplama sınırı: en fazla {POLICY['max_candidates']} aday ve {POLICY['max_rows']} bar. İstenen: {count} aday, {rows} bar.", 422, "policy_rejected")
    return {"candidate_limit": count, "fit_upper_bound": count * (spec.validation.folds if spec.validation.method == "walk_forward" else 1) + 1,
            "timeout_seconds": POLICY["max_training_minutes"] * 60}


def estimate_research_risk(spec, rows, usage=None):
    """A transparent, deliberately conservative multiple-testing estimate."""
    estimate = check_policy(spec, rows)
    usage = usage or {}
    candidates = estimate["candidate_limit"]
    backtests = candidates * (spec.validation.folds if spec.validation.method == "walk_forward" else 1) + 1
    pressure = max((usage.get("experiments", 0) + 1) / RESEARCH_BUDGET["max_experiments"],
                   (usage.get("candidates", 0) + candidates) / RESEARCH_BUDGET["max_candidates"],
                   (usage.get("backtests", 0) + backtests) / RESEARCH_BUDGET["max_backtests"])
    return {"estimated_candidates": candidates, "estimated_backtests": backtests,
            "risk_score": min(1.0, round(pressure, 4)), "limits": RESEARCH_BUDGET,
            "sealed_test_accesses": usage.get("sealed_test_accesses", 0),
            "post_test_iteration": usage.get("sealed_test_accesses", 0) > 0}
