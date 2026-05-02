"""Aggregate Node Alpha continuation calculations into one report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .blueprint import Blueprint


def generate_node_alpha_compute_report(
    blueprint: Blueprint,
    *,
    device_sweep_path: str | Path,
    threshold_sweep_path: str | Path,
    resource_sweep_path: str | Path,
    closure_path: str | Path = "reports/node-alpha/qc-path/node-alpha-closure.json",
) -> dict[str, Any]:
    device = _read_json(Path(device_sweep_path))
    threshold = _read_json(Path(threshold_sweep_path))
    resources = _read_json(Path(resource_sweep_path))
    closure = _read_json(Path(closure_path))
    return {
        "schemaVersion": "open-quantum.node-alpha-compute-report.v1",
        "sourcePath": blueprint.source_path,
        "scope": {
            "node": "node-alpha",
            "claim": "extended_simulation_and_analytical_ranking",
            "simulatedOnly": True,
            "notEvidenceFor": [
                "foundry-calibrated S-parameters",
                "foundry PDK readiness",
                "DRC/LVS signoff",
                "hardware readiness",
                "fault-tolerant logical qubits",
                "experimental primitive demonstration",
            ],
        },
        "artifacts": {
            "deviceSweep": str(device_sweep_path),
            "thresholdSweep": str(threshold_sweep_path),
            "resourceSweep": str(resource_sweep_path),
            "nodeAlphaClosure": str(closure_path),
        },
        "deviceSweep": _device_summary(device),
        "thresholdSweep": _threshold_summary(threshold),
        "resourceSweep": _resource_summary(resources),
        "readinessImpact": {
            "nodeAlphaMaxed": _flag(closure, "node_alpha_maxed_without_realworld_input"),
            "prototypeReady": _flag(closure, "prototype_ready"),
            "completeQuantumComputer": _flag(closure, "complete_quantum_computer"),
            "hardStopsRequiringRealWorldInput": closure.get("hardStopsRequiringRealWorldInput", []),
        },
        "summary": {
            "deviceRunCount": device.get("runCount", 0),
            "thresholdRunCount": threshold.get("runCount", 0),
            "resourceRunCount": resources.get("runCount", 0),
            "bestDeviceSweepStatus": device.get("status"),
            "thresholdStatus": threshold.get("status"),
            "nodeAlphaStatus": (closure.get("summary") or {}).get("status"),
        },
    }


def _device_summary(report: dict[str, Any]) -> dict[str, Any]:
    per_device = report.get("perDeviceChampions", {})
    gaps = report.get("perDeviceGapToAcceptance", {})
    return {
        "status": report.get("status"),
        "runCount": report.get("runCount"),
        "validationTier": report.get("validationTier"),
        "champion": _candidate_summary(report.get("champion")),
        "gapSummary": report.get("gapSummary"),
        "perDeviceBestCandidates": {
            device: {
                "candidate": _candidate_summary(candidate),
                "gapToAcceptance": gaps.get(device),
            }
            for device, candidate in per_device.items()
        },
    }


def _candidate_summary(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if not candidate:
        return None
    metrics = candidate.get("fdtdMetrics", {})
    return {
        "candidateId": candidate.get("candidateId"),
        "device": candidate.get("device"),
        "backend": candidate.get("backend"),
        "physicalValidationLevel": candidate.get("physicalValidationLevel"),
        "sourceModel": candidate.get("sourceModel"),
        "acceptanceStatus": candidate.get("acceptanceStatus"),
        "score": candidate.get("score"),
        "metrics": {
            "usefulTransmission": metrics.get("usefulTransmission"),
            "insertionLossDb": metrics.get("insertionLossDb"),
            "reflectionRatio": metrics.get("reflectionRatio"),
            "crosstalkRatio": metrics.get("crosstalkRatio"),
            "normalizationReliable": metrics.get("normalizationReliable"),
        },
    }


def _threshold_summary(report: dict[str, Any]) -> dict[str, Any]:
    champion = report.get("champion") or {}
    return {
        "status": report.get("status"),
        "runCount": report.get("runCount"),
        "acceptedCandidateCount": len(report.get("acceptedCandidates", [])),
        "champion": {
            "candidateId": champion.get("candidateId"),
            "belowThreshold": champion.get("belowThreshold"),
            "effectivePhysicalErrorRate": champion.get("effectivePhysicalErrorRate"),
            "estimatedLogicalErrorRatePerCycle": champion.get("estimatedLogicalErrorRatePerCycle"),
            "score": champion.get("score"),
        },
        "deviceEvidence": report.get("deviceEvidence"),
        "blockers": report.get("blockers", []),
    }


def _resource_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "runCount": report.get("runCount"),
        "summary": report.get("summary"),
        "logicalQubitValues": report.get("logicalQubitValues"),
        "targetLogicalErrorRates": report.get("targetLogicalErrorRates"),
        "limitations": report.get("limitations", []),
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _flag(report: dict[str, Any], name: str) -> bool:
    flags = report.get("readinessFlags")
    return bool(isinstance(flags, dict) and flags.get(name) is True)
