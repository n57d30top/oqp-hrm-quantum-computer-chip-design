"""Update the public report index and machine-readable checksum manifest."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_INDEX = ROOT / "reports" / "node-alpha" / "report-index.json"
HASH_MANIFEST = ROOT / "ARTIFACTS.sha256"

PUBLIC_PATTERNS = [
    ".github/workflows/ci.yml",
    ".devcontainer/devcontainer.json",
    "Dockerfile",
    "Makefile",
    "README.md",
    "licence.md",
    "LICENSE-CODE.md",
    "COMMERCIAL-LICENSING.md",
    "VALIDATION_ROADMAP.md",
    "requirements-lock.txt",
    "pyproject.toml",
    "architecture/*.md",
    "docs/*.md",
    "docs/*.json",
    "hardware/*.yaml",
    "hardware/*.json",
    "oqp/*.py",
    "tests/*.py",
    "tools/*.py",
    "reports/node-alpha/deep-hardening-v3-20260502/*",
    "reports/node-alpha/qc-path/*.json",
]

PUBLIC_INDEX_EXCLUDES = {
    "reports/node-alpha/report-index.json",
    "ARTIFACTS.md",
    "ARTIFACTS.sha256",
}

HASH_PATTERNS = [
    "reports/node-alpha/deep-hardening-v3-20260502/*",
    "reports/node-alpha/qc-path/*.json",
    "reports/node-alpha/report-index.json",
]

KIND_BY_SUFFIX = {
    ".json": "json",
    ".md": "markdown",
    ".py": "python",
    ".toml": "toml",
    ".txt": "text",
    ".yaml": "yaml",
    ".yml": "yaml",
}


def main() -> None:
    artifacts = [_artifact_entry(path) for path in _public_paths()]
    index = {
        "schemaVersion": "open-quantum.public-report-index.v1",
        "generatedAt": _now(),
        "claimBoundary": (
            "Public simulation-only reproducibility index. No foundry, hardware, "
            "DRC/LVS, tapeout, prototype, or commercial-product readiness is claimed."
        ),
        "summary": {
            "publicArtifactCount": len(artifacts),
            "missingPublicArtifactCount": 0,
            "hashManifestPath": "ARTIFACTS.sha256",
            "hashManifestDescribedIn": "ARTIFACTS.md",
            "simulatorIncluded": True,
            "testsIncluded": True,
            "ciWorkflowIncluded": (ROOT / ".github" / "workflows" / "ci.yml").exists(),
            "deepHardeningV3Included": True,
            "foundryCalibratedSparametersReady": False,
            "hardwareMeasured": False,
            "drcRun": False,
            "lvsRun": False,
            "tapeoutReady": False,
            "prototypeReady": False,
            "excludedPublicEvidence": [
                "full value-upgrade folder",
                "no-budget generated package folder",
                "generic GDS path and audit outputs",
                "lab/demo notebooks",
                "full private QC-path working directories and mission sweeps",
                "graphify outputs and local caches",
                "private partner materials",
            ],
        },
        "artifacts": artifacts,
    }
    REPORT_INDEX.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    HASH_MANIFEST.write_text(_hash_manifest_text(), encoding="utf-8")


def _public_paths() -> list[Path]:
    paths: set[Path] = set()
    for pattern in PUBLIC_PATTERNS:
        for path in ROOT.glob(pattern):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel not in PUBLIC_INDEX_EXCLUDES:
                paths.add(path)
    return sorted(paths, key=lambda path: path.relative_to(ROOT).as_posix())


def _artifact_entry(path: Path) -> dict[str, Any]:
    rel = path.relative_to(ROOT).as_posix()
    entry: dict[str, Any] = {
        "path": rel,
        "exists": True,
        "kind": KIND_BY_SUFFIX.get(path.suffix, path.suffix.lstrip(".") or "file"),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }
    if path.suffix == ".json":
        summary = _json_summary(path)
        if summary:
            entry["summary"] = summary
    return entry


def _json_summary(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    summary: dict[str, Any] = {}
    if "schemaVersion" in data:
        summary["schemaVersion"] = data["schemaVersion"]
    if isinstance(data.get("summary"), dict):
        for key, value in data["summary"].items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                summary[key] = value
    for key in [
        "prototypeReady",
        "tapeoutReady",
        "hardwareMeasured",
        "foundrySparametersReady",
        "deepHardeningScore",
        "internalConsistencyPassed",
        "maxScaledPhysicalModes",
        "maxScaledLogicalDualRailQubits",
    ]:
        if key in data and key not in summary:
            summary[key] = data[key]
    return summary


def _hash_manifest_text() -> str:
    paths: set[Path] = set()
    for pattern in HASH_PATTERNS:
        for path in ROOT.glob(pattern):
            if path.is_file():
                paths.add(path)
    lines = [
        f"{_sha256(path)}  {path.relative_to(ROOT).as_posix()}"
        for path in sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix())
    ]
    return "\n".join(lines) + "\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    main()
