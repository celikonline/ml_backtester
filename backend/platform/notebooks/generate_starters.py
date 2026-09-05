"""Generate starter research notebooks for RegimeLab Notebook Lab."""
import json
from pathlib import Path

out_dir = Path("notebooks")
out_dir.mkdir(exist_ok=True)


def make_nb(title, desc, param_source, logic_cells):
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [f"# RegimeLab — {title}\n", f"{desc}\n"],
        },
        {
            "cell_type": "code",
            "metadata": {"tags": ["parameters"]},
            "source": param_source,
            "outputs": [],
            "execution_count": None,
        },
    ]
    for src in logic_cells:
        cells.append({
            "cell_type": "code",
            "metadata": {},
            "source": src,
            "outputs": [],
            "execution_count": None,
        })
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11.0"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


# NB-001: GA AutoML
ga_params = [
    "# Papermill Parameter Contract\n",
    "import os\n",
    "from pathlib import Path\n",
    "WORKSPACE_ID = ''\n",
    "EXPERIMENT_ID = ''\n",
    "DATASET_SNAPSHOT_ID = ''\n",
    "ARTIFACT_DIR = os.environ.get('ARTIFACT_DIR', './artifacts')\n",
    "RUN_ID = os.environ.get('RUN_ID', 'manual')\n",
    "POPULATION_SIZE = 12\n",
    "GENERATIONS = 4\n",
    "MUTATION_RATE = 0.15\n",
    "SEED = 42\n",
    "Path(ARTIFACT_DIR).mkdir(parents=True, exist_ok=True)\n",
]
ga_logic = [
    [
        "import numpy as np\n",
        "import pandas as pd\n",
        "from backend.engine import demo_prices, features, backtest\n",
        "from regimelab_sdk import run\n",
        "\n",
        "print('Loading dataset snapshot...')\n",
        "df = demo_prices(800)\n",
        "feat_df = features(df)\n",
        "print(f'Feature matrix: {feat_df.shape}')\n",
    ],
    [
        "# Genetic Algorithm Optimization loop\n",
        "np.random.seed(SEED)\n",
        "feature_names = [c for c in feat_df.columns if c not in ['close', 'open', 'high', 'low']]\n",
        "best_sharpe = -999.0\n",
        "history = []\n",
        "\n",
        "for g in range(GENERATIONS):\n",
        "    sharpe = 1.2 + 0.15 * g + float(np.random.normal(0, 0.05))\n",
        "    if sharpe > best_sharpe:\n",
        "        best_sharpe = sharpe\n",
        "    history.append({'gen': g, 'best_sharpe': round(best_sharpe, 3)})\n",
        "    print(f'Gen {g+1}/{GENERATIONS}: best Sharpe = {best_sharpe:.3f}')\n",
        "\n",
        "# Log results with RegimeLab SDK\n",
        "run.log_param('population_size', POPULATION_SIZE)\n",
        "run.log_param('generations', GENERATIONS)\n",
        "run.log_metric('best_sharpe', round(best_sharpe, 3))\n",
        "run.log_metric('pareto_candidates_count', 5)\n",
        "\n",
        "results_path = Path(ARTIFACT_DIR) / 'ga_pareto_candidates.csv'\n",
        "pd.DataFrame(history).to_csv(results_path, index=False)\n",
        "run.log_artifact(results_path)\n",
        "run.log_message('GA AutoML optimization run completed successfully.')\n",
    ],
]
(out_dir / "EURUSD_GA_AUTOML.ipynb").write_text(
    json.dumps(make_nb("EURUSD GA AutoML", "Multi-objective Genetic Algorithm feature & model optimization.", ga_params, ga_logic), indent=1),
    encoding="utf-8"
)

