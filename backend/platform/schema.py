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

    @model_validator(mode="after")
    def coherent(self):
        if self.elitism >= self.population or self.min_features > self.max_features:
            raise ValueError("Elitizm popülasyondan küçük; minimum özellik maksimumdan küçük/eşit olmalı.")
        return self


class ValidationSpec(Contract):
    method: Literal["holdout", "walk_forward"] = "walk_forward"
    train_ratio: float = Field(.65, ge=.50, le=.75)
    folds: int = Field(3, ge=2, le=5)
    gap: int = Field(2, ge=2, le=30)
    locked_test: Literal[True] = True


class BacktestSpec(Contract):
    capital: float = Field(10000, ge=100, le=100000000)
    cost_bps: float = Field(.5, ge=0, le=20)
    slippage_bps: float = Field(.2, ge=0, le=20)


class ExperimentSpec(Contract):
    schema_version: Literal["1.0"] = "1.0"
    name: str = Field("EURUSD araştırması", min_length=1, max_length=120)
    description: str = Field("", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=12)
    market: Literal["FX"] = "FX"
    symbol: Literal["EURUSD"] = "EURUSD"
    dataset_id: str = Field("demo", max_length=80)
    timeframe: Literal["native", "10min", "1h", "4h", "1D"] = "native"
    features: FeatureSpec = Field(default_factory=FeatureSpec)
    models: list[Literal["ridge", "random_forest", "hist_gradient_boosting", "xgboost", "lightgbm"]] = Field(default_factory=lambda: ["ridge", "xgboost"], min_length=1, max_length=5)
    optimization: OptimizationSpec = Field(default_factory=OptimizationSpec)
    validation: ValidationSpec = Field(default_factory=ValidationSpec)
    backtest: BacktestSpec = Field(default_factory=BacktestSpec)
    seed: int = Field(42, ge=0, le=2147483647)
    regime_states: int = Field(3, ge=2, le=5)

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


class DomainError(Exception):
    def __init__(self, message, status=400, code="invalid_request"):
        super().__init__(message)
        self.status, self.code = status, code


STAGES = ["QUEUED", "DATA_PREPARATION", "FEATURE_ENGINEERING", "TRAINING", "OPTIMIZING", "VALIDATING", "TESTING", "BACKTESTING", "ANALYZING", "COMPLETED"]
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "POLICY_REJECTED"}
POLICY = {"max_population": 32, "max_generations": 20, "max_candidates": 128, "max_models": 5,
          "max_training_minutes": 10, "max_parallel_jobs": 1, "max_queued_jobs": 8, "max_rows": 50000}


def check_policy(spec, rows):
    count = spec.optimization.population * spec.optimization.generations if spec.optimization.algorithm == "genetic" else len(spec.models)
    if count > POLICY["max_candidates"] or rows > POLICY["max_rows"]:
        raise DomainError(f"Hesaplama sınırı: en fazla {POLICY['max_candidates']} aday ve {POLICY['max_rows']} bar. İstenen: {count} aday, {rows} bar.", 422, "policy_rejected")
    return {"candidate_limit": count, "fit_upper_bound": count * (spec.validation.folds if spec.validation.method == "walk_forward" else 1) + 1,
            "timeout_seconds": POLICY["max_training_minutes"] * 60}
