"""Report writers for OQP-HRM runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_report(report: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def format_text_report(report: dict[str, Any]) -> str:
    spatial = report["spatialModel"]
    metrics = report["observedMetrics"]
    lines = [
        "=== OQP-HRM Validation Report ===",
        f"Backend: {report['backend']}",
        f"Topology: {report['topologyClass']}",
        f"Modes: {spatial['waveguideCount']}",
        f"Interferometers: {spatial['interferometerCount']}",
        f"Pairing stride: {spatial['pairingStride']}",
        f"Connected components: {spatial['modeGraphConnectedComponents']}",
        f"Heralding yield: {metrics['reconstructedAverageHeraldingYieldPercent']:.1f}%",
        (
            "Total mesh path loss from attenuation score: "
            f"{metrics['totalMeshPathLossFromAttenuationScoreDb']:.3f} dB"
        ),
        (
            "Total mesh path loss from heralding yield: "
            f"{metrics['totalMeshPathLossFromHeraldingYieldDb']:.3f} dB"
        ),
        (
            "Effective per-stage/component loss: "
            f"{metrics['effectivePerStageComponentLossDb']:.3f} dB "
            f"({metrics['effectivePerStageComponentLossPercent']:.2f}%)"
        ),
        f"Architecture score: {metrics['architectureScore']:.3f}",
    ]
    if report["warnings"]:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in report["warnings"])
    return "\n".join(lines)
