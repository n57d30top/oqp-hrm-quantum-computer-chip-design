"""Value-upgrade package for simulation-only OQP-HRM evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any

from .blueprint import Blueprint
from .evidence_bundle import generate_evidence_bundle
from .fault_tolerance import generate_fault_tolerance_audit, ingest_fault_tolerance_dataset
from .node_alpha import generate_node_alpha_closure
from .prototype_readiness import generate_prototype_readiness
from .report import write_json_report
from .sparameters import generate_sparameter_audit
from .testchip_simulation import TESTCHIP_DEVICES, run_testchip_simulation
from .threshold import run_threshold_sweep


DEFAULT_WIDTH_ERRORS_NM = [-20.0, -10.0, 0.0, 10.0, 20.0]
DEFAULT_GAP_ERRORS_NM = [-20.0, -10.0, 0.0, 10.0, 20.0]
DEFAULT_PHASE_ERRORS_RAD = [-0.01, -0.005, 0.0, 0.005, 0.01]
DEFAULT_TEMPERATURE_DELTAS_C = [-10.0, -5.0, 0.0, 5.0, 10.0]
DEFAULT_WAVELENGTHS_NM = [1510.0, 1520.0, 1550.0, 1580.0, 1590.0]


def generate_value_package(
    blueprint: Blueprint,
    *,
    artifact_root: str | Path = "reports/node-alpha",
    out_dir: str | Path | None = None,
    device_sweep_path: str | Path | None = None,
    syndrome_event_count: int = 10000,
    shots: int = 10000,
    target_logical_error_rate: float = 1e-6,
) -> dict[str, Any]:
    """Generate the highest-value simulation-only package available without lab data."""

    root = Path(artifact_root)
    qc = root / "qc-path"
    package = Path(out_dir) if out_dir else root / "value-upgrade-20260502"
    package.mkdir(parents=True, exist_ok=True)
    qc.mkdir(parents=True, exist_ok=True)

    device_path = Path(device_sweep_path) if device_sweep_path else qc / "device-sweep.json"
    device_sweep = _read_json(device_path)
    threshold_device = _best_threshold_device_candidate(device_sweep)
    threshold_device_path = package / "threshold-device-candidate.json"
    if threshold_device:
        write_json_report(threshold_device, threshold_device_path)

    threshold_dir = qc / "threshold-sweep-value-upgrade-20260502"
    threshold_sweep = run_threshold_sweep(
        blueprint,
        device_report=threshold_device,
        distances=[5, 7, 9, 11, 13, 15],
        physical_error_rates=[0.00005, 0.0001, 0.00025],
        loss_values_db=[0.0, 0.02, 0.05],
        detector_efficiencies=[1.0, 0.995],
        dark_count_rates_hz=[0.0],
        phase_errors_rad=[0.0, 0.001],
        feed_forward_latencies_ns=[0.0, 5.0],
        max_runs=512,
        out_dir=threshold_dir,
    )
    threshold_sweep = _promote_logical_target_candidate(threshold_sweep, threshold_dir, target_logical_error_rate)
    write_json_report(threshold_sweep, qc / "threshold-sweep.json")

    high_resolution = _high_resolution_robustness_report(root=root, baseline_device_sweep=device_sweep)
    high_resolution_path = package / "high-resolution-robustness-report.json"
    write_json_report(high_resolution, high_resolution_path)
    yield_optimized_sweep = _yield_optimized_device_sweep(
        baseline_device_sweep=device_sweep,
        high_resolution=high_resolution,
    )
    yield_optimized_path = package / "yield-optimized-device-sweep.json"
    write_json_report(yield_optimized_sweep, yield_optimized_path)

    testchip_dir = package / "testchip"
    testchip = run_testchip_simulation(
        blueprint,
        out_dir=testchip_dir,
        device_sweep_path=yield_optimized_path,
        wavelengths_nm=DEFAULT_WAVELENGTHS_NM,
        width_errors_nm=DEFAULT_WIDTH_ERRORS_NM,
        gap_errors_nm=DEFAULT_GAP_ERRORS_NM,
        phase_errors_rad=DEFAULT_PHASE_ERRORS_RAD,
        temperature_deltas_c=DEFAULT_TEMPERATURE_DELTAS_C,
        shots=shots,
    )

    virtual_manifest = _write_virtual_sparameter_manifest(
        root=root,
        package=package,
        virtual_sparameters=testchip["virtualSParameters"],
    )
    sparameter_audit = generate_sparameter_audit(blueprint, model_manifest_path=qc / "sparameter-models.json")
    write_json_report(sparameter_audit, qc / "sparameter-audit.json")

    syndrome_dataset = package / "synthetic-syndrome-events.jsonl"
    _write_synthetic_syndrome_events(syndrome_dataset, syndrome_event_count)
    fault_ingest = ingest_fault_tolerance_dataset(
        blueprint,
        dataset_path=syndrome_dataset,
        decoder_report_out=qc / "decoder-report.json",
        noise_dataset_manifest_out=qc / "syndrome-noise-dataset.json",
        decoder="synthetic_erasure_matching",
        implementation_status="benchmarked",
    )
    fault_audit = generate_fault_tolerance_audit(
        blueprint,
        threshold_report_path=qc / "threshold-sweep.json",
        decoder_report_path=qc / "decoder-report.json",
        noise_dataset_manifest_path=qc / "syndrome-noise-dataset.json",
        hardware_audit_path=qc / "hardware-audit.json",
        target_logical_error_rate=target_logical_error_rate,
        min_sampled_syndrome_events=syndrome_event_count,
    )
    write_json_report(fault_audit, qc / "fault-tolerance-audit.json")

    evidence_bundle = generate_evidence_bundle(
        blueprint,
        artifact_root=root,
        write_templates=True,
        templates_dir=root / "evidence-intake" / "templates",
    )
    write_json_report(evidence_bundle, qc / "evidence-bundle.json")
    prototype = generate_prototype_readiness(blueprint, artifact_root=root, evidence_dir=qc)
    write_json_report(prototype, qc / "prototype-readiness.json")
    closure = generate_node_alpha_closure(blueprint, artifact_root=root)
    write_json_report(closure, qc / "node-alpha-closure.json")

    ip_dossier = _ip_value_dossier(
        blueprint=blueprint,
        device_sweep=device_sweep,
        threshold_sweep=threshold_sweep,
        testchip=testchip,
        sparameter_audit=sparameter_audit,
        fault_audit=fault_audit,
    )
    ip_json = package / "ip-value-dossier.json"
    ip_markdown = package / "ip-value-dossier.md"
    write_json_report(ip_dossier, ip_json)
    ip_markdown.write_text(_ip_markdown(ip_dossier), encoding="utf-8")

    repro_manifest = _reproducibility_manifest(
        artifact_root=root,
        package=package,
        device_sweep_path=device_path,
        syndrome_event_count=syndrome_event_count,
        shots=shots,
        target_logical_error_rate=target_logical_error_rate,
    )
    repro_path = package / "reproducibility-manifest.json"
    write_json_report(repro_manifest, repro_path)

    report = {
        "schemaVersion": "open-quantum.value-upgrade-package.v1",
        "generatedAt": _now(),
        "sourcePath": blueprint.source_path,
        "objective": "Increase value using Node Alpha and repository-only work without claiming real-world readiness.",
        "scope": {
            "simulatedOnly": True,
            "notEvidenceFor": [
                "foundry-calibrated S-parameters",
                "hardware primitive demonstration",
                "DRC/LVS signoff",
                "prototype readiness",
                "legal patentability opinion",
            ],
        },
        "artifactRefs": {
            "testchipSimulation": str(testchip_dir / "testchip-simulation.json"),
            "highResolutionRobustnessReport": str(high_resolution_path),
            "yieldOptimizedDeviceSweep": str(yield_optimized_path),
            "virtualSparameterManifest": str(qc / "sparameter-models.json"),
            "sparameterAudit": str(qc / "sparameter-audit.json"),
            "thresholdSweep": str(qc / "threshold-sweep.json"),
            "thresholdSweepDirectory": str(threshold_dir),
            "syntheticSyndromeDataset": str(syndrome_dataset),
            "decoderReport": str(qc / "decoder-report.json"),
            "syndromeDatasetManifest": str(qc / "syndrome-noise-dataset.json"),
            "faultToleranceAudit": str(qc / "fault-tolerance-audit.json"),
            "evidenceBundle": str(qc / "evidence-bundle.json"),
            "evidenceTemplates": str(root / "evidence-intake" / "templates"),
            "prototypeReadiness": str(qc / "prototype-readiness.json"),
            "nodeAlphaClosure": str(qc / "node-alpha-closure.json"),
            "ipValueDossier": str(ip_json),
            "ipValueDossierMarkdown": str(ip_markdown),
            "reproducibilityManifest": str(repro_path),
        },
        "summary": {
            "status": "value_package_generated",
            "testchipStatus": testchip["summary"]["status"],
            "testchipSystemYieldEstimate": testchip["yieldSweep"]["summary"]["systemYieldEstimate"],
            "testchipYieldAcceptedDevices": testchip["yieldSweep"]["summary"]["acceptedDeviceCount"],
            "testchipYieldRequiredDevices": testchip["yieldSweep"]["summary"]["requiredDeviceCount"],
            "testchipYieldDeviceSource": yield_optimized_sweep["sourceSelection"]["method"],
            "highResolutionStatus": high_resolution["summary"]["status"],
            "highResolutionAcceptedDevices": high_resolution["summary"]["acceptedDevices"],
            "highResolutionBlockedDevices": high_resolution["summary"]["blockedDevices"],
            "virtualSparameterModelCount": virtual_manifest["summary"]["modelCount"],
            "virtualSparameterModelsReadyForFoundryGate": sparameter_audit["readinessFlags"]["sparameter_models_ready"],
            "thresholdStatus": threshold_sweep["status"],
            "thresholdChampionLogicalErrorRate": (threshold_sweep.get("champion") or {}).get(
                "estimatedLogicalErrorRatePerCycle"
            ),
            "syntheticSyndromeEventCount": syndrome_event_count,
            "faultToleranceReady": fault_audit["readinessFlags"]["fault_tolerance_ready"],
            "faultToleranceBlocksOnlyOnHardware": _fault_tolerance_blocks_only_on_hardware(fault_audit),
            "prototypeStatus": prototype["summary"]["status"],
            "prototypeCompleteCriteria": prototype["summary"].get("completeCriteria"),
            "prototypeTotalCriteria": prototype["summary"].get("totalCriteria"),
            "evidencePresentArtifacts": evidence_bundle["summary"]["presentArtifactCount"],
            "evidenceRequiredArtifacts": evidence_bundle["summary"]["requiredArtifactCount"],
        },
        "valueLeversCompleted": [
            "expanded deterministic tolerance/yield sweep",
            "yield-optimized testchip candidate promotion from accepted 20/60 Node Alpha evidence",
            "20/60 high-resolution robustness audit over available Node Alpha sweeps",
            "virtual S-parameter model files and manifest",
            "synthetic decoder/syndrome dataset with hash manifest",
            "stronger analytical threshold sweep using the lowest-error accepted local device evidence",
            "evidence intake templates",
            "IP/value dossier",
            "reproducibility manifest",
        ],
        "remainingRealWorldValueLevers": [
            "replace virtual S-parameters with foundry/wafer-calibrated compact models",
            "fabricate and measure the testchip",
            "attach real source, detector, packaging, control, and calibration evidence",
            "run DRC/LVS with a version-locked foundry PDK",
            "replace synthetic syndrome data with sampled hardware-calibrated circuit-noise datasets",
            "obtain a patentability and freedom-to-operate opinion from counsel",
        ],
    }
    write_json_report(report, package / "value-upgrade-report.json")
    return report


def _high_resolution_robustness_report(*, root: Path, baseline_device_sweep: dict[str, Any]) -> dict[str, Any]:
    qc = root / "qc-path"
    required_devices = sorted((baseline_device_sweep.get("perDeviceChampions") or {}).keys()) or sorted(TESTCHIP_DEVICES)
    runs: list[dict[str, Any]] = []
    for path in sorted(qc.glob("mission-*-device-sweep.json")):
        wrapper = _read_json(path)
        report = _unwrap_device_sweep_report(wrapper)
        resolution = int(report.get("resolution", 0) or 0)
        until = float(report.get("until", 0.0) or 0.0)
        if resolution < 20 or until < 60:
            continue
        runs.append(_summarize_high_resolution_run(path, wrapper, report))

    candidate_file_evidence = _high_resolution_candidate_file_evidence(qc, required_devices)
    best_by_device: dict[str, Any] = {}
    for device in required_devices:
        device_evidence = [
            champion
            for run in runs
            for champion in run["deviceChampions"].values()
            if champion.get("device") == device
        ]
        device_evidence.extend(item for item in candidate_file_evidence if item.get("device") == device)
        if not device_evidence:
            best_by_device[device] = {
                "device": device,
                "status": "missing_high_resolution_evidence",
                "accepted": False,
                "blockers": ["no 20/60 Node Alpha evidence found for this device"],
            }
            continue
        best = min(device_evidence, key=_high_resolution_evidence_rank)
        best_by_device[device] = best

    accepted_devices = sorted(device for device, evidence in best_by_device.items() if evidence.get("accepted") is True)
    blocked_devices = sorted(device for device in required_devices if device not in accepted_devices)
    if not runs:
        status = "no_high_resolution_runs_found"
    elif not blocked_devices:
        status = "all_core_devices_high_resolution_accepted"
    else:
        status = "high_resolution_gap_quantified"
    return {
        "schemaVersion": "open-quantum.high-resolution-robustness.v1",
        "generatedAt": _now(),
        "baseline": {
            "status": baseline_device_sweep.get("status"),
            "resolution": baseline_device_sweep.get("resolution"),
            "until": baseline_device_sweep.get("until"),
            "validationTier": baseline_device_sweep.get("validationTier"),
            "deviceCount": len(required_devices),
        },
        "highResolutionTarget": {
            "resolution": 20,
            "until": 60,
            "devices": required_devices,
        },
        "summary": {
            "status": status,
            "runCount": len(runs),
            "candidateFileCount": len(candidate_file_evidence),
            "acceptedDevices": accepted_devices,
            "blockedDevices": blocked_devices,
            "allRequiredDevicesAccepted": not blocked_devices and bool(required_devices),
        },
        "bestEvidenceByDevice": best_by_device,
        "runs": runs,
        "simulationOnlyLimitations": [
            "This robustness report is based on available Node Alpha 2D simulation sweeps.",
            "It does not replace 3D electromagnetic verification, foundry PDK signoff, measured S-parameters, or lab data.",
        ],
    }


def _high_resolution_candidate_file_evidence(qc: Path, required_devices: list[str]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for mission_dir in sorted(qc.glob("mission-*")):
        if not mission_dir.is_dir():
            continue
        for path in sorted(mission_dir.glob("*.json")):
            candidate = _read_json(path)
            device = candidate.get("device")
            if device not in required_devices:
                continue
            metrics = candidate.get("fdtdMetrics") or {}
            timing = metrics.get("timing") or {}
            geometry = candidate.get("geometry") or {}
            resolution = int(timing.get("resolution") or geometry.get("resolution") or 0)
            until = float(timing.get("until") or geometry.get("until") or 0.0)
            if resolution < 20 or until < 60:
                continue
            evidence.append(
                _summarize_high_resolution_champion(
                    path=path,
                    run={
                        "status": candidate.get("acceptanceStatus"),
                        "resolution": resolution,
                        "until": until,
                    },
                    device=device,
                    candidate=candidate,
                    gap=candidate.get("gapToAcceptance") or {},
                )
            )
    return evidence


def _yield_optimized_device_sweep(*, baseline_device_sweep: dict[str, Any], high_resolution: dict[str, Any]) -> dict[str, Any]:
    baseline_champions = baseline_device_sweep.get("perDeviceChampions") or {}
    required_devices = sorted(baseline_champions.keys()) or sorted(TESTCHIP_DEVICES)
    optimized_champions: dict[str, Any] = {}
    promoted_devices: list[str] = []
    retained_devices: list[str] = []
    for device in required_devices:
        high_res = (high_resolution.get("bestEvidenceByDevice") or {}).get(device, {})
        if high_res.get("accepted") is True:
            optimized_champions[device] = _candidate_from_high_resolution_evidence(high_res)
            promoted_devices.append(device)
        elif isinstance(baseline_champions.get(device), dict):
            optimized_champions[device] = baseline_champions[device]
            retained_devices.append(device)

    all_devices_present = all(device in optimized_champions for device in required_devices)
    all_promoted = all(device in promoted_devices for device in required_devices)
    status = "all_requested_devices_accepted" if all_devices_present and all_promoted else baseline_device_sweep.get("status")
    return {
        "schemaVersion": "open-quantum.device-sweep.v1",
        "sourcePath": baseline_device_sweep.get("sourcePath"),
        "sourceArtifact": baseline_device_sweep.get("sourceArtifact"),
        "status": status,
        "runCount": sum(int(run.get("runCount", 0) or 0) for run in high_resolution.get("runs", []))
        or baseline_device_sweep.get("runCount", 0),
        "resolution": 20 if promoted_devices else baseline_device_sweep.get("resolution"),
        "until": 60 if promoted_devices else baseline_device_sweep.get("until"),
        "validationTier": "high_resolution_yield_optimized_2d_first_pass" if promoted_devices else baseline_device_sweep.get("validationTier"),
        "perDeviceChampions": optimized_champions,
        "champion": _yield_optimized_champion(optimized_champions),
        "deviceCoverage": {
            "requestedDevices": required_devices,
            "observedDevices": sorted(optimized_champions.keys()),
            "missingDevices": [device for device in required_devices if device not in optimized_champions],
            "complete": all_devices_present,
        },
        "sourceSelection": {
            "method": "promote_accepted_20_60_high_resolution_candidates_for_testchip_yield",
            "promotedDevices": sorted(promoted_devices),
            "retainedBaselineDevices": sorted(retained_devices),
            "fallbackAllowed": True,
            "claimBoundary": "simulation-only candidate promotion, not foundry yield proof",
        },
        "limitations": [
            "Promoted candidates are accepted 2D Node Alpha evidence, not 3D foundry-calibrated device models.",
            "Yield estimate remains deterministic and must be replaced by foundry process statistics.",
        ],
    }


def _candidate_from_high_resolution_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    metrics = dict(evidence.get("metrics") or {})
    useful = float(metrics.get("usefulTransmission", 0.0) or 0.0)
    crosstalk = float(metrics.get("crosstalkRatio", 0.0) or 0.0)
    reflection = float(metrics.get("reflectionRatio", 0.0) or 0.0)
    through = max(0.0, useful - crosstalk)
    cross = max(0.0, min(useful, crosstalk))
    metrics.update(
        {
            "throughRatio": through,
            "crossRatio": cross,
            "reflectionRatio": reflection,
            "crosstalkRatio": crosstalk,
            "insertionLossDb": float(metrics.get("insertionLossDb", 0.0) or 0.0),
            "usefulTransmission": useful,
            "normalizationReliable": True,
        }
    )
    return {
        "schemaVersion": "open-quantum.eigenmode-device.v1",
        "candidateId": evidence.get("candidateId"),
        "device": evidence.get("device"),
        "acceptanceStatus": "accepted_first_pass_candidate",
        "physicalValidationLevel": "eigenmode_calibrated_2d_first_pass",
        "sourceModel": "eigenmode",
        "validationTier": "high_resolution_gap_probe",
        "sourceRun": evidence.get("sourceRun"),
        "fdtdMetrics": metrics,
        "limitations": [
            "Promoted from 20/60 Node Alpha evidence for simulation-only yield planning.",
            "Not a foundry-calibrated or measured device artifact.",
        ],
    }


def _yield_optimized_champion(candidates: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    return min(candidates.values(), key=lambda candidate: _threshold_candidate_penalty(candidate))


def _unwrap_device_sweep_report(wrapper: dict[str, Any]) -> dict[str, Any]:
    report = wrapper.get("report")
    return report if isinstance(report, dict) else wrapper


def _summarize_high_resolution_run(path: Path, wrapper: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    champions = report.get("perDeviceChampions") or {}
    gaps = report.get("perDeviceGapToAcceptance") or {}
    device_champions = {
        device: _summarize_high_resolution_champion(
            path=path,
            run=report,
            device=device,
            candidate=candidate,
            gap=gaps.get(device, {}),
        )
        for device, candidate in champions.items()
        if isinstance(candidate, dict)
    }
    return {
        "path": str(path),
        "runId": wrapper.get("runId") or path.stem.removesuffix("-device-sweep"),
        "status": report.get("status"),
        "resolution": report.get("resolution"),
        "until": report.get("until"),
        "runCount": report.get("runCount"),
        "requestedDevices": (report.get("deviceCoverage") or {}).get("requestedDevices", []),
        "observedDevices": (report.get("deviceCoverage") or {}).get("observedDevices", []),
        "deviceChampions": device_champions,
    }


def _summarize_high_resolution_champion(
    *,
    path: Path,
    run: dict[str, Any],
    device: str,
    candidate: dict[str, Any],
    gap: dict[str, Any],
) -> dict[str, Any]:
    metrics = candidate.get("fdtdMetrics") or {}
    accepted = _device_gap_passes(gap)
    return {
        "device": device,
        "candidateId": candidate.get("candidateId"),
        "accepted": accepted,
        "status": "accepted_at_20_60" if accepted else "gap_at_20_60",
        "sourceRun": str(path),
        "sourceStatus": run.get("status"),
        "metrics": {
            "crosstalkRatio": metrics.get("crosstalkRatio", metrics.get("imbalanceRatio")),
            "reflectionRatio": metrics.get("reflectionRatio"),
            "insertionLossDb": metrics.get("insertionLossDb"),
            "usefulTransmission": metrics.get("usefulTransmission"),
            "outputPortNormalizationFlux": metrics.get("outputPortNormalizationFlux"),
        },
        "acceptanceGap": {
            "crosstalkRatioExcess": gap.get("crosstalkRatioExcess"),
            "reflectionRatioExcess": gap.get("reflectionRatioExcess"),
            "insertionLossDbExcess": gap.get("insertionLossDbExcess"),
            "usefulTransmissionTarget": gap.get("usefulTransmissionTarget"),
            "outputPortNormalizationFluxTarget": gap.get("outputPortNormalizationFluxTarget"),
            "normalizationReliable": gap.get("normalizationReliable"),
        },
        "blockers": [] if accepted else _high_resolution_blockers(gap),
    }


def _device_gap_passes(gap: dict[str, Any]) -> bool:
    if not gap:
        return False
    try:
        return (
            bool(gap.get("normalizationReliable"))
            and float(gap.get("crosstalkRatioExcess", math.inf)) <= 1e-12
            and float(gap.get("reflectionRatioExcess", math.inf)) <= 1e-12
            and float(gap.get("insertionLossDbExcess", math.inf)) <= 1e-12
            and float(gap.get("usefulTransmission", 0.0)) >= float(gap.get("usefulTransmissionTarget", math.inf))
            and float(gap.get("outputPortNormalizationFlux", 0.0))
            >= float(gap.get("outputPortNormalizationFluxTarget", math.inf))
        )
    except (TypeError, ValueError):
        return False


def _high_resolution_blockers(gap: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if not gap:
        return ["missing acceptance gap details"]
    if not gap.get("normalizationReliable"):
        blockers.append("normalization is not reliable")
    for metric in ("crosstalkRatio", "reflectionRatio", "insertionLossDb"):
        excess = gap.get(f"{metric}Excess")
        if excess is not None and float(excess) > 1e-12:
            blockers.append(f"{metric} exceeds target by {excess}")
    useful = gap.get("usefulTransmission")
    useful_target = gap.get("usefulTransmissionTarget")
    if useful is not None and useful_target is not None and float(useful) < float(useful_target):
        blockers.append(f"usefulTransmission {useful} below target {useful_target}")
    norm = gap.get("outputPortNormalizationFlux")
    norm_target = gap.get("outputPortNormalizationFluxTarget")
    if norm is not None and norm_target is not None and float(norm) < float(norm_target):
        blockers.append(f"outputPortNormalizationFlux {norm} below target {norm_target}")
    return blockers


def _high_resolution_evidence_rank(evidence: dict[str, Any]) -> tuple[int, float, float, float]:
    metrics = evidence.get("metrics") or {}
    gap = evidence.get("acceptanceGap") or {}
    crosstalk_excess = float(gap.get("crosstalkRatioExcess", 1.0) or 0.0)
    reflection_excess = float(gap.get("reflectionRatioExcess", 1.0) or 0.0)
    loss_excess = float(gap.get("insertionLossDbExcess", 1.0) or 0.0)
    crosstalk = float(metrics.get("crosstalkRatio", 1.0) or 0.0)
    reflection = float(metrics.get("reflectionRatio", 1.0) or 0.0)
    return (
        0 if evidence.get("accepted") else 1,
        crosstalk_excess + reflection_excess + loss_excess,
        reflection,
        crosstalk,
    )


def _best_threshold_device_candidate(device_sweep: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [
        candidate
        for candidate in (device_sweep.get("perDeviceChampions") or {}).values()
        if isinstance(candidate, dict)
    ]
    if not candidates:
        champion = device_sweep.get("champion")
        return champion if isinstance(champion, dict) else None
    return min(candidates, key=_threshold_candidate_penalty)


def _promote_logical_target_candidate(
    threshold_sweep: dict[str, Any],
    threshold_dir: Path,
    target_logical_error_rate: float,
) -> dict[str, Any]:
    candidates = []
    for path in sorted(threshold_dir.glob("*.json")):
        if path.name in {"threshold-sweep.json", "champion.json"}:
            continue
        candidate = _read_json(path)
        if candidate.get("belowThreshold") is True:
            candidates.append(candidate)
    target_candidates = [
        candidate
        for candidate in candidates
        if float(candidate.get("estimatedLogicalErrorRatePerCycle", 1.0)) <= target_logical_error_rate
    ]
    if not target_candidates:
        return threshold_sweep
    promoted = min(
        target_candidates,
        key=lambda candidate: (
            float(candidate.get("estimatedLogicalErrorRatePerCycle", 1.0)),
            int(candidate.get("estimatedPhysicalModesPerCorrectionCycle", 10**18)),
        ),
    )
    ranked = sorted(
        candidates,
        key=lambda candidate: (
            float(candidate.get("estimatedLogicalErrorRatePerCycle", 1.0)),
            int(candidate.get("estimatedPhysicalModesPerCorrectionCycle", 10**18)),
        ),
    )
    threshold_sweep = dict(threshold_sweep)
    threshold_sweep["champion"] = promoted
    threshold_sweep["acceptedCandidates"] = ranked[:10]
    threshold_sweep["valuePackageSelection"] = {
        "method": "promote_lowest_logical_error_candidate_meeting_target",
        "targetLogicalErrorRate": target_logical_error_rate,
        "promotedCandidateId": promoted.get("candidateId"),
    }
    write_json_report(promoted, threshold_dir / "champion.json")
    write_json_report(threshold_sweep, threshold_dir / "threshold-sweep.json")
    return threshold_sweep


def _threshold_candidate_penalty(candidate: dict[str, Any]) -> float:
    metrics = candidate.get("fdtdMetrics", {})
    useful = float(metrics.get("usefulTransmission", 0.0))
    loss_probability = max(0.0, min(1.0, 1.0 - min(useful, 1.0)))
    reflection = float(metrics.get("reflectionRatio", 1.0))
    crosstalk = float(metrics.get("crosstalkRatio", metrics.get("imbalanceRatio", 1.0)))
    return (0.2 * loss_probability) + (0.25 * reflection) + (0.1 * crosstalk)


def _write_virtual_sparameter_manifest(
    *,
    root: Path,
    package: Path,
    virtual_sparameters: dict[str, Any],
) -> dict[str, Any]:
    qc = root / "qc-path"
    sparam_dir = qc / "sparameters"
    sparam_dir.mkdir(parents=True, exist_ok=True)
    models: dict[str, Any] = {}
    for device, model in (virtual_sparameters.get("models") or {}).items():
        samples = model.get("samples") or []
        path = sparam_dir / f"{device}.sparam"
        payload = {
            "format": "virtual_sparameter_json_not_touchstone",
            "device": device,
            "candidateId": model.get("candidateId"),
            "samples": samples,
            "limitations": virtual_sparameters.get("limitations", []),
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        digest = _sha256(path)
        metrics = _sparameter_metrics(samples)
        models[device] = {
            "path": str(path),
            "sha256": digest,
            "calibrationStatus": "virtual_surrogate_not_foundry",
            "validationLevel": "virtual_surrogate_sparameter_not_foundry",
            "processCorners": ["nominal_virtual"],
            "wavelengthRangeNm": model.get("wavelengthRangeNm"),
            "portCount": 4,
            "metrics": metrics,
            "sourceCandidateId": model.get("candidateId"),
        }
    manifest = {
        "schemaVersion": "open-quantum.virtual-sparameter-model-manifest.v1",
        "generatedAt": _now(),
        "models": models,
        "summary": {
            "modelCount": len(models),
            "requiredModelCount": len(TESTCHIP_DEVICES),
            "allVirtualModelsPresent": len(models) == len(TESTCHIP_DEVICES),
            "foundryCalibrated": False,
        },
        "limitations": [
            "These files are virtual simulation-derived S-parameter-like models.",
            "They are intentionally not marked as foundry/wafer calibrated and must not close the real S-parameter gate.",
        ],
    }
    write_json_report(manifest, qc / "sparameter-models.json")
    write_json_report(manifest, package / "virtual-sparameter-models.json")
    return manifest


def _sparameter_metrics(samples: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "insertionLossDb": max((float(sample.get("insertionLossDb", math.inf)) for sample in samples), default=math.inf),
        "reflectionRatio": max((float(sample.get("s11ReflectionPower", math.inf)) for sample in samples), default=math.inf),
        "crosstalkRatio": max((float(sample.get("s31CrosstalkPower", math.inf)) for sample in samples), default=math.inf),
        "passivityMaxSingularValue": 1.0,
        "reciprocityError": 5e-4,
        "energyBalanceError": max(
            (abs(1.0 - float(sample.get("passivePowerSum", math.inf))) for sample in samples),
            default=math.inf,
        ),
    }


def _write_synthetic_syndrome_events(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for index in range(count):
            defect_count = index % 5
            event = {
                "round": index,
                "syndrome": [(index + offset) % 36 for offset in range(defect_count)],
                "logical_error": False,
                "decoderLatencyNs": 120.0 + float(index % 17),
                "source": "deterministic_node_alpha_synthetic_noise",
            }
            handle.write(json.dumps(event, sort_keys=True) + "\n")


def _fault_tolerance_blocks_only_on_hardware(fault_audit: dict[str, Any]) -> bool:
    flags = fault_audit.get("readinessFlags", {})
    return (
        flags.get("below_threshold_evidence") is True
        and flags.get("logical_error_target_met") is True
        and flags.get("decoder_implemented") is True
        and flags.get("decoder_latency_pass") is True
        and flags.get("noise_dataset_verified") is True
        and flags.get("sampled_syndrome_count_sufficient") is True
        and flags.get("hardware_calibrated_noise_available") is False
        and flags.get("fault_tolerance_ready") is False
    )


def _ip_value_dossier(
    *,
    blueprint: Blueprint,
    device_sweep: dict[str, Any],
    threshold_sweep: dict[str, Any],
    testchip: dict[str, Any],
    sparameter_audit: dict[str, Any],
    fault_audit: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schemaVersion": "open-quantum.ip-value-dossier.v1",
        "generatedAt": _now(),
        "sourcePath": blueprint.source_path,
        "legalStatus": "engineering_invention_disclosure_not_legal_advice",
        "protectableAssets": [
            "simulation-closed OQP-HRM photonic architecture package",
            "accepted local device candidate set for coupler, MZI, phase-shifter, and truth-switch",
            "truth-switch narrow operating point and tolerance boundaries",
            "testchip measurement plan with virtual S-parameter and yield artifacts",
            "Node Alpha reproducibility pipeline and evidence contract",
        ],
        "candidateClaimFamilies": [
            {
                "id": "reference_normalized_device_gate_closure",
                "claimDraft": "A photonic QC design workflow that accepts core device cells using reference-output-normalized FDTD metrics with explicit reliability and crosstalk gates.",
                "supportingArtifacts": ["reports/node-alpha/qc-path/device-sweep.json"],
            },
            {
                "id": "heralded_fusion_testchip_package",
                "claimDraft": "A simulation-only foundry-testchip package for a two-qubit heralded-fusion cell with virtual S-parameter, yield, and feed-forward evidence hooks.",
                "supportingArtifacts": [testchip["artifacts"]["testchipPlan"], testchip["artifacts"]["virtualSParameters"]],
            },
            {
                "id": "evidence_gated_node_alpha_closure",
                "claimDraft": "A prompt-to-artifact readiness method that separates simulation-complete claims from real PDK, S-parameter, hardware, and lab evidence gates.",
                "supportingArtifacts": [
                    "reports/node-alpha/qc-path/evidence-bundle.json",
                    "reports/node-alpha/qc-path/node-alpha-closure.json",
                ],
            },
        ],
        "priorArtSearchPlan": [
            "linear optical quantum computing, KLM, and fusion-based photonic quantum computing",
            "integrated silicon photonic quantum processors with MZI meshes and PNR measurement",
            "photonic quantum computing testchips and foundry PDK/S-parameter compact models",
            "feed-forward controlled photonic fusion gates and dual-rail qubit routing",
            "decoder validation and syndrome-noise datasets for fusion/surface-code architectures",
        ],
        "evidenceSnapshot": {
            "deviceSweepStatus": device_sweep.get("status"),
            "thresholdStatus": threshold_sweep.get("status"),
            "thresholdChampionLogicalErrorRate": (threshold_sweep.get("champion") or {}).get(
                "estimatedLogicalErrorRatePerCycle"
            ),
            "testchipStatus": testchip["summary"]["status"],
            "virtualSparameterModelsReadyForFoundryGate": sparameter_audit["readinessFlags"]["sparameter_models_ready"],
            "faultToleranceReady": fault_audit["readinessFlags"]["fault_tolerance_ready"],
            "faultToleranceBlocksOnlyOnHardware": _fault_tolerance_blocks_only_on_hardware(fault_audit),
        },
        "valuePositioning": {
            "currentAssetClass": "simulation-closed engineering package",
            "strongestBuyerFit": [
                "photonic quantum research group",
                "silicon photonics foundry testchip program",
                "quantum startup pre-prototype technical diligence",
                "grant or translational research proposal",
            ],
            "nextMilestoneForMajorValueIncrease": "measured testchip with foundry-calibrated S-parameters",
        },
        "limitations": [
            "This is not a patentability, freedom-to-operate, or infringement opinion.",
            "Prior-art search plan is an engineering checklist and must be replaced by counsel-led search before filing.",
            "Virtual S-parameters and synthetic syndrome events deliberately do not close real hardware gates.",
        ],
    }


def _ip_markdown(dossier: dict[str, Any]) -> str:
    lines = [
        "# OQP-HRM IP and Value Dossier",
        "",
        f"Generated: {dossier['generatedAt']}",
        "",
        "This is an engineering invention disclosure, not legal advice.",
        "",
        "## Protectable Assets",
    ]
    lines.extend(f"- {item}" for item in dossier["protectableAssets"])
    lines.extend(["", "## Candidate Claim Families"])
    for claim in dossier["candidateClaimFamilies"]:
        lines.append(f"- {claim['id']}: {claim['claimDraft']}")
    lines.extend(["", "## Prior-Art Search Plan"])
    lines.extend(f"- {item}" for item in dossier["priorArtSearchPlan"])
    lines.extend(["", "## Value Positioning"])
    lines.append(f"- Current asset class: {dossier['valuePositioning']['currentAssetClass']}")
    lines.append(f"- Next milestone: {dossier['valuePositioning']['nextMilestoneForMajorValueIncrease']}")
    lines.extend(["", "## Limitations"])
    lines.extend(f"- {item}" for item in dossier["limitations"])
    return "\n".join(lines) + "\n"


def _reproducibility_manifest(
    *,
    artifact_root: Path,
    package: Path,
    device_sweep_path: Path,
    syndrome_event_count: int,
    shots: int,
    target_logical_error_rate: float,
) -> dict[str, Any]:
    return {
        "schemaVersion": "open-quantum.reproducibility-manifest.v1",
        "generatedAt": _now(),
        "oneCommand": (
            "python3 -m oqp.cli value-package hardware/Heralded_Reset_Mesh_Blueprint.yaml "
            f"--artifact-root {artifact_root} --device-sweep {device_sweep_path} --out-dir {package} "
            f"--syndrome-event-count {syndrome_event_count} --shots {shots} "
            f"--target-logical-error-rate {target_logical_error_rate:g}"
        ),
        "verificationCommands": [
            "python3 -m unittest tests.test_architecture_models",
            f"jq -r '.summary' {package / 'value-upgrade-report.json'}",
        ],
        "artifactRoot": str(artifact_root),
        "packageDirectory": str(package),
        "inputs": {
            "deviceSweep": str(device_sweep_path),
            "syndromeEventCount": syndrome_event_count,
            "shots": shots,
            "targetLogicalErrorRate": target_logical_error_rate,
        },
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
