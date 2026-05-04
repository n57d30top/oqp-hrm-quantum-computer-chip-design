"""End-to-end simulation audit for the OQP-HRM quantum-computer design."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .blueprint import Blueprint
from .compiler import compile_blueprint, runtime_trace
from .design_dossier import generate_design_dossier
from .encoding import generate_encoding_spec
from .error_budget import generate_error_budget
from .error_correction import generate_error_correction_plan
from .metrics import architecture_score, loss_fraction_to_db, per_stage_loss, transmission_to_db
from .node_alpha import generate_node_alpha_closure
from .node_alpha_compute import generate_node_alpha_compute_report
from .primitive import generate_fusion_primitive, generate_primitive_spec
from .resource_model import generate_resource_model
from .topology import connected_component_count, mzi_pairs


def run_complete_simulation(
    blueprint: Blueprint,
    *,
    artifact_root: str | Path = "reports/node-alpha",
    device_sweep_path: str | Path | None = None,
    threshold_sweep_path: str | Path | None = None,
    resource_sweep_path: str | Path | None = None,
    compute_report_path: str | Path | None = None,
    closure_path: str | Path | None = None,
    design_dossier_path: str | Path | None = None,
    encoding: str = "dual_rail",
    primitive: str = "fusion_entangling",
    shots: int = 1000,
    feed_forward_latency_ns: float = 5.0,
    target_logical_error_rate: float = 1e-6,
) -> dict[str, Any]:
    """Run the complete simulation stack that is possible without real-world inputs."""

    root = Path(artifact_root)
    qc = root / "qc-path"
    device_path = Path(device_sweep_path) if device_sweep_path else _latest_report(
        qc, "device-sweep-node-alpha-extended-*", "device-sweep.json", qc / "device-sweep.json"
    )
    threshold_path = Path(threshold_sweep_path) if threshold_sweep_path else _latest_report(
        qc, "threshold-sweep-node-alpha-extended-*", "threshold-sweep.json", qc / "threshold-sweep.json"
    )
    resource_path = Path(resource_sweep_path) if resource_sweep_path else _latest_report(
        qc, "resource-sweep-node-alpha-extended-*", "resource-sweep.json", qc / "resource-sweep.json"
    )
    closure_report_path = Path(closure_path) if closure_path else qc / "node-alpha-closure.json"
    dossier_path = Path(design_dossier_path) if design_dossier_path else qc / "complete-design-dossier.json"
    compute_path = Path(compute_report_path) if compute_report_path else qc / "node-alpha-compute-report-20260502.json"

    topology = _run_topology_simulation(blueprint)
    encoding_report = generate_encoding_spec(blueprint, encoding=encoding)
    primitive_spec = generate_primitive_spec(blueprint, encoding=encoding, primitive=primitive)
    resource_model = generate_resource_model(
        blueprint,
        encoding=encoding,
        target_logical_error_rate=target_logical_error_rate,
    )
    compiled = compile_blueprint(blueprint, shots=shots, encoding=encoding)
    runtime = runtime_trace(compiled, feed_forward_latency_ns=feed_forward_latency_ns)
    error_budget = generate_error_budget(blueprint, feed_forward_latency_ns=feed_forward_latency_ns)
    error_correction = generate_error_correction_plan(
        blueprint,
        physical_error_rate=_estimated_physical_error_rate(error_budget),
    )

    device_sweep = _read_json(device_path)
    threshold_sweep = _read_json(threshold_path)
    resource_sweep = _read_json(resource_path)
    closure = _read_json(closure_report_path) or generate_node_alpha_closure(
        blueprint,
        artifact_root=root,
    )
    dossier = _read_json(dossier_path) or generate_design_dossier(
        blueprint,
        artifact_root=root,
        encoding=encoding,
        primitive=primitive,
        shots=shots,
        feed_forward_latency_ns=feed_forward_latency_ns,
        target_logical_error_rate=target_logical_error_rate,
    )
    compute = _read_json(compute_path)
    if not compute and device_sweep and threshold_sweep and resource_sweep:
        compute = generate_node_alpha_compute_report(
            blueprint,
            device_sweep_path=device_path,
            threshold_sweep_path=threshold_path,
            resource_sweep_path=resource_path,
            closure_path=closure_report_path,
        )

    fusion_device = _fusion_device_candidate(device_sweep)
    fusion = generate_fusion_primitive(
        blueprint,
        device_report=fusion_device,
        encoding=encoding,
        feed_forward_latency_ns=feed_forward_latency_ns,
    )
    layers = _simulation_layers(
        topology=topology,
        encoding_report=encoding_report,
        primitive_spec=primitive_spec,
        resource_model=resource_model,
        compiled=compiled,
        runtime=runtime,
        error_budget=error_budget,
        error_correction=error_correction,
        device_sweep=device_sweep,
        threshold_sweep=threshold_sweep,
        resource_sweep=resource_sweep,
        fusion=fusion,
        compute=compute,
        dossier=dossier,
        closure=closure,
    )
    checklist = _completion_checklist(
        artifact_paths={
            "deviceSweep": device_path,
            "thresholdSweep": threshold_path,
            "resourceSweep": resource_path,
            "computeReport": compute_path,
            "designDossier": dossier_path,
            "nodeAlphaClosure": closure_report_path,
        },
        layers=layers,
        device_sweep=device_sweep,
        threshold_sweep=threshold_sweep,
        fusion=fusion,
        closure=closure,
    )
    failed_simulation_gates = _failed_simulation_gates(
        device_sweep=device_sweep,
        threshold_sweep=threshold_sweep,
        fusion=fusion,
    )
    hard_stops = _hard_stops_requiring_real_world_input(closure)
    all_referenced_artifacts_complete = all(item["status"] == "complete" for item in checklist)
    flags = {
        "completeSimulationExecuted": True,
        "allReferencedSimulationArtifactsComplete": all_referenced_artifacts_complete,
        "topologyBackendFullyAvailable": topology["backendAvailable"],
        "allCoreDevicesPassSimulatedGates": _all_core_devices_accepted(device_sweep),
        "primitiveReadyInSimulation": fusion["readinessFlags"]["primitiveReady"],
        "belowThresholdCandidateFound": threshold_sweep.get("status") == "below_threshold_candidate_found",
        "nodeAlphaMaxed": _closure_flag(closure, "node_alpha_maxed_without_realworld_input"),
        "prototypeReady": _closure_flag(closure, "prototype_ready"),
        "realWorldPrototypeReady": _closure_flag(closure, "prototype_ready"),
        "simulatedQuantumComputerComplete": False,
    }
    flags["simulatedQuantumComputerComplete"] = all(
        flags[name]
        for name in (
            "allReferencedSimulationArtifactsComplete",
            "allCoreDevicesPassSimulatedGates",
            "primitiveReadyInSimulation",
            "belowThresholdCandidateFound",
        )
    )
    return {
        "schemaVersion": "open-quantum.complete-simulation.v1",
        "sourcePath": blueprint.source_path,
        "objective": "Complete Node Alpha simulation of the OQP-HRM quantum-computer design.",
        "scope": {
            "claim": "complete_available_node_alpha_simulation",
            "simulatedOnly": True,
            "usesSurrogatesWhenBackendsMissing": True,
            "notEvidenceFor": [
                "MEEP/FDTD completion when MEEP is unavailable",
                "Strawberry Fields Gaussian validation when numpy/strawberryfields are unavailable",
                "foundry-calibrated S-parameters",
                "foundry PDK readiness",
                "DRC/LVS signoff",
                "hardware readiness",
                "fault-tolerant logical qubits",
                "experimental primitive demonstration",
            ],
        },
        "artifacts": {
            "deviceSweep": _artifact(device_path, device_sweep),
            "thresholdSweep": _artifact(threshold_path, threshold_sweep),
            "resourceSweep": _artifact(resource_path, resource_sweep),
            "computeReport": _artifact(compute_path, compute),
            "designDossier": _artifact(dossier_path, dossier),
            "nodeAlphaClosure": _artifact(closure_report_path, closure),
        },
        "simulationLayers": layers,
        "completionAudit": {
            "objective": "Run the complete available simulation stack and bring simulation-only gates to a passing state.",
            "successCriteria": checklist,
            "missingOrFailedRequirements": [
                item for item in checklist if item["status"] != "complete"
            ],
        },
        "readinessFlags": flags,
        "failedReadinessGates": failed_simulation_gates,
        "hardStopsRequiringRealWorldInput": hard_stops,
        "summary": {
            "status": (
                "complete_simulation_passed"
                if flags["simulatedQuantumComputerComplete"]
                else "complete_simulation_executed_not_viable"
            ),
            "simulatedLayerCount": sum(1 for item in layers.values() if item["status"] == "complete"),
            "totalLayerCount": len(layers),
            "failedGateCount": len(failed_simulation_gates),
            "missingOrFailedRequirementCount": len(
                [item for item in checklist if item["status"] != "complete"]
            ),
            "realWorldHardStopCount": len(hard_stops),
            "deviceSweepRuns": device_sweep.get("runCount", 0),
            "thresholdSweepRuns": threshold_sweep.get("runCount", 0),
            "resourceSweepRuns": resource_sweep.get("runCount", 0),
            "conclusion": (
                (
                    "The available Node Alpha simulation stack passes its simulation-only gates. "
                    "This is not prototype, foundry, hardware, or lab readiness."
                )
                if flags["simulatedQuantumComputerComplete"]
                else (
                    "The available Node Alpha simulation stack has been executed, "
                    "but the design is not a complete simulated quantum computer because "
                    "core device, primitive, or threshold gates do not all close."
                )
            ),
        },
    }


def _run_topology_simulation(blueprint: Blueprint) -> dict[str, Any]:
    try:
        from .simulator_sf import simulate_blueprint

        report = simulate_blueprint(blueprint)
        return {
            "status": "complete",
            "backend": report.get("backend"),
            "backendAvailable": True,
            "physicalValidationLevel": "strawberryfields_gaussian",
            "report": _topology_summary(report),
        }
    except ModuleNotFoundError as exc:
        return _topology_surrogate(blueprint, exc)
    except Exception as exc:  # pragma: no cover - defensive runtime capture
        return _topology_surrogate(blueprint, exc)


def _topology_surrogate(blueprint: Blueprint, exc: BaseException) -> dict[str, Any]:
    spatial = blueprint.spatial_model
    metrics = blueprint.metrics
    pairs = mzi_pairs(
        spatial.waveguide_count,
        spatial.interferometer_count,
        spatial.pairing_stride,
    )
    component_count = connected_component_count(spatial.waveguide_count, pairs)
    total_loss_score_db = loss_fraction_to_db(metrics.attenuation_loss_score)
    stage_loss_db, stage_loss_fraction = per_stage_loss(
        total_loss_score_db,
        metrics.effective_component_stage_count,
    )
    score = architecture_score(
        heralding_yield=metrics.heralding_yield,
        total_loss_db=total_loss_score_db,
        connected_components=component_count,
        crosstalk_risk_score=metrics.crosstalk_risk_score,
        hop_latency_score=metrics.hop_latency_score,
    )
    return {
        "status": "complete",
        "backend": "analytical_topology_surrogate",
        "backendAvailable": False,
        "physicalValidationLevel": "node_alpha_surrogate_not_strawberryfields",
        "backendError": {
            "type": type(exc).__name__,
            "message": str(exc),
        },
        "report": {
            "schemaVersion": "open-quantum.photonic-validation-surrogate.v1",
            "spatialModel": {
                "waveguideCount": spatial.waveguide_count,
                "interferometerCount": spatial.interferometer_count,
                "pairingStride": spatial.pairing_stride,
                "modeGraphConnectedComponents": component_count,
                "mziPairCount": len(pairs),
            },
            "observedMetrics": {
                "heraldingYield": metrics.heralding_yield,
                "reconstructedAverageHeraldingYieldPercent": metrics.heralding_yield * 100,
                "attenuationLossScore": metrics.attenuation_loss_score,
                "totalMeshPathLossFromAttenuationScoreDb": total_loss_score_db,
                "totalMeshPathLossFromHeraldingYieldDb": transmission_to_db(metrics.heralding_yield),
                "effectiveStageCount": metrics.effective_component_stage_count,
                "effectivePerStageComponentLossDb": stage_loss_db,
                "effectivePerStageComponentLossPercent": stage_loss_fraction * 100,
                "crosstalkRiskScore": metrics.crosstalk_risk_score,
                "hopLatencyScore": metrics.hop_latency_score,
                "architectureScore": score,
            },
            "limitations": [
                "Analytical topology surrogate, not a Strawberry Fields Gaussian state simulation.",
                "Generated because the local Gaussian simulation backend is unavailable.",
            ],
        },
    }


def _topology_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": report.get("schemaVersion"),
        "backend": report.get("backend"),
        "spatialModel": report.get("spatialModel", {}),
        "observedMetrics": report.get("observedMetrics", {}),
        "warnings": report.get("warnings", []),
    }


def _simulation_layers(
    *,
    topology: dict[str, Any],
    encoding_report: dict[str, Any],
    primitive_spec: dict[str, Any],
    resource_model: dict[str, Any],
    compiled: dict[str, Any],
    runtime: dict[str, Any],
    error_budget: dict[str, Any],
    error_correction: dict[str, Any],
    device_sweep: dict[str, Any],
    threshold_sweep: dict[str, Any],
    resource_sweep: dict[str, Any],
    fusion: dict[str, Any],
    compute: dict[str, Any],
    dossier: dict[str, Any],
    closure: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        "topologyValidation": {
            "status": topology["status"],
            "backend": topology["backend"],
            "backendAvailable": topology["backendAvailable"],
            "physicalValidationLevel": topology["physicalValidationLevel"],
        },
        "encoding": {
            "status": _complete_if(encoding_report.get("logicalQubitCapacity", 0) > 0),
            "logicalQubitCapacity": encoding_report.get("logicalQubitCapacity"),
        },
        "primitiveSpec": {
            "status": _complete_if(primitive_spec.get("universalityStatus") == "conditional_universal_path"),
            "universalityStatus": primitive_spec.get("universalityStatus"),
        },
        "resourceModel": {
            "status": _complete_if(bool(resource_model.get("requiredNonGaussianResources"))),
            "logicalQubits": resource_model.get("logicalQubits"),
        },
        "compilerRuntime": {
            "status": _complete_if(compiled.get("instructionCount", 0) > 0 and runtime.get("totalProgramTimeNsPerShot", 0) > 0),
            "instructionCount": compiled.get("instructionCount"),
            "totalProgramTimeNsPerShot": runtime.get("totalProgramTimeNsPerShot"),
        },
        "errorBudget": {
            "status": _complete_if(_estimated_physical_error_rate(error_budget) >= 0),
            "estimatedPhysicalErrorRate": _estimated_physical_error_rate(error_budget),
        },
        "errorCorrectionPlan": {
            "status": _complete_if("decoder" in error_correction),
            "belowThreshold": error_correction.get("belowThreshold"),
            "estimatedLogicalErrorRatePerCycle": error_correction.get("estimatedLogicalErrorRatePerCycle"),
        },
        "deviceSweep": {
            "status": _complete_if(device_sweep.get("schemaVersion") == "open-quantum.device-sweep.v1"),
            "sweepStatus": device_sweep.get("status"),
            "runCount": device_sweep.get("runCount", 0),
            "perDeviceBestCandidates": _per_device_best(device_sweep),
        },
        "fusionPrimitive": {
            "status": _complete_if(fusion.get("schemaVersion") == "open-quantum.fusion-primitive.v1"),
            "primitiveStatus": fusion.get("status"),
            "estimatedProcessFidelity": (fusion.get("qualityModel") or {}).get("estimatedProcessFidelity"),
            "estimatedHeraldingSuccessProbability": (fusion.get("heraldingModel") or {}).get(
                "estimatedHeraldingSuccessProbability"
            ),
        },
        "thresholdSweep": {
            "status": _complete_if(threshold_sweep.get("schemaVersion") == "open-quantum.threshold-sweep.v1"),
            "sweepStatus": threshold_sweep.get("status"),
            "runCount": threshold_sweep.get("runCount", 0),
            "champion": _threshold_champion(threshold_sweep),
        },
        "resourceSweep": {
            "status": _complete_if(resource_sweep.get("schemaVersion") == "open-quantum.resource-sweep.v1"),
            "runCount": resource_sweep.get("runCount", 0),
            "summary": resource_sweep.get("summary", {}),
        },
        "nodeAlphaCompute": {
            "status": _complete_if(compute.get("schemaVersion") == "open-quantum.node-alpha-compute-report.v1"),
            "summary": compute.get("summary", {}),
        },
        "designDossier": {
            "status": _complete_if(dossier.get("schemaVersion") == "open-quantum.design-dossier.v1"),
            "dossierStatus": (dossier.get("summary") or {}).get("status"),
        },
        "nodeAlphaClosure": {
            "status": _complete_if(closure.get("schemaVersion") == "open-quantum.node-alpha-closure.v1"),
            "closureStatus": (closure.get("summary") or {}).get("status"),
            "completeQuantumComputer": _closure_flag(closure, "complete_quantum_computer"),
        },
    }


def _completion_checklist(
    *,
    artifact_paths: dict[str, Path],
    layers: dict[str, dict[str, Any]],
    device_sweep: dict[str, Any],
    threshold_sweep: dict[str, Any],
    fusion: dict[str, Any],
    closure: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        _check(
            "topology_validation_simulated",
            "Run or surrogate the full topology validation layer.",
            layers["topologyValidation"]["status"] == "complete",
            ["complete-simulation.topologyValidation"],
            _backend_caveat(layers["topologyValidation"]),
        ),
        _check(
            "static_stack_models_generated",
            "Generate encoding, primitive, resources, compiler/runtime, error budget, and error-correction plan.",
            all(
                layers[name]["status"] == "complete"
                for name in (
                    "encoding",
                    "primitiveSpec",
                    "resourceModel",
                    "compilerRuntime",
                    "errorBudget",
                    "errorCorrectionPlan",
                )
            ),
            ["complete-simulation.simulationLayers"],
            [],
        ),
        _check(
            "extended_device_sweep_attached",
            "Attach extended Device sweep and best local candidates for coupler, MZI, phase-shifter, and truth-switch.",
            layers["deviceSweep"]["status"] == "complete"
            and {"coupler", "mzi", "phase-shifter", "truth-switch"}.issubset(
                set((device_sweep.get("perDeviceChampions") or {}).keys())
            ),
            [artifact_paths["deviceSweep"]],
            [],
        ),
        _check(
            "fusion_primitive_simulated",
            "Simulate the two-qubit heralded fusion primitive from the best local MZI/fusion-cell evidence.",
            layers["fusionPrimitive"]["status"] == "complete",
            ["complete-simulation.fusionPrimitive"],
            fusion.get("blockers", []),
        ),
        _check(
            "threshold_sweep_attached",
            "Attach the extended Threshold sweep and its best candidate.",
            layers["thresholdSweep"]["status"] == "complete" and bool(threshold_sweep.get("champion")),
            [artifact_paths["thresholdSweep"]],
            threshold_sweep.get("blockers", []),
        ),
        _check(
            "resource_sweep_attached",
            "Attach the extended analytical Resource sweep.",
            layers["resourceSweep"]["status"] == "complete",
            [artifact_paths["resourceSweep"]],
            [],
        ),
        _check(
            "node_alpha_reports_attached",
            "Attach Node Alpha compute, design dossier, and closure reports.",
            all(
                layers[name]["status"] == "complete"
                for name in ("nodeAlphaCompute", "designDossier", "nodeAlphaClosure")
            ),
            [
                artifact_paths["computeReport"],
                artifact_paths["designDossier"],
                artifact_paths["nodeAlphaClosure"],
            ],
            [],
        ),
        _check(
            "real_world_gates_marked",
            "Mark gates that still need real foundry, hardware, decoder, or lab data.",
            bool(closure.get("hardStopsRequiringRealWorldInput")),
            [artifact_paths["nodeAlphaClosure"]],
            [],
        ),
    ]


def _failed_simulation_gates(
    *,
    device_sweep: dict[str, Any],
    threshold_sweep: dict[str, Any],
    fusion: dict[str, Any],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for device, gap in (device_sweep.get("perDeviceGapToAcceptance") or {}).items():
        if not isinstance(gap, dict):
            continue
        blockers = [
            name.removesuffix("Excess")
            for name, value in gap.items()
            if name.endswith("Excess") and _positive(value)
        ]
        if blockers:
            failures.append(
                {
                    "gate": f"device:{device}",
                    "status": "failed_simulated_acceptance",
                    "blockingMetrics": blockers,
                    "candidateId": gap.get("candidateId"),
                }
            )
    if fusion.get("status") != "primitive_ready":
        failures.append(
            {
                "gate": "fusion_primitive",
                "status": fusion.get("status"),
                "blockers": fusion.get("blockers", []),
            }
        )
    if threshold_sweep.get("status") != "below_threshold_candidate_found":
        failures.append(
            {
                "gate": "threshold",
                "status": threshold_sweep.get("status"),
                "blockers": threshold_sweep.get("blockers", []),
            }
        )
    return failures


def _hard_stops_requiring_real_world_input(closure: dict[str, Any]) -> list[dict[str, Any]]:
    stops = []
    for stop in closure.get("hardStopsRequiringRealWorldInput", []):
        stops.append(
            {
                "gate": stop.get("prototypeCriterion") or stop.get("requirement"),
                "status": "requires_real_world_input",
                "reason": stop.get("reason"),
                "firstBlocker": stop.get("firstBlocker"),
            }
        )
    return stops


def _per_device_best(report: dict[str, Any]) -> dict[str, Any]:
    best: dict[str, Any] = {}
    for device, candidate in (report.get("perDeviceChampions") or {}).items():
        metrics = candidate.get("fdtdMetrics", {}) if isinstance(candidate, dict) else {}
        best[device] = {
            "candidateId": candidate.get("candidateId") if isinstance(candidate, dict) else None,
            "acceptanceStatus": candidate.get("acceptanceStatus") if isinstance(candidate, dict) else None,
            "physicalValidationLevel": candidate.get("physicalValidationLevel") if isinstance(candidate, dict) else None,
            "sourceModel": candidate.get("sourceModel") if isinstance(candidate, dict) else None,
            "usefulTransmission": metrics.get("usefulTransmission"),
            "insertionLossDb": metrics.get("insertionLossDb"),
            "reflectionRatio": metrics.get("reflectionRatio"),
            "crosstalkRatio": metrics.get("crosstalkRatio"),
        }
    return best


def _threshold_champion(report: dict[str, Any]) -> dict[str, Any] | None:
    champion = report.get("champion")
    if not isinstance(champion, dict):
        return None
    return {
        "candidateId": champion.get("candidateId"),
        "belowThreshold": champion.get("belowThreshold"),
        "effectivePhysicalErrorRate": champion.get("effectivePhysicalErrorRate"),
        "estimatedLogicalErrorRatePerCycle": champion.get("estimatedLogicalErrorRatePerCycle"),
    }


def _fusion_device_candidate(device_sweep: dict[str, Any]) -> dict[str, Any] | None:
    champions = device_sweep.get("perDeviceChampions")
    if isinstance(champions, dict):
        candidates = [
            candidate
            for device in ("truth-switch", "mzi", "coupler")
            if isinstance((candidate := champions.get(device)), dict)
        ]
        if candidates:
            return max(candidates, key=_fusion_candidate_rank)
    champion = device_sweep.get("champion")
    return champion if isinstance(champion, dict) else None


def _fusion_candidate_rank(candidate: dict[str, Any]) -> tuple[int, int, float, float]:
    metrics = candidate.get("fdtdMetrics", {})
    through = float(metrics.get("throughRatio", 0.0))
    cross = float(metrics.get("crossRatio", 0.0))
    useful = float(metrics.get("usefulTransmission", through + cross))
    reflection = float(metrics.get("reflectionRatio", 1.0))
    crosstalk = float(metrics.get("crosstalkRatio", metrics.get("imbalanceRatio", abs(through - cross))))
    fidelity_penalty = (0.5 * reflection) + (0.25 * crosstalk) + (0.25 * max(0.0, 1.0 - useful))
    reliable = metrics.get("normalizationReliable") is not False
    return (
        1 if _device_candidate_accepted(candidate) else 0,
        1 if reliable else 0,
        -fidelity_penalty,
        float(candidate.get("score", 0.0)),
    )


def _all_core_devices_accepted(report: dict[str, Any]) -> bool:
    champions = report.get("perDeviceChampions")
    if not isinstance(champions, dict):
        return False
    required = {"coupler", "mzi", "phase-shifter", "truth-switch"}
    if not required.issubset(set(champions)):
        return False
    return all(isinstance(candidate, dict) and _device_candidate_accepted(candidate) for candidate in champions.values())


def _device_candidate_accepted(candidate: dict[str, Any]) -> bool:
    status = str(candidate.get("acceptanceStatus", ""))
    if status in {"accepted_first_pass_candidate", "surrogate_accepted_candidate"}:
        return True
    if status.endswith("_accepted_candidate"):
        return True
    metrics = candidate.get("fdtdMetrics", {})
    return (
        metrics.get("normalizationReliable") is not False
        and float(metrics.get("insertionLossDb", 120.0)) <= 1.0
        and float(metrics.get("reflectionRatio", 1.0)) <= 0.05
        and float(metrics.get("usefulTransmission", 0.0)) >= 0.5
        and float(metrics.get("crosstalkRatio", metrics.get("imbalanceRatio", 1.0))) <= 0.05
    )



def _artifact(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path),
        "present": path.is_file() or bool(report),
        "schemaVersion": report.get("schemaVersion"),
        "status": report.get("status") or (report.get("summary") or {}).get("status"),
    }


def _check(
    criterion_id: str,
    requirement: str,
    passed: bool,
    evidence: list[Any],
    caveats: list[str],
) -> dict[str, Any]:
    return {
        "id": criterion_id,
        "requirement": requirement,
        "status": "complete" if passed else "missing_or_failed",
        "evidence": [str(item) for item in evidence],
        "caveats": caveats,
    }


def _backend_caveat(layer: dict[str, Any]) -> list[str]:
    if layer.get("backendAvailable"):
        return []
    return [
        f"Backend {layer.get('backend')} used because the full topology simulator is unavailable."
    ]


def _latest_report(root: Path, directory_glob: str, filename: str, fallback: Path) -> Path:
    candidates = sorted(path / filename for path in root.glob(directory_glob) if (path / filename).is_file())
    return candidates[-1] if candidates else fallback


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _estimated_physical_error_rate(error_budget: dict[str, Any]) -> float:
    terms = error_budget.get("estimatedPhysicalErrorTerms", {})
    return float(sum(float(value) for value in terms.values() if isinstance(value, (int, float)) and math.isfinite(value)))


def _closure_flag(report: dict[str, Any], name: str) -> bool:
    flags = report.get("readinessFlags")
    return bool(isinstance(flags, dict) and flags.get(name) is True)


def _complete_if(condition: bool) -> str:
    return "complete" if condition else "missing_or_failed"


def _positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and value > 0
