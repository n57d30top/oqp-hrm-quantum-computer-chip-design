"""Prototype-readiness audits for the OQP-HRM quantum-computer path."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .blueprint import Blueprint
from .eigenmode_device import DEVICE_SIMULATION_MODEL_VERSION
from .gds import collect_device_evidence


DEFAULT_QC_PATH = Path("reports/node-alpha/qc-path")
DEFAULT_GDS_PATH = Path("reports/node-alpha/gds-path")
REQUIRED_CORE_DEVICES = ("coupler", "mzi", "phase-shifter", "truth-switch")
CURRENT_DEVICE_SIMULATION_MODEL_VERSION = DEVICE_SIMULATION_MODEL_VERSION


def generate_device_acceptance_audit(
    blueprint: Blueprint,
    *,
    evidence_dir: str | Path | None = DEFAULT_QC_PATH,
    device_reports: list[str | Path] | None = None,
    min_useful_transmission: float = 0.5,
    max_insertion_loss_db: float = 1.0,
    max_reflection_ratio: float = 0.05,
    max_crosstalk_ratio: float = 0.05,
) -> dict[str, Any]:
    evidence = collect_device_evidence(evidence_dir=evidence_dir, device_reports=device_reports)
    device_rows = []
    for device in REQUIRED_CORE_DEVICES:
        report = evidence["byDevice"].get(device)
        device_rows.append(
            _device_acceptance_row(
                device,
                report,
                min_useful_transmission=min_useful_transmission,
                max_insertion_loss_db=max_insertion_loss_db,
                max_reflection_ratio=max_reflection_ratio,
                max_crosstalk_ratio=max_crosstalk_ratio,
            )
        )
    accepted = [row for row in device_rows if row["accepted"]]
    missing = [row for row in device_rows if row["status"] == "missing_evidence"]
    stale = [row for row in device_rows if row["status"] == "stale_simulation_model_evidence"]
    gap_backed = [row for row in device_rows if row["status"] in {"fdtd_gap_backed_placeholder", "stale_simulation_model_evidence"}]
    return {
        "schemaVersion": "open-quantum.device-acceptance-audit.v1",
        "sourcePath": blueprint.source_path,
        "acceptanceTargets": {
            "minUsefulTransmission": min_useful_transmission,
            "maxInsertionLossDb": max_insertion_loss_db,
            "maxReflectionRatio": max_reflection_ratio,
            "maxCrosstalkRatio": max_crosstalk_ratio,
            "requiredValidation": "3D/MPB/FDTD plus foundry-calibrated S-parameters before tapeout promotion",
            "currentSimulationModelVersion": CURRENT_DEVICE_SIMULATION_MODEL_VERSION,
        },
        "deviceEvidence": evidence,
        "devices": device_rows,
        "summary": {
            "requiredDeviceCount": len(REQUIRED_CORE_DEVICES),
            "acceptedDeviceCount": len(accepted),
            "missingEvidenceCount": len(missing),
            "staleEvidenceCount": len(stale),
            "fdtdGapBackedPlaceholderCount": len(gap_backed),
            "allCoreDevicesAccepted": len(accepted) == len(REQUIRED_CORE_DEVICES),
        },
        "readinessFlags": {
            "core_devices_accepted": len(accepted) == len(REQUIRED_CORE_DEVICES),
            "fdtd_gap_backed_placeholder": bool(gap_backed),
            "device_evidence_missing": bool(missing),
            "stale_simulation_model_evidence": bool(stale),
            "s_parameters_missing": True,
            "foundry_calibrated_models_missing": True,
        },
        "blockers": _device_blockers(device_rows),
        "nextExperiments": _device_next_experiments(device_rows),
    }


def generate_prototype_readiness(
    blueprint: Blueprint,
    *,
    artifact_root: str | Path = "reports/node-alpha",
    evidence_dir: str | Path | None = DEFAULT_QC_PATH,
    sparameter_audit_path: str | Path | None = DEFAULT_QC_PATH / "sparameter-audit.json",
    gds_audit_path: str | Path | None = DEFAULT_GDS_PATH / "gds-audit.json",
    pdk_audit_path: str | Path | None = DEFAULT_GDS_PATH / "pdk-audit.json",
    signoff_audit_path: str | Path | None = DEFAULT_GDS_PATH / "signoff-audit.json",
    hardware_audit_path: str | Path | None = DEFAULT_QC_PATH / "hardware-audit.json",
    primitive_demo_audit_path: str | Path | None = DEFAULT_QC_PATH / "primitive-demo-audit.json",
    fault_tolerance_audit_path: str | Path | None = DEFAULT_QC_PATH / "fault-tolerance-audit.json",
    threshold_report_path: str | Path | None = DEFAULT_QC_PATH / "threshold-sweep.json",
    control_report_path: str | Path | None = DEFAULT_QC_PATH / "control-readiness.json",
    lab_report_path: str | Path | None = DEFAULT_QC_PATH / "lab-readiness.json",
    fusion_report_path: str | Path | None = DEFAULT_QC_PATH / "fusion-primitive.json",
) -> dict[str, Any]:
    device_audit = generate_device_acceptance_audit(blueprint, evidence_dir=evidence_dir)
    sparameter_audit = _read_json(sparameter_audit_path)
    gds_audit = _read_json(gds_audit_path)
    pdk_audit = _read_json(pdk_audit_path)
    signoff_audit = _read_json(signoff_audit_path)
    hardware_audit = _read_json(hardware_audit_path)
    primitive_demo_audit = _read_json(primitive_demo_audit_path)
    fault_tolerance_audit = _read_json(fault_tolerance_audit_path)
    threshold = _read_json(threshold_report_path)
    control = _read_json(control_report_path)
    lab = _read_json(lab_report_path)
    fusion = _read_json(fusion_report_path)
    checklist = _prototype_checklist(
        device_audit=device_audit,
        sparameter_audit=sparameter_audit,
        gds_audit=gds_audit,
        pdk_audit=pdk_audit,
        signoff_audit=signoff_audit,
        hardware_audit=hardware_audit,
        primitive_demo_audit=primitive_demo_audit,
        fault_tolerance_audit=fault_tolerance_audit,
        threshold=threshold,
        control=control,
        lab=lab,
        fusion=fusion,
        artifact_root=Path(artifact_root),
    )
    missing = [item for item in checklist if item["status"] != "complete"]
    return {
        "schemaVersion": "open-quantum.prototype-readiness.v1",
        "sourcePath": blueprint.source_path,
        "objective": (
            "Build OQP-HRM from generic-SiPh pre-tapeout GDS into a physically validated, "
            "foundry-ready, experimentally demonstrated photonic quantum-computer prototype."
        ),
        "successCriteria": [
            "accepted MZI, directional-coupler, phase-shifter, and truth-switch devices",
            "real version-locked foundry PDK integration",
            "DRC/LVS-clean GDS",
            "source, detector, packaging, and control hardware path",
            "automatic phase/loss/crosstalk/timing/detector calibration",
            "feed-forward operation",
            "fault-tolerance and decoder path with below-threshold evidence",
            "measured heralded quantum primitive demonstration",
        ],
        "promptToArtifactChecklist": checklist,
        "deviceAcceptance": device_audit,
        "artifactInputs": {
            "deviceEvidenceDir": str(evidence_dir) if evidence_dir else None,
            "sparameterAudit": str(sparameter_audit_path) if sparameter_audit_path else None,
            "gdsAudit": str(gds_audit_path) if gds_audit_path else None,
            "pdkAudit": str(pdk_audit_path) if pdk_audit_path else None,
            "signoffAudit": str(signoff_audit_path) if signoff_audit_path else None,
            "hardwareAudit": str(hardware_audit_path) if hardware_audit_path else None,
            "primitiveDemoAudit": str(primitive_demo_audit_path) if primitive_demo_audit_path else None,
            "faultToleranceAudit": str(fault_tolerance_audit_path) if fault_tolerance_audit_path else None,
            "thresholdReport": str(threshold_report_path) if threshold_report_path else None,
            "controlReadiness": str(control_report_path) if control_report_path else None,
            "labReadiness": str(lab_report_path) if lab_report_path else None,
            "fusionPrimitive": str(fusion_report_path) if fusion_report_path else None,
        },
        "readinessFlags": {
            "prototype_ready": not missing,
            "device_acceptance_ready": device_audit["readinessFlags"]["core_devices_accepted"],
            "sparameter_models_ready": _flag(sparameter_audit, "sparameter_models_ready") is True,
            "foundry_ready": _flag(pdk_audit, "pdk_ready") is True or _flag(gds_audit, "foundry_pdk_missing") is False,
            "drc_lvs_ready": _flag(signoff_audit, "drc_lvs_clean") is True
            or (_flag(gds_audit, "drc_not_run") is False and _flag(gds_audit, "lvs_not_run") is False),
            "hardware_ready": _flag(hardware_audit, "hardware_ready") is True,
            "control_ready": _flag(hardware_audit, "control_hardware_ready") is True
            or bool(control and control.get("controlReady") is True),
            "lab_ready": (
                _flag(hardware_audit, "source_hardware_ready") is True
                and _flag(hardware_audit, "detector_hardware_ready") is True
                and _flag(hardware_audit, "packaging_ready") is True
            )
            or bool(lab and lab.get("labReady") is True),
            "automatic_calibration_ready": _flag(hardware_audit, "automatic_calibration_ready") is True,
            "feed_forward_verified": _flag(hardware_audit, "feed_forward_verified") is True,
            "below_threshold_candidate": _flag(fault_tolerance_audit, "below_threshold_evidence") is True
            or bool(threshold and threshold.get("status") == "below_threshold_candidate_found"),
            "fault_tolerance_ready": _flag(fault_tolerance_audit, "fault_tolerance_ready") is True,
            "primitive_demonstrated": _flag(primitive_demo_audit, "primitive_demonstrated") is True
            or _primitive_demonstrated(fusion),
        },
        "summary": {
            "status": "prototype_ready" if not missing else "not_prototype_ready",
            "completeCriteria": len(checklist) - len(missing),
            "totalCriteria": len(checklist),
            "highestPriorityBlocker": missing[0]["blockers"][0] if missing and missing[0]["blockers"] else None,
        },
        "blockers": [blocker for item in missing for blocker in item["blockers"]],
        "nextMilestones": _next_milestones(missing),
    }


def _device_acceptance_row(
    device: str,
    report: dict[str, Any] | None,
    *,
    min_useful_transmission: float,
    max_insertion_loss_db: float,
    max_reflection_ratio: float,
    max_crosstalk_ratio: float,
) -> dict[str, Any]:
    if not report:
        return {
            "device": device,
            "status": "missing_evidence",
            "accepted": False,
            "evidenceRef": None,
            "metrics": {},
            "gapToAcceptance": {
                "missingEvidence": True,
                "required": "Run eigenmode/3D FDTD and S-parameter extraction for this device.",
            },
            "nextExperiment": f"Run calibrated eigenmode and 3D FDTD sweep for {device}.",
        }
    metrics = report.get("fdtdMetrics", {})
    simulation_model_version = report.get("simulationModelVersion")
    stale_model = simulation_model_version != CURRENT_DEVICE_SIMULATION_MODEL_VERSION
    useful = float(metrics.get("usefulTransmission", float(metrics.get("throughRatio", 0.0)) + float(metrics.get("crossRatio", 0.0))))
    insertion = float(metrics.get("insertionLossDb", math.inf))
    reflection = float(metrics.get("reflectionRatio", math.inf))
    crosstalk = float(metrics.get("crosstalkRatio", metrics.get("imbalanceRatio", 0.0)))
    normalization_reliable = metrics.get("normalizationReliable") is not False
    output_norm = metrics.get("outputPortNormalizationFlux")
    gaps = {
        "normalizationReliable": normalization_reliable,
        "outputPortNormalizationFlux": output_norm,
        "usefulTransmission": useful,
        "usefulTransmissionTarget": min_useful_transmission,
        "usefulTransmissionFactorBelowTarget": min_useful_transmission / max(useful, 1e-18),
        "insertionLossDb": insertion,
        "insertionLossDbTarget": max_insertion_loss_db,
        "insertionLossDbExcess": max(0.0, insertion - max_insertion_loss_db),
        "reflectionRatio": reflection,
        "reflectionRatioTarget": max_reflection_ratio,
        "reflectionRatioExcess": max(0.0, reflection - max_reflection_ratio),
        "crosstalkRatio": crosstalk,
        "crosstalkRatioTarget": max_crosstalk_ratio,
        "crosstalkRatioExcess": max(0.0, crosstalk - max_crosstalk_ratio),
    }
    accepted = (
        useful >= min_useful_transmission
        and insertion <= max_insertion_loss_db
        and reflection <= max_reflection_ratio
        and crosstalk <= max_crosstalk_ratio
        and normalization_reliable
        and report.get("accepted") is True
        and not stale_model
    )
    return {
        "device": device,
        "status": "accepted_device" if accepted else "stale_simulation_model_evidence" if stale_model else "fdtd_gap_backed_placeholder",
        "accepted": accepted,
        "evidenceRef": report.get("sourcePath"),
        "evidenceId": report.get("evidenceId"),
        "acceptanceStatus": report.get("acceptanceStatus"),
        "physicalValidationLevel": report.get("physicalValidationLevel"),
        "simulationModelVersion": simulation_model_version,
        "currentSimulationModelVersion": CURRENT_DEVICE_SIMULATION_MODEL_VERSION,
        "staleSimulationModel": stale_model,
        "metrics": {
            "usefulTransmission": useful,
            "insertionLossDb": insertion,
            "reflectionRatio": reflection,
            "crosstalkRatio": crosstalk,
            "normalizationReliable": normalization_reliable,
            "outputPortNormalizationFlux": output_norm,
        },
        "gapToAcceptance": gaps,
        "nextExperiment": _next_experiment_for_device(device, gaps),
    }


def _device_blockers(rows: list[dict[str, Any]]) -> list[str]:
    blockers = []
    for row in rows:
        if row["accepted"]:
            continue
        if row["status"] == "missing_evidence":
            blockers.append(f"{row['device']}: no accepted device evidence exists.")
            continue
        if row["status"] == "stale_simulation_model_evidence":
            blockers.append(
                f"{row['device']}: evidence was generated with simulation model "
                f"{row.get('simulationModelVersion') or 'unknown'}; rerun with "
                f"{CURRENT_DEVICE_SIMULATION_MODEL_VERSION}."
            )
        gap = row["gapToAcceptance"]
        blockers.extend(_metric_blockers(row["device"], gap))
    blockers.append("No foundry-calibrated S-parameter compact models are attached to core devices.")
    return blockers


def _device_next_experiments(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "device": row["device"],
            "experiment": row["nextExperiment"],
            "evidenceTarget": "accepted_device with S-parameter compact model",
        }
        for row in rows
        if not row["accepted"]
    ]


def _metric_blockers(device: str, gap: dict[str, Any]) -> list[str]:
    blockers = []
    if gap.get("normalizationReliable") is False:
        blockers.append(
            f"{device}: output-port normalization reference is too weak "
            f"({gap.get('outputPortNormalizationFlux')}); rerun with stronger reference transmission or MPB/S-parameter extraction."
        )
    if gap["usefulTransmission"] < gap["usefulTransmissionTarget"]:
        blockers.append(
            f"{device}: useful transmission {gap['usefulTransmission']:.6g} below {gap['usefulTransmissionTarget']}."
        )
    if gap["insertionLossDb"] > gap["insertionLossDbTarget"]:
        blockers.append(
            f"{device}: insertion loss {gap['insertionLossDb']:.3f} dB above {gap['insertionLossDbTarget']} dB target."
        )
    if gap["reflectionRatio"] > gap["reflectionRatioTarget"]:
        blockers.append(
            f"{device}: reflection ratio {gap['reflectionRatio']:.6g} above {gap['reflectionRatioTarget']} target."
        )
    if gap["crosstalkRatio"] > gap["crosstalkRatioTarget"]:
        blockers.append(
            f"{device}: crosstalk/imbalance ratio {gap['crosstalkRatio']:.6g} above {gap['crosstalkRatioTarget']} target."
        )
    return blockers or [f"{device}: evidence did not meet acceptance metadata requirements."]


def _next_experiment_for_device(device: str, gap: dict[str, Any]) -> str:
    if gap.get("missingEvidence"):
        return f"Generate baseline evidence for {device}."
    if gap.get("normalizationReliable") is False:
        return f"Improve {device} reference output-port normalization and extract MPB/S-parameters."
    if gap["usefulTransmission"] < gap["usefulTransmissionTarget"]:
        return (
            f"Rework {device} geometry/source-monitor placement and run 3D/MPB mode extraction; "
            "primary blocker is useful transmission."
        )
    if gap["insertionLossDb"] > gap["insertionLossDbTarget"]:
        return f"Optimize {device} loss with bend/coupler/heater stack sweep and extract S-parameters."
    if gap["reflectionRatio"] > gap["reflectionRatioTarget"]:
        return f"Add taper/termination/reflection sweep for {device}."
    if gap["crosstalkRatio"] > gap["crosstalkRatioTarget"]:
        return f"Optimize {device} coupling balance/crosstalk with S-parameter extraction."
    return f"Promote {device} to foundry-calibrated S-parameter validation."


def _prototype_checklist(
    *,
    device_audit: dict[str, Any],
    sparameter_audit: dict[str, Any] | None,
    gds_audit: dict[str, Any] | None,
    pdk_audit: dict[str, Any] | None,
    signoff_audit: dict[str, Any] | None,
    hardware_audit: dict[str, Any] | None,
    primitive_demo_audit: dict[str, Any] | None,
    fault_tolerance_audit: dict[str, Any] | None,
    threshold: dict[str, Any] | None,
    control: dict[str, Any] | None,
    lab: dict[str, Any] | None,
    fusion: dict[str, Any] | None,
    artifact_root: Path,
) -> list[dict[str, Any]]:
    gds_flags = gds_audit.get("auditFlags", {}) if gds_audit else {}
    pdk_flags = pdk_audit.get("readinessFlags", {}) if pdk_audit else {}
    signoff_flags = signoff_audit.get("readinessFlags", {}) if signoff_audit else {}
    hardware_flags = hardware_audit.get("readinessFlags", {}) if hardware_audit else {}
    return [
        _item(
            "pre_tapeout_gds",
            "Pre-tapeout GDS exists and is layout-computable.",
            bool(gds_flags.get("gds_generated") and gds_flags.get("layout_computable")),
            [str(artifact_root / "gds-path" / "gds-audit.json"), str(artifact_root / "gds-path" / "oqp-hrm-generic-siph.gds")],
            ["Generate GDS bundle with oqp gds-generate."] if not gds_audit else [],
        ),
        _item(
            "core_device_acceptance",
            "MZI, coupler, phase-shifter, and truth-switch devices are accepted with foundry-calibrated S-parameters.",
            bool(
                device_audit["readinessFlags"]["core_devices_accepted"]
                and _flag(sparameter_audit, "sparameter_models_ready") is True
            ),
            _device_evidence_refs(device_audit, artifact_root) + [str(artifact_root / "qc-path" / "sparameter-audit.json")],
            device_audit["blockers"]
            + (
                sparameter_audit.get("blockers", ["Run oqp sparameter-audit with foundry-calibrated core-device models."])
                if sparameter_audit
                else ["Run oqp sparameter-audit with foundry-calibrated core-device models."]
            ),
        ),
        _item(
            "foundry_pdk",
            "Real foundry PDK is selected, installed, and version-locked.",
            bool(pdk_flags.get("pdk_ready") or (gds_audit and gds_flags.get("foundry_pdk_missing") is False)),
            [str(artifact_root / "gds-path" / "pdk-audit.json"), str(artifact_root / "gds-path" / "layer-map.json")],
            pdk_audit.get("blockers", ["Run oqp pdk-audit with a locked foundry PDK manifest."])
            if pdk_audit
            else ["Run oqp pdk-audit with a locked foundry PDK manifest."],
        ),
        _item(
            "drc_lvs",
            "GDS is DRC-clean and LVS-clean.",
            bool(
                signoff_flags.get("drc_lvs_clean")
                or (gds_audit and gds_flags.get("drc_not_run") is False and gds_flags.get("lvs_not_run") is False)
            ),
            [
                str(artifact_root / "gds-path" / "gds-audit.json"),
                str(artifact_root / "gds-path" / "pdk-audit.json"),
                str(artifact_root / "gds-path" / "signoff-audit.json"),
            ],
            signoff_audit.get("blockers", ["Run oqp signoff-audit with DRC/LVS reports."])
            if signoff_audit
            else (
                ["Run foundry DRC/LVS and persist clean reports or approved waivers."]
                if pdk_flags.get("drc_lvs_runnable")
                else ["Complete pdk-audit until DRC/LVS is runnable, then run signoff-audit with DRC/LVS reports."]
            ),
        ),
        _item(
            "source_detector_packaging",
            "Source, detector, fiber/edge-coupler, probe-card, and package path are real.",
            bool(
                hardware_flags.get("source_hardware_ready")
                and hardware_flags.get("detector_hardware_ready")
                and hardware_flags.get("packaging_ready")
            )
            or bool(lab and lab.get("labReady") is True),
            [str(artifact_root / "qc-path" / "hardware-audit.json"), str(artifact_root / "qc-path" / "lab-readiness.json")],
            _hardware_blockers(hardware_audit, ["source_hardware", "detector_hardware", "packaging"])
            if hardware_audit
            else lab.get("blockers", ["Run oqp hardware-audit with source, detector, and packaging reports."])
            if lab
            else ["Run oqp hardware-audit with source, detector, and packaging reports."],
        ),
        _item(
            "control_feed_forward",
            "Control electronics and feed-forward operation are hardware-verified.",
            bool(hardware_flags.get("control_hardware_ready") and hardware_flags.get("feed_forward_verified"))
            or bool(control and control.get("controlReady") is True),
            [str(artifact_root / "qc-path" / "hardware-audit.json"), str(artifact_root / "qc-path" / "control-readiness.json")],
            _hardware_blockers(hardware_audit, ["control_hardware", "feed_forward"])
            if hardware_audit
            else control.get("blockers", ["Run oqp hardware-audit with control and feed-forward reports."])
            if control
            else ["Run oqp hardware-audit with control and feed-forward reports."],
        ),
        _item(
            "automatic_calibration",
            "Automatic phase/loss/crosstalk/timing/detector calibration is implemented.",
            bool(hardware_flags.get("automatic_calibration_ready"))
            or bool(lab and lab.get("labReady") is True and control and control.get("controlReady") is True),
            [
                str(artifact_root / "qc-path" / "hardware-audit.json"),
                str(artifact_root / "qc-path" / "lab-readiness.json"),
                str(artifact_root / "qc-path" / "control-readiness.json"),
            ],
            _hardware_blockers(hardware_audit, ["calibration"])
            if hardware_audit
            else ["Implement calibration automation for phase, loss, crosstalk, detector timing, and source indistinguishability."],
        ),
        _item(
            "fault_tolerance",
            "Error-correction path has below-threshold evidence and decoder interface.",
            bool(_flag(fault_tolerance_audit, "fault_tolerance_ready") is True),
            [str(artifact_root / "qc-path" / "fault-tolerance-audit.json"), str(artifact_root / "qc-path" / "threshold-sweep.json")],
            fault_tolerance_audit.get("blockers", ["Run oqp fault-tolerance-audit with decoder and sampled-noise evidence."])
            if fault_tolerance_audit
            else threshold.get("blockers", ["Run oqp fault-tolerance-audit with decoder and sampled-noise evidence."])
            if threshold
            else ["Run oqp fault-tolerance-audit with threshold, decoder, and sampled-noise evidence."],
        ),
        _item(
            "heralded_primitive_demo",
            "A heralded quantum primitive has been experimentally demonstrated.",
            bool(_flag(primitive_demo_audit, "primitive_demonstrated") is True or _primitive_demonstrated(fusion)),
            [str(artifact_root / "qc-path" / "primitive-demo-audit.json"), str(artifact_root / "qc-path" / "fusion-primitive.json")],
            primitive_demo_audit.get("blockers", ["Run oqp primitive-demo-audit with measured primitive evidence."])
            if primitive_demo_audit
            else fusion.get("blockers", ["Run oqp primitive-demo-audit with measured primitive evidence."])
            if fusion
            else ["Run oqp primitive-demo-audit with measured primitive evidence."],
        ),
    ]


def _item(
    item_id: str,
    requirement: str,
    complete: bool,
    evidence_refs: list[str],
    blockers: list[str],
) -> dict[str, Any]:
    return {
        "id": item_id,
        "requirement": requirement,
        "status": "complete" if complete else "missing",
        "evidenceRefs": evidence_refs,
        "blockers": [] if complete else blockers,
    }


def _device_evidence_refs(device_audit: dict[str, Any], artifact_root: Path) -> list[str]:
    refs = []
    for row in device_audit.get("devices", []):
        if not isinstance(row, dict):
            continue
        ref = row.get("evidenceRef")
        if isinstance(ref, str) and ref and ref not in refs:
            refs.append(ref)
    return refs or [str(artifact_root / "qc-path" / "device-sweep.json")]


def _hardware_blockers(hardware_audit: dict[str, Any] | None, prefixes: list[str]) -> list[str]:
    if not hardware_audit:
        return ["Run oqp hardware-audit with source, detector, packaging, control, calibration, and feed-forward reports."]
    blockers = []
    for blocker in hardware_audit.get("blockers", []):
        if any(str(blocker).startswith(prefix) for prefix in prefixes):
            blockers.append(blocker)
    return blockers or ["Hardware audit did not satisfy this readiness gate."]


def _next_milestones(missing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "criterion": item["id"],
            "milestone": item["blockers"][0] if item["blockers"] else "Collect missing evidence.",
            "evidenceToProduce": item["evidenceRefs"],
        }
        for item in missing[:8]
    ]


def _read_json(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    target = Path(path)
    if not target.is_file():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _flag(report: dict[str, Any] | None, name: str) -> bool | None:
    if not report:
        return None
    flags = report.get("auditFlags") or report.get("readinessFlags")
    if isinstance(flags, dict) and name in flags:
        return bool(flags[name])
    return None


def _primitive_demonstrated(fusion: dict[str, Any] | None) -> bool:
    if not fusion:
        return False
    return bool(
        fusion.get("experimentalStatus") == "measured"
        or fusion.get("status") == "experimentally_demonstrated"
        or fusion.get("readinessFlags", {}).get("experimentallyDemonstrated") is True
    )
