"""
Notebook Lab — Artifact Collector.

After notebook execution, scans ARTIFACT_DIR and registers
all files as run artifacts in the database.
"""
import hashlib
import mimetypes
import os
from pathlib import Path


# Maximum artifact size (100 MB per file by default)
MAX_ARTIFACT_SIZE_BYTES = int(os.environ.get("REGIMELAB_MAX_ARTIFACT_MB", "100")) * 1024 * 1024

# Maximum number of artifacts per run
MAX_ARTIFACT_COUNT = int(os.environ.get("REGIMELAB_MAX_ARTIFACT_COUNT", "200"))


def collect_artifacts(artifact_dir: Path) -> list[dict]:
    """
    Recursively scan artifact_dir and return a list of artifact descriptors.

    Returns [
        {
            name: str           — relative path from artifact_dir
            size_bytes: int
            sha256: str
            content_type: str
            path: str           — absolute path
        }
    ]
    """
    artifacts = []

    if not artifact_dir.exists():
        return artifacts

    for path in sorted(artifact_dir.rglob("*")):
        if not path.is_file():
            continue
        # Skip internal files
        if path.name in {"nb_params.json"}:
            continue
        if path.suffix == ".tmp":
            continue

        size = path.stat().st_size
        if size > MAX_ARTIFACT_SIZE_BYTES:
            continue  # silently skip oversized files

        if len(artifacts) >= MAX_ARTIFACT_COUNT:
            break

        try:
            raw = path.read_bytes()
            sha256 = hashlib.sha256(raw).hexdigest()
        except OSError:
            continue

        rel = str(path.relative_to(artifact_dir)).replace("\\", "/")
        content_type, _ = mimetypes.guess_type(str(path))

        artifacts.append({
            "name": rel,
            "size_bytes": size,
            "sha256": sha256,
            "content_type": content_type or "application/octet-stream",
            "path": str(path),
        })

    return artifacts


def artifact_summary(artifacts: list[dict]) -> dict:
    return {
        "count": len(artifacts),
        "total_bytes": sum(a["size_bytes"] for a in artifacts),
        "types": sorted({a["content_type"] for a in artifacts}),
    }
