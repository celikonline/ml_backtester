"""
RegimeLab Notebook Migrator & Sanitizer.

Converts legacy unconstrained notebooks (such as Colab/Jupyter notebooks)
into RegimeLab-compatible, reproducible, parameterized research notebooks.

Performs:
1. Injects a 'parameters' tagged cell with standard RegimeLab contract variables
2. Comments out runtime `!pip install` and `!apt install` invocations
3. Replaces hardcoded secrets (e.g. FRED_API_KEY) with environment injections
4. Replaces hardcoded storage paths (e.g. SAVE_DIR) with ARTIFACT_DIR
5. Injects RegimeLab SDK metrics & artifact logging hooks
"""
import copy
import json
import re
from pathlib import Path
from typing import Any


PARAMETER_CELL_SOURCE = [
    "# [REGIMELAB] Parameterized Contract Cell (Papermill)\n",
    "import os\n",
    "from pathlib import Path\n",
    "\n",
    "WORKSPACE_ID = ''\n",
    "EXPERIMENT_ID = ''\n",
    "DATASET_SNAPSHOT_ID = ''\n",
    "INPUT_DIR = ''\n",
    "ARTIFACT_DIR = os.environ.get('ARTIFACT_DIR', './artifacts')\n",
    "RUN_ID = os.environ.get('RUN_ID', 'local')\n",
    "FRED_API_KEY = os.environ.get('FRED_API_KEY', '')\n",
    "DATA_MODE = 'snapshot'\n",
    "Path(ARTIFACT_DIR).mkdir(parents=True, exist_ok=True)\n",
]

SDK_HOOK_CELL_SOURCE = [
    "# [REGIMELAB] Post-Execution Metrics & Artifact Manifest Hook\n",
    "try:\n",
    "    from regimelab_sdk import run\n",
    "    run.log_message('RegimeLab notebook run finished successfully.')\n",
    "    # Register any generated tables or curves in ARTIFACT_DIR\n",
    "    for p in Path(ARTIFACT_DIR).glob('*.csv'):\n",
    "        run.log_artifact(p)\n",
    "    for p in Path(ARTIFACT_DIR).glob('*.png'):\n",
    "        run.log_artifact(p)\n",
    "except Exception as _sdk_err:\n",
    "    print(f'[RegimeLab SDK Hook Warning]: {_sdk_err}')\n",
]


def sanitize_notebook(nb_dict: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """
    Sanitize and adapt a notebook dictionary for RegimeLab.
    Returns (sanitized_nb, list_of_changes).
    """
    nb = copy.deepcopy(nb_dict)
    changes = []

    cells = nb.get("cells", [])

    # 1. Check if a parameter cell exists
    has_params = False
    for cell in cells:
        tags = cell.get("metadata", {}).get("tags", [])
        if "parameters" in tags:
            has_params = True
            break

    # If missing, prepend parameter cell
    if not has_params:
        param_cell = {
            "cell_type": "code",
            "metadata": {
                "tags": ["parameters"],
                "regimelab_injected": True,
            },
            "source": list(PARAMETER_CELL_SOURCE),
            "outputs": [],
            "execution_count": None,
        }
        cells.insert(0, param_cell)
        changes.append("Injected standard RegimeLab 'parameters' tagged cell at index 0.")

    # 2. Iterate and sanitize cells
    for idx, cell in enumerate(cells):
        if cell.get("cell_type") != "code":
            continue

        raw_source = cell.get("source", [])
        if isinstance(raw_source, str):
            lines = raw_source.splitlines(keepends=True)
        else:
            lines = list(raw_source)

        new_lines = []
        cell_modified = False

        for line in lines:
            stripped = line.strip()

            # A) Disable inline pip/apt installs
            if re.match(r"^!.*pip\s+install", stripped, re.IGNORECASE):
                new_lines.append(f"# [REGIMELAB: DISABLED_INLINE_INSTALL] {line}")
                changes.append(f"Cell {idx}: Disabled inline pip install: {stripped[:60]}")
                cell_modified = True
            elif re.match(r"^!.*apt(-get)?\s+install", stripped, re.IGNORECASE):
                new_lines.append(f"# [REGIMELAB: DISABLED_INLINE_INSTALL] {line}")
                changes.append(f"Cell {idx}: Disabled inline apt install: {stripped[:60]}")
                cell_modified = True

            # B) Replace hardcoded FRED API Key assignments
            elif re.match(r'^FRED_API_KEY\s*=\s*["\'][a-zA-Z0-9]{16,}["\']', stripped):
                new_lines.append(
                    "# [REGIMELAB: SANITIZED_SECRET]\n"
                    "FRED_API_KEY = os.environ.get('FRED_API_KEY', FRED_API_KEY or '')\n"
                )
                changes.append(f"Cell {idx}: Sanitized hardcoded FRED_API_KEY to read from environment.")
                cell_modified = True

            # C) Replace hardcoded Google Drive or absolute Colab SAVE_DIR
            elif re.match(r'^SAVE_DIR\s*=\s*["\'](/content/|C:\\\\|D:\\\\)', stripped, re.IGNORECASE):
                new_lines.append(
                    "# [REGIMELAB: ADAPTED_ARTIFACT_PATH]\n"
                    "SAVE_DIR = ARTIFACT_DIR\n"
                )
                changes.append(f"Cell {idx}: Adapted SAVE_DIR to use ARTIFACT_DIR.")
                cell_modified = True

            else:
                new_lines.append(line)

        if cell_modified:
            cell["source"] = new_lines

    # 3. Add SDK hook cell at the end if not already present
    has_sdk_hook = any(
        cell.get("metadata", {}).get("regimelab_hook") for cell in cells
    )
    if not has_sdk_hook:
        sdk_cell = {
            "cell_type": "code",
            "metadata": {
                "tags": ["regimelab_hook"],
                "regimelab_hook": True,
            },
            "source": list(SDK_HOOK_CELL_SOURCE),
            "outputs": [],
            "execution_count": None,
        }
        cells.append(sdk_cell)
        changes.append("Appended RegimeLab SDK artifact & metric logging hook at notebook end.")

    nb["cells"] = cells
    return nb, changes


def migrate_notebook_file(src_path: Path, dest_path: Path) -> list[str]:
    """Read a notebook from src_path, sanitize it, and save to dest_path."""
    raw_content = src_path.read_text(encoding="utf-8")
    nb_dict = json.loads(raw_content)
    sanitized, changes = sanitize_notebook(nb_dict)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(json.dumps(sanitized, indent=1, ensure_ascii=False), encoding="utf-8")
    return changes


if __name__ == "__main__":
    import sys
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tezmodelfinal (1).ipynb")
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("tezmodelfinal_regimelab.ipynb")
    print(f"Migrating {src} -> {dst}...")
    log = migrate_notebook_file(src, dst)
    print(f"Migration completed with {len(log)} changes:")
    for entry in log:
        print(f" - {entry}")
