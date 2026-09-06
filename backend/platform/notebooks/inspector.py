"""
Notebook Lab — static inspector.

Scans a notebook's source cells for:
  - pip / apt install calls
  - Hard-coded secrets (patterns)
  - Unknown imports against a known-good environment package list
  - Hardcoded local paths
  - External network access patterns
"""
import ast
import json
import re
from pathlib import Path
from typing import Any


# Packages shipped in the default regimelab-quant environment
QUANT_ENV_PACKAGES = {
    "numpy", "pandas", "scipy", "sklearn", "sklearn.pipeline",
    "xgboost", "lightgbm", "optuna", "hmmlearn", "yfinance",
    "pandas_datareader", "matplotlib", "joblib", "pyarrow",
    "papermill", "nbclient", "nbformat", "requests", "httpx",
    "pathlib", "os", "sys", "json", "csv", "datetime", "time",
    "math", "random", "hashlib", "uuid", "io", "re", "copy",
    "itertools", "functools", "collections", "typing", "abc",
    "contextlib", "threading", "multiprocessing", "subprocess",
    "warnings", "logging", "traceback", "inspect", "types",
    "dataclasses", "enum", "struct", "string", "textwrap",
    "dukascopy", "regimelab_sdk",
}

# Patterns that suggest a hardcoded secret
_SECRET_PATTERNS = [
    re.compile(r'[A-Z_]{3,40}\s*=\s*["\'][a-f0-9]{20,}["\']', re.IGNORECASE),
    re.compile(r'api[_\-]?key\s*=\s*["\'].+?["\']', re.IGNORECASE),
    re.compile(r'token\s*=\s*["\'].+?["\']', re.IGNORECASE),
    re.compile(r'password\s*=\s*["\'].+?["\']', re.IGNORECASE),
    re.compile(r'secret\s*=\s*["\'].+?["\']', re.IGNORECASE),
]

# Patterns for network access
_NETWORK_PATTERNS = [
    re.compile(r'requests\.(get|post|put|delete|patch)\s*\(', re.IGNORECASE),
    re.compile(r'httpx\.(get|post|AsyncClient)', re.IGNORECASE),
    re.compile(r'urllib\.request', re.IGNORECASE),
    re.compile(r'yfinance|yf\.download', re.IGNORECASE),
    re.compile(r'pandas_datareader', re.IGNORECASE),
    re.compile(r'dukascopy', re.IGNORECASE),
    re.compile(r'fred\.get_series', re.IGNORECASE),
]

# Hardcoded path patterns
_PATH_PATTERNS = [
    re.compile(r'["\'][A-Za-z]:\\\\', re.IGNORECASE),   # Windows absolute
    re.compile(r'["\']/(?:home|Users|tmp|root|var|data)/'),  # Unix absolute
    re.compile(r'SAVE_DIR\s*=\s*["\'][^{]', re.IGNORECASE),
]


def _cell_sources(nb: dict[str, Any]) -> list[tuple[int, str, str]]:
    """Yield (cell_index, cell_type, source_code)."""
    cells = nb.get("cells", [])
    result = []
    for idx, cell in enumerate(cells):
        source = "".join(cell.get("source", []))
        result.append((idx, cell.get("cell_type", ""), source))
    return result


def _has_parameter_tag(nb: dict[str, Any]) -> bool:
    for cell in nb.get("cells", []):
        tags = cell.get("metadata", {}).get("tags", [])
        if "parameters" in tags:
            return True
    return False


def _extract_imports(source: str) -> set[str]:
    imports = set()
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])
    except SyntaxError:
        pass
    return imports


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name): return node.id
    if isinstance(node, ast.Attribute): return node.attr
    return ""


def _static_analysis(cells: list[tuple[int, str, str]]) -> dict[str, Any]:
    """Extract research concepts without executing notebook code."""
    models: set[str] = set(); validation: set[str] = set(); backtest: set[str] = set()
    datasets: set[str] = set(); features: set[str] = set(); metrics: set[str] = set()
    targets: set[str] = set(); model_parameters: dict[str, dict[str, str]] = {}; warnings: list[dict[str, str]] = []
    for idx, ctype, source in cells:
        if ctype != "code": continue
        low = source.lower()
        for match in re.findall(r"(?:read_csv|read_parquet)\s*\(\s*['\"]([^'\"]+)", source, re.I): datasets.add(match)
        for match in re.findall(r"(?:features?|feature_cols?)\s*=\s*\[([^\]]+)\]", source, re.I):
            features.update(re.findall(r"['\"]([^'\"]+)['\"]", match))
        targets.update(re.findall(r"(?:target|target_col|target_column|label)\s*=\s*['\"]([^'\"]+)", source, re.I))
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = _call_name(node.func)
                    model_map = {"XGBRegressor":"XGBoost", "XGBClassifier":"XGBoost", "LGBMRegressor":"LightGBM", "LGBMClassifier":"LightGBM", "RandomForestRegressor":"Random Forest", "RandomForestClassifier":"Random Forest", "Ridge":"Ridge", "GaussianHMM":"HMM", "HiddenMarkovModel":"HMM"}
                    if name in model_map:
                        models.add(model_map[name])
                        model_parameters[name] = {kw.arg: ast.unparse(kw.value)[:200] for kw in node.keywords if kw.arg}
                    val_map = {"TimeSeriesSplit":"Time Series Split", "PurgedKFold":"Purged K-Fold", "CombinatorialPurgedCV":"CPCV", "walk_forward":"Walk Forward", "walk_forward_validation":"Walk Forward"}
                    if name in val_map: validation.add(val_map[name])
        except SyntaxError:
            pass
        if re.search(r"(walk.?forward|time.?series.?split|purged|embargo|cross.?val|validation)", low): validation.add("Validation")
        if re.search(r"(backtest|sharpe|drawdown|slippage|transaction.?cost|equity)", low): backtest.add("Backtest")
        for metric in ("sharpe", "return", "drawdown", "sortino", "win_rate", "calmar"):
            if metric in low: metrics.add(metric)
        if re.search(r"scaler\.fit_transform\s*\(\s*(df|x|data)\s*\)", low):
            warnings.append({"severity":"warning", "code":"POTENTIAL_SCALER_LEAKAGE", "detail":f"Cell {idx}: scaler may be fit before the train split."})
        if re.search(r"train_test_split\s*\([^\n]*shuffle\s*=\s*true", low):
            warnings.append({"severity":"warning", "code":"RANDOM_SPLIT", "detail":f"Cell {idx}: shuffle=True may break time-series ordering."})
    if not any(v in validation for v in {"Walk Forward", "Time Series Split", "Purged K-Fold", "CPCV", "Validation"}):
        warnings.append({"severity":"info", "code":"NO_TIME_VALIDATION", "detail":"No time-series validation method detected."})
    if not backtest:
        warnings.append({"severity":"info", "code":"NO_BACKTEST_COMPONENT", "detail":"No backtest or performance metric detected."})
    return {"datasets":sorted(datasets), "target": sorted(targets)[0] if targets else None,
            "features":sorted(features), "models":sorted(models), "model_parameters": model_parameters,
            "regime_model": "Gaussian HMM" if "HMM" in models else None,
            "validation":sorted(validation), "backtest":sorted(backtest), "metrics":sorted(metrics), "warnings":warnings}


