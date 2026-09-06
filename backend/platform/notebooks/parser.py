"""Safe, read-only parser for Notebook Lab viewer responses."""
from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path
from typing import Any

_MAX_TEXT = 100_000
_MAX_IMAGE = 8 * 1024 * 1024
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_STRIP_HTML = re.compile(r"<\s*/?\s*(script|style|iframe|object|embed|form|meta|link)[^>]*>", re.I)
_EVENT_ATTR = re.compile(r"\s+on[a-z]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
_JS_URL = re.compile(r"(href|src)\s*=\s*(['\"])\s*javascript:[^'\"]*\2", re.I)


def _text(value: Any) -> str:
    if isinstance(value, list):
        return "".join(str(x) for x in value)
    return "" if value is None else str(value)


def _clip(value: str, limit: int = _MAX_TEXT) -> str:
    return value if len(value) <= limit else value[:limit] + "\n… [çıktı kısaltıldı]"


def sanitize_html(value: str) -> str:
    """Remove executable/embedded HTML while preserving simple tables/markup."""
    cleaned = _STRIP_HTML.sub("", value)
    cleaned = _EVENT_ATTR.sub("", cleaned)
    return _JS_URL.sub(r"\1=\2#\2", cleaned)


def _output(output: dict[str, Any]) -> dict[str, Any]:
    kind = str(output.get("output_type") or "")
    result: dict[str, Any] = {"output_type": kind}
    if "execution_count" in output:
        result["execution_count"] = output.get("execution_count")
    if kind == "error":
        result["ename"] = _clip(_text(output.get("ename")), 500)
        result["evalue"] = _clip(_text(output.get("evalue")), 2_000)
        result["traceback"] = [_clip(_text(v), 4_000) for v in (output.get("traceback") or [])]
        return result
    data = output.get("data") or {}
    if "text/plain" in data:
        result["text"] = _clip(_text(data["text/plain"]))
    elif "text" in output:
        result["text"] = _clip(_text(output.get("text")))
    if "text/html" in data:
        result["html"] = sanitize_html(_clip(_text(data["text/html"])))
    for mime in ("image/png", "image/jpeg"):
        if mime in data:
            raw = _text(data[mime]).replace("\n", "")
            try:
                decoded = base64.b64decode(raw, validate=True)
                if len(decoded) <= _MAX_IMAGE:
                    result["image"] = {"mime": mime, "base64": base64.b64encode(decoded).decode("ascii")}
            except (ValueError, TypeError):
                result["image_error"] = "Geçersiz görsel çıktısı"
            break
    if "application/json" in data:
        result["json"] = data["application/json"]
    return result


def _classify(cell_type: str, source: str) -> str:
    if cell_type == "markdown":
        return "OTHER"
    low = source.lower()
    if re.search(r"(read_csv|read_parquet|dukascopy|fred|yfinance|\.csv|\.parquet)", low):
        return "DATA"
    if re.search(r"(feature|transform|scaler|rolling|rsi|macd|momentum|volatility|pct_change)", low):
        return "FEATURE"
    if re.search(r"(xgb|lightgbm|randomforest|ridge\s*\(|hmm|lstm|tft|model)", low):
        return "MODEL"
    if re.search(r"(walk.?forward|time.?series.?split|purged|embargo|cross.?val|validation)", low):
        return "VALIDATION"
    if re.search(r"(backtest|sharpe|drawdown|slippage|transaction.?cost|equity)", low):
        return "BACKTEST"
    if re.search(r"(plot|chart|heatmap|\.show\s*\(|matplotlib|seaborn)", low):
        return "PLOT"
    return "OTHER"


def parse_notebook_bytes(raw: bytes) -> dict[str, Any]:
    try:
        notebook = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Geçersiz notebook JSON dosyası.") from exc
    if not isinstance(notebook, dict) or not isinstance(notebook.get("cells"), list):
        raise ValueError("Notebook cells listesi bulunamadı.")
    cells = []
    outline = []
    counts = {"code": 0, "markdown": 0, "raw": 0, "outputs": 0}
    for index, cell in enumerate(notebook["cells"]):
        if not isinstance(cell, dict):
            continue
        cell_type = str(cell.get("cell_type") or "raw")
        if cell_type not in {"code", "markdown", "raw"}:
            cell_type = "raw"
        source = _clip(_text(cell.get("source")))
        outputs = [_output(o) for o in (cell.get("outputs") or []) if isinstance(o, dict)]
        counts[cell_type] += 1
        counts["outputs"] += len(outputs)
        item = {
            "cell_id": str(cell.get("id") or f"cell-{index + 1:03d}"),
            "index": index,
            "cell_type": cell_type,
            "classification": _classify(cell_type, source),
            "execution_count": cell.get("execution_count"),
            "source": source,
            "outputs": outputs,
            "tags": list((cell.get("metadata") or {}).get("tags") or []),
        }
        cells.append(item)
        if cell_type == "markdown":
            for line in source.splitlines():
                match = _HEADING.match(line)
                if match:
                    outline.append({"cell_index": index, "level": len(match.group(1)), "title": match.group(2)})
                    break
    return {"cells": cells, "outline": outline, "statistics": {"total_cells": len(cells), **counts}}


def parse_notebook_file(path: str | Path) -> dict[str, Any]:
    return parse_notebook_bytes(Path(path).read_bytes())
