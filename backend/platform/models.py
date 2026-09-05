"""Model adapters share fit/predict/save; no orchestration-specific branching."""
import joblib
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor

MODEL_REGISTRY = {
    "ridge": {"name": "Ridge", "parameters": [{"alpha": a} for a in [1, 10, 100]]},
    "random_forest": {"name": "Random Forest", "parameters": [{"max_depth": d} for d in [3, 5, 8]]},
    "hist_gradient_boosting": {"name": "Histogram Gradient Boosting", "parameters": [{"learning_rate": r} for r in [.03, .08, .15]]},
    "xgboost": {"name": "XGBoost", "parameters": [{"max_depth": d, "learning_rate": .05} for d in [2, 4, 6]]},
    "lightgbm": {"name": "LightGBM", "parameters": [{"num_leaves": n, "learning_rate": .05} for n in [7, 15, 31]]},
}


class ModelAdapter:
    def __init__(self, model_id, params, seed):
        self.model_id, self.params = model_id, params
        if model_id == "ridge":
            self.model = make_pipeline(StandardScaler(), Ridge(**params))
        elif model_id == "random_forest":
            self.model = RandomForestRegressor(**params, n_estimators=50, min_samples_leaf=15, random_state=seed, n_jobs=2)
        elif model_id == "hist_gradient_boosting":
            self.model = HistGradientBoostingRegressor(**params, max_iter=60, max_leaf_nodes=12, early_stopping=False, random_state=seed)
        elif model_id == "xgboost":
            from xgboost import XGBRegressor
            self.model = XGBRegressor(**params, n_estimators=60, reg_lambda=5, random_state=seed, n_jobs=2, tree_method="hist")
        elif model_id == "lightgbm":
            from lightgbm import LGBMRegressor
            self.model = LGBMRegressor(**params, n_estimators=60, random_state=seed, n_jobs=2, verbosity=-1, deterministic=True, force_col_wise=True)
        else:
            raise ValueError("Desteklenmeyen model adapter'ı.")

    def fit(self, x, y):
        self.model.fit(x, y * 10000)
        return self

    def predict(self, x):
        return self.model.predict(x) / 10000

    def get_params(self):
        return {"model": self.model_id, "parameters": self.params}

    def save(self, path):
        joblib.dump(self, path)

    @staticmethod
    def load(path):
        """Only trusted, server-generated model files; never an upload endpoint."""
        return joblib.load(path)
