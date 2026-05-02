"""Resource scaling sweeps for OQP-HRM Node Alpha studies."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .blueprint import Blueprint
from .report import write_json_report
from .resource_model import generate_resource_model


def run_resource_sweep(
    blueprint: Blueprint,
    *,
    encoding: str = "dual_rail",
    logical_qubits: list[int] | None = None,
    target_logical_error_rates: list[float] | None = None,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    logical_qubits = logical_qubits or [2, 4, 8, 18, 36]
    target_logical_error_rates = target_logical_error_rates or [1e-3, 1e-6]
    results = []
    for logical in logical_qubits:
        for target in target_logical_error_rates:
            report = generate_resource_model(
                blueprint,
                encoding=encoding,
                logical_qubits=logical,
                target_logical_error_rate=target,
            )
            result = {
                "candidateId": f"{encoding}_lq{logical}_target{target:g}".replace(".", "p"),
                "encoding": encoding,
                "logicalQubits": logical,
                "targetLogicalErrorRate": target,
                "physicalModes": report["physicalModes"],
                "singlePhotonSources": report["requiredNonGaussianResources"]["singlePhotonSources"]["count"],
                "pnrDetectors": report["requiredNonGaussianResources"]["pnrDetectors"]["count"],
                "ancillaModesPerCycle": report["requiredNonGaussianResources"]["ancillaFactory"]["ancillaModesPerCycle"],
                "minimumParallelSourceBanks": report["requiredNonGaussianResources"]["multiplexing"]["minimumParallelSourceBanks"],
                "resourceModel": report,
            }
            results.append(result)
            if out_dir:
                write_json_report(result, Path(out_dir) / f"{result['candidateId']}.json")
    summary = {
        "schemaVersion": "open-quantum.resource-sweep.v1",
        "sourcePath": blueprint.source_path,
        "encoding": encoding,
        "runCount": len(results),
        "logicalQubitValues": logical_qubits,
        "targetLogicalErrorRates": target_logical_error_rates,
        "results": results,
        "summary": {
            "minLogicalQubits": min(logical_qubits) if logical_qubits else 0,
            "maxLogicalQubits": max(logical_qubits) if logical_qubits else 0,
            "maxSinglePhotonSources": max((item["singlePhotonSources"] for item in results), default=0),
            "maxPnrDetectors": max((item["pnrDetectors"] for item in results), default=0),
            "maxAncillaModesPerCycle": max((item["ancillaModesPerCycle"] for item in results), default=0),
            "maxMinimumParallelSourceBanks": max((item["minimumParallelSourceBanks"] for item in results), default=0),
        },
        "limitations": [
            "Resource scaling is analytical and topology-level only.",
            "Counts are not validated against a foundry package, source bank, or detector readout implementation.",
            "Use as Node Alpha sizing guidance, not as hardware procurement evidence.",
        ],
    }
    if out_dir:
        write_json_report(summary, Path(out_dir) / "resource-sweep.json")
    return summary