def inspect_notebook(nb_bytes: bytes) -> dict[str, Any]:
    """
    Run static analysis on a raw .ipynb file.
    Returns a dict with:
        compatible: bool
        python_version: str | None
        parameter_cell_found: bool
        imports: list[str]
        issues: list[{severity, code, detail}]
        cells_inspected: int
    """
    issues: list[dict[str, str]] = []
    all_imports: set[str] = set()

    try:
        nb = json.loads(nb_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {
            "compatible": False,
            "python_version": None,
            "parameter_cell_found": False,
            "imports": [],
            "issues": [{"severity": "critical", "code": "PARSE_ERROR", "detail": str(exc)}],
            "cells_inspected": 0,
        }

    python_version = nb.get("metadata", {}).get("kernelspec", {}).get("language_info", {}).get("version") \
        or nb.get("metadata", {}).get("language_info", {}).get("version")
    if not python_version:
        python_version = nb.get("metadata", {}).get("kernelspec", {}).get("display_name", "")

    parameter_cell_found = _has_parameter_tag(nb)
    if not parameter_cell_found:
        issues.append({"severity": "warning", "code": "NO_PARAMETER_CELL",
                       "detail": "No cell with 'parameters' tag found. Papermill cannot inject parameters."})

    cells = _cell_sources(nb)

    for idx, ctype, source in cells:
        if not source.strip():
            continue

        # Shell commands
        if ctype == "code":
            all_imports |= _extract_imports(source)

            for line in source.splitlines():
                stripped = line.strip()
                # pip install
                if re.match(r"^!.*pip\s+install", stripped, re.IGNORECASE):
                    issues.append({"severity": "warning", "code": "INLINE_PIP_INSTALL",
                                   "detail": f"Cell {idx}: {stripped[:120]}"})
                # apt install
                if re.match(r"^!.*apt(-get)?\s+install", stripped, re.IGNORECASE):
                    issues.append({"severity": "warning", "code": "INLINE_APT_INSTALL",
                                   "detail": f"Cell {idx}: {stripped[:120]}"})

            # Secret patterns
            for pat in _SECRET_PATTERNS:
                m = pat.search(source)
                if m:
                    issues.append({"severity": "critical", "code": "POSSIBLE_SECRET",
                                   "detail": f"Cell {idx}: possible hard-coded secret"})
                    break

            # Network patterns
            for pat in _NETWORK_PATTERNS:
                if pat.search(source):
                    issues.append({"severity": "warning", "code": "EXTERNAL_NETWORK_DETECTED",
                                   "detail": f"Cell {idx}: external network call detected"})
                    break

            # Hardcoded paths
            for pat in _PATH_PATTERNS:
                if pat.search(source):
                    issues.append({"severity": "warning", "code": "HARDCODED_PATH",
                                   "detail": f"Cell {idx}: hardcoded filesystem path"})
                    break

    unknown_imports = sorted(all_imports - QUANT_ENV_PACKAGES - {"__future__", ""})
    if unknown_imports:
        issues.append({"severity": "info", "code": "UNKNOWN_IMPORTS",
                       "detail": f"Not in quant env: {', '.join(unknown_imports[:15])}"})

    # Severity ranking
    sev_rank = {"critical": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda i: sev_rank.get(i["severity"], 99))

    critical = any(i["severity"] == "critical" for i in issues)
    compatible = not critical and parameter_cell_found

    analysis = _static_analysis(cells)
    issues.extend(analysis["warnings"])
    issues.sort(key=lambda i: sev_rank.get(i["severity"], 99))
    return {
        "compatible": compatible,
        "python_version": python_version or "unknown",
        "parameter_cell_found": parameter_cell_found,
        "imports": sorted(all_imports - {"", "__future__"}),
        "issues": issues,
        "cells_inspected": len(cells),
        "analysis": analysis,
    }