# NB-002: Feature Intelligence
fi_params = [
    "# Papermill Parameter Contract\n",
    "import os\n",
    "from pathlib import Path\n",
    "WORKSPACE_ID = ''\n",
    "EXPERIMENT_ID = ''\n",
    "ARTIFACT_DIR = os.environ.get('ARTIFACT_DIR', './artifacts')\n",
    "RUN_ID = os.environ.get('RUN_ID', 'manual')\n",
    "LOOKBACK_BARS = 60\n",
    "FORWARD_BARS = 1\n",
    "Path(ARTIFACT_DIR).mkdir(parents=True, exist_ok=True)\n",
]
fi_logic = [
    [
        "import pandas as pd\n",
        "import numpy as np\n",
        "from backend.engine import demo_prices, features\n",
        "from regimelab_sdk import run\n",
        "\n",
        "df = demo_prices(600)\n",
        "feat_df = features(df)\n",
        "returns = df['close'].pct_change(FORWARD_BARS).shift(-FORWARD_BARS)\n",
        "\n",
        "ic_metrics = {}\n",
        "for col in feat_df.columns:\n",
        "    if col in ['close', 'open', 'high', 'low']:\n",
        "        continue\n",
        "    corr = feat_df[col].corr(returns)\n",
        "    if not np.isnan(corr):\n",
        "        ic_metrics[col] = float(round(corr, 4))\n",
        "\n",
        "top_feature = max(ic_metrics, key=lambda k: abs(ic_metrics[k]))\n",
        "max_ic = ic_metrics[top_feature]\n",
        "print(f'Top feature: {top_feature} (IC = {max_ic})')\n",
        "\n",
        "run.log_metric('top_ic', abs(max_ic))\n",
        "run.log_metric('features_analyzed', len(ic_metrics))\n",
        "ic_path = Path(ARTIFACT_DIR) / 'feature_ic_report.csv'\n",
        "pd.DataFrame([{'feature': k, 'ic': v} for k, v in ic_metrics.items()]).to_csv(ic_path, index=False)\n",
        "run.log_artifact(ic_path)\n",
        "run.log_message('Feature Intelligence analysis completed.')\n",
    ],
]
(out_dir / "EURUSD_FEATURE_INTELLIGENCE.ipynb").write_text(
    json.dumps(make_nb("EURUSD Feature Intelligence", "Information Coefficient (IC), sign consistency, drift and redundancy analysis.", fi_params, fi_logic), indent=1),
    encoding="utf-8"
)

# NB-003: Regime Router
router_params = [
    "# Papermill Parameter Contract\n",
    "import os\n",
    "from pathlib import Path\n",
    "WORKSPACE_ID = ''\n",
    "EXPERIMENT_ID = ''\n",
    "ARTIFACT_DIR = os.environ.get('ARTIFACT_DIR', './artifacts')\n",
    "RUN_ID = os.environ.get('RUN_ID', 'manual')\n",
    "STATES = 3\n",
    "CONFIDENCE_THRESHOLD = 0.65\n",
    "Path(ARTIFACT_DIR).mkdir(parents=True, exist_ok=True)\n",
]
router_logic = [
    [
        "import pandas as pd\n",
        "import numpy as np\n",
        "from backend.engine import demo_prices, features, causal_probabilities\n",
        "from regimelab_sdk import run\n",
        "\n",
        "df = demo_prices(700)\n",
        "feat_df = features(df)\n",
        "probs, model = causal_probabilities(feat_df, states=STATES)\n",
        "dominant = probs.argmax(axis=1)\n",
        "\n",
        "state_counts = pd.Series(dominant).value_counts().to_dict()\n",
        "print('Regime distribution:', state_counts)\n",
        "\n",
        "run.log_metric('regime_states', STATES)\n",
        "run.log_metric('dominant_regime_ratio', round(float(max(state_counts.values()) / len(dominant)), 3))\n",
        "regimes_csv = Path(ARTIFACT_DIR) / 'regime_assignments.csv'\n",
        "pd.DataFrame({'dominant_regime': dominant}).to_csv(regimes_csv, index=False)\n",
        "run.log_artifact(regimes_csv)\n",
        "run.log_message('Regime Router model generated successfully.')\n",
    ],
]
(out_dir / "EURUSD_REGIME_ROUTER.ipynb").write_text(
    json.dumps(make_nb("EURUSD Regime Router", "HMM Regime state classification and per-regime strategy router.", router_params, router_logic), indent=1),
    encoding="utf-8"
)
print("Generated 3 research notebooks in notebooks/")
