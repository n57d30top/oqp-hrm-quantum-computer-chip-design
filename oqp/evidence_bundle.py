"""Evidence-bundle intake contract for OQP-HRM prototype readiness."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .blueprint import Blueprint


SCHEMA_PREFIX = "open-quantum"
DEFAULT_ARTIFACT_ROOT = Path("reports/node-alpha")


def generate_evidence_bundle(
    blueprint: Blueprint,
    *,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
    write_templates: bool = False,
    templates_dir: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(artifact_root)
    artifacts = [_artifact_report(definition) for definition in _artifact_definitions(root)]
    by_id = {artifact["id"]: artifact for artifact in artifacts}
    reports = {artifact["id"]: artifact["json"] for artifact in artifacts if isinstance(artifact.get("json"), dict)}
    requirements = _requirement_reports(by_id, reports)
    missing = [artifact for artifact in artifacts if not artifact["present"]]
    hash_gaps = [
        artifact
        for artifact in artifacts
        if artifact.get("hashRequired") and artifact.get("contentHashVerified") is not True
    ]
    incomplete = [requirement for requirement in requirements if requirement["status"] != "complete"]
    template_outputs = _write_templates(root, templates_dir) if write_templates else []
    flags = {
        "evidence_bundle_computable": True,
        "required_artifacts_present": not missing,
        "hash_verified_datasets": not hash_gaps,
        "prototype_evidence_complete": not missing and not hash_gaps and not incomplete,
    }
    blockers = (
        [f"missing_artifact: {artifact['id']} at {artifact['path']}." for artifact in missing]
        + [
            f"hash_gap: {artifact['id']} manifest is missing a verified dataset hash."
            for artifact in hash_gaps
        ]
        + [
            f"requirement_gap: {requirement['id']} is {requirement['status']}."
            for requirement in incomplete
        ]
    )
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.evidence-bundle.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "artifactRoot": str(root),
        "readinessFlags": flags,
        "summary": {
            "requiredArtifactCount": len(artifacts),
            "presentArtifactCount": len(artifacts) - len(missing),
            "missingArtifactCount": len(missing),
            "hashGapCount": len(hash_gaps),
            "completeRequirementCount": len(requirements) - len(incomplete),
            "totalRequirementCount": len(requirements),
        },
        "requirements": requirements,
        "artifacts": _strip_internal_json(artifacts),
        "templateOutputs": template_outputs,
        "blockers": blockers,
        "nextSteps": _next_steps(missing, hash_gaps, incomplete),
    }


def _artifact_definitions(root: Path) -> list[dict[str, Any]]:
    gds = root / "gds-path"
    qc = root / "qc-path"
    return [
        _artifact("gds_file", gds / "oqp-hrm-generic-siph.gds", "layout", "oqp gds-generate"),
        _artifact("gds_audit", gds / "gds-audit.json", "layout", "oqp gds-audit"),
        _artifact("foundry_pdk_manifest", gds / "foundry-pdk-manifest.json", "foundry", "oqp pdk-audit --pdk-manifest"),
        _artifact("pdk_audit", gds / "pdk-audit.json", "foundry", "oqp pdk-audit"),
        _artifact("signoff_audit", gds / "signoff-audit.json", "signoff", "oqp signoff-audit"),
        _artifact("device_acceptance_audit", qc / "device-acceptance-audit.json", "device", "oqp device-acceptance"),
        _artifact("sparameter_models", qc / "sparameter-models.json", "device", "oqp sparameter-audit"),
        _artifact("sparameter_audit", qc / "sparameter-audit.json", "device", "oqp sparameter-audit"),
        _artifact("source_hardware", qc / "source-hardware.json", "hardware", "oqp hardware-ingest"),
        _artifact("detector_hardware", qc / "detector-hardware.json", "hardware", "oqp hardware-ingest"),
        _artifact("packaging_plan", qc / "packaging-plan.json", "hardware", "oqp hardware-ingest"),
        _artifact("control_hardware", qc / "control-hardware.json", "hardware", "oqp hardware-ingest"),
        _artifact("calibration_report", qc / "calibration-report.json", "hardware", "oqp hardware-ingest"),
        _artifact("feed_forward_report", qc / "feed-forward-report.json", "hardware", "oqp hardware-ingest"),
        _artifact("hardware_audit", qc / "hardware-audit.json", "hardware", "oqp hardware-audit"),
        _artifact("threshold_sweep", qc / "threshold-sweep.json", "fault_tolerance", "oqp threshold-sweep"),
        _artifact("decoder_report", qc / "decoder-report.json", "fault_tolerance", "oqp fault-tolerance-ingest"),
        _artifact(
            "syndrome_noise_dataset",
            qc / "syndrome-noise-dataset.json",
            "fault_tolerance",
            "oqp fault-tolerance-ingest",
            hash_required=True,
        ),
        _artifact("fault_tolerance_audit", qc / "fault-tolerance-audit.json", "fault_tolerance", "oqp fault-tolerance-audit"),
        _artifact("fusion_primitive", qc / "fusion-primitive.json", "primitive_demo", "oqp fusion-primitive"),
        _artifact("primitive_demo_measurement", qc / "primitive-demo-measurement.json", "primitive_demo", "oqp primitive-demo-ingest"),
        _artifact(
            "primitive_demo_dataset",
            qc / "primitive-demo-dataset.json",
            "primitive_demo",
            "oqp primitive-demo-ingest",
            hash_required=True,
        ),
        _artifact("primitive_demo_audit", qc / "primitive-demo-audit.json", "primitive_demo", "oqp primitive-demo-audit"),
        _artifact("prototype_readiness", qc / "prototype-readiness.json", "prototype", "oqp prototype-readiness"),
    ]


def _artifact(id_: str, path: Path, group: str, producer: str, *, hash_required: bool = False) -> dict[str, Any]:
    return {
        "id": id_,
        "path": path,
        "group": group,
        "producerCommand": producer,
        "hashRequired": hash_required,
    }


def _artifact_report(definition: dict[str, Any]) -> dict[str, Any]:
    path = Path(definition["path"])
    raw = _read_json(path) if path.suffix == ".json" else {}
    hash_status = _manifest_hash_status(raw) if definition.get("hashRequired") else {}
    return {
        "id": definition["id"],
        "path": str(path),
        "group": definition["group"],
        "producerCommand": definition["producerCommand"],
        "present": path.is_file(),
        "schemaVersion": raw.get("schemaVersion") if raw else None,
        "status": raw.get("status") if raw else None,
        "readinessFlags": raw.get("readinessFlags") if isinstance(raw.get("readinessFlags"), dict) else None,
        "auditFlags": raw.get("auditFlags") if isinstance(raw.get("auditFlags"), dict) else None,
        "hashRequired": bool(definition.get("hashRequired")),
        "contentHashVerified": hash_status.get("verified"),
        "contentPath": hash_status.get("path"),
        "contentSha256": hash_status.get("sha256"),
        "actualContentSha256": hash_status.get("actualSha256"),
        "json": raw,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _manifest_hash_status(raw: dict[str, Any]) -> dict[str, Any]:
    path = raw.get("path") if raw else None
    expected_hash = raw.get("sha256") if raw else None
    target = Path(path) if path else None
    if not target or not target.is_file():
        return {"path": str(path) if path else None, "sha256": expected_hash, "actualSha256": None, "verified": False}
    actual = _sha256(target)
    return {
        "path": str(path),
        "sha256": expected_hash,
        "actualSha256": actual,
        "verified": bool(expected_hash and actual == expected_hash),
    }


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _requirement_reports(by_id: dict[str, dict[str, Any]], reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _requirement(
            "core_device_models",
            "Accepted MZI, directional-coupler, phase-shifter, and truth-switch devices plus S-parameter models.",
            ("device_acceptance_audit", "sparameter_models", "sparameter_audit"),
            (
                _flag(reports.get("device_acceptance_audit"), "core_devices_accepted"),
                _flag(reports.get("sparameter_audit"), "sparameter_models_ready"),
            ),
            by_id,
            reports,
        ),
        _requirement(
            "foundry_pdk",
            "Real version-locked foundry PDK integration.",
            ("foundry_pdk_manifest", "pdk_audit"),
            (_flag(reports.get("pdk_audit"), "pdk_ready"),),
            by_id,
            reports,
        ),
        _requirement(
            "drc_lvs_clean_gds",
            "DRC/LVS-clean GDS signoff evidence.",
            ("gds_file", "gds_audit", "pdk_audit", "signoff_audit"),
            (_flag(reports.get("signoff_audit"), "drc_lvs_clean"), _flag(reports.get("signoff_audit"), "signoff_ready")),
            by_id,
            reports,
        ),
        _requirement(
            "hardware_chain",
            "Source, detector, packaging, and control hardware path.",
            (
                "source_hardware",
                "detector_hardware",
                "packaging_plan",
                "control_hardware",
                "hardware_audit",
            ),
            (_flag(reports.get("hardware_audit"), "hardware_ready"),),
            by_id,
            reports,
        ),
        _requirement(
            "automatic_calibration",
            "Automatic phase, loss, crosstalk, detector timing, source, and switch-latency calibration.",
            ("calibration_report", "hardware_audit"),
            (_flag(reports.get("hardware_audit"), "automatic_calibration_ready"),),
            by_id,
            reports,
        ),
        _requirement(
            "feed_forward_operation",
            "Measured feed-forward operation.",
            ("feed_forward_report", "hardware_audit"),
            (_flag(reports.get("hardware_audit"), "feed_forward_verified"),),
            by_id,
            reports,
        ),
        _requirement(
            "fault_tolerance_path",
            "Fault-tolerance and decoder path with below-threshold and sampled-noise evidence.",
            ("threshold_sweep", "decoder_report", "syndrome_noise_dataset", "fault_tolerance_audit"),
            (_flag(reports.get("fault_tolerance_audit"), "fault_tolerance_ready"),),
            by_id,
            reports,
        ),
        _requirement(
            "heralded_primitive_demo",
            "Measured heralded quantum primitive demonstration.",
            (
                "fusion_primitive",
                "primitive_demo_measurement",
                "primitive_demo_dataset",
                "primitive_demo_audit",
            ),
            (_flag(reports.get("primitive_demo_audit"), "primitive_demonstrated"),),
            by_id,
            reports,
        ),
        _requirement(
            "prototype_gate",
            "All prototype-readiness success criteria closed.",
            ("prototype_readiness",),
            (_flag(reports.get("prototype_readiness"), "prototype_ready"),),
            by_id,
            reports,
        ),
    ]


def _requirement(
    id_: str,
    description: str,
    artifact_ids: tuple[str, ...],
    flag_values: tuple[bool | None, ...],
    by_id: dict[str, dict[str, Any]],
    reports: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    missing = [artifact_id for artifact_id in artifact_ids if not by_id.get(artifact_id, {}).get("present")]
    hash_gaps = [
        artifact_id
        for artifact_id in artifact_ids
        if by_id.get(artifact_id, {}).get("hashRequired") and by_id.get(artifact_id, {}).get("contentHashVerified") is not True
    ]
    false_flags = [value for value in flag_values if value is not True]
    status = "complete" if not missing and not hash_gaps and not false_flags else "blocked"
    blockers = []
    if missing:
        blockers.append(f"missing artifacts: {missing}")
    if hash_gaps:
        blockers.append(f"hash verification gaps: {hash_gaps}")
    if false_flags:
        blockers.extend(_report_blockers(reports, artifact_ids))
        if not blockers or all(blocker.startswith("missing artifacts") for blocker in blockers):
            blockers.append("required audit readiness flags are not true.")
    return {
        "id": id_,
        "description": description,
        "status": status,
        "artifactIds": list(artifact_ids),
        "auditFlagsPass": not false_flags,
        "blockers": blockers,
    }


def _flag(report: dict[str, Any] | None, name: str) -> bool | None:
    if not report:
        return None
    readiness = report.get("readinessFlags")
    if isinstance(readiness, dict) and name in readiness:
        return bool(readiness[name])
    audit = report.get("auditFlags")
    if isinstance(audit, dict) and name in audit:
        return bool(audit[name])
    return None


def _report_blockers(reports: dict[str, dict[str, Any]], artifact_ids: tuple[str, ...]) -> list[str]:
    blockers: list[str] = []
    for artifact_id in artifact_ids:
        report = reports.get(artifact_id)
        raw = report.get("blockers") if report else None
        if isinstance(raw, list):
            blockers.extend(str(item) for item in raw[:5])
    return blockers


def _strip_internal_json(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stripped = []
    for artifact in artifacts:
        public = {key: value for key, value in artifact.items() if key != "json"}
        stripped.append(public)
    return stripped


def _write_templates(root: Path, templates_dir: str | Path | None) -> list[dict[str, str]]:
    target = Path(templates_dir) if templates_dir else root / "evidence-intake" / "templates"
    target.mkdir(parents=True, exist_ok=True)
    outputs = []
    for name, payload in _templates(root).items():
        path = target / name
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        outputs.append({"path": str(path), "template": name})
    return outputs


def _templates(root: Path) -> dict[str, dict[str, Any]]:
    gds = root / "gds-path"
    qc = root / "qc-path"
    return {
        "foundry-pdk-manifest.template.json": {
            "schemaVersion": f"{SCHEMA_PREFIX}.pdk-manifest.v1",
            "status": "template_not_evidence",
            "foundryPdkLocked": False,
            "foundry": "replace-with-foundry-name",
            "pdkName": "replace-with-version-locked-pdk-name",
            "process": "replace-with-process",
            "layerMap": [
                {"purpose": "waveguide", "layer": [1, 0]},
                {"purpose": "etch", "layer": [2, 0]},
                {"purpose": "metal", "layer": [10, 0]},
                {"purpose": "pad", "layer": [11, 0]},
                {"purpose": "port", "layer": [90, 0]},
                {"purpose": "label", "layer": [91, 0]},
                {"purpose": "keepout", "layer": [99, 0]},
            ],
            "ruleDecks": {"drc": "replace-with-drc-deck-path", "lvs": "replace-with-lvs-deck-path"},
            "processCorners": [{"name": "tt"}],
            "pcellLibrary": "replace-with-pcell-library-path",
            "compactModels": {
                device: str(qc / "sparameters" / f"{device}.sparam")
                for device in ("coupler", "mzi", "phase-shifter", "truth-switch")
            },
            "packageRules": {
                "fiberArray": False,
                "edgeCoupler": False,
                "padOpening": False,
                "thermalKeepout": False,
                "probeCard": False,
            },
        },
        "sparameter-models.template.json": {
            "schemaVersion": f"{SCHEMA_PREFIX}.sparameter-model-manifest.v1",
            "status": "template_not_evidence",
            "models": {
                device: {
                    "path": str(qc / "sparameters" / f"{device}.sparam"),
                    "sha256": "replace-with-file-sha256",
                    "calibrationStatus": "foundry_calibrated",
                    "validationLevel": "3d_mpb_sparameter",
                    "processCorners": ["tt", "ff", "ss"],
                    "wavelengthRangeNm": [1520.0, 1580.0],
                    "portCount": 4,
                    "metrics": {
                        "insertionLossDb": 0.0,
                        "reflectionRatio": 0.0,
                        "crosstalkRatio": 0.0,
                        "passivityMaxSingularValue": 1.0,
                        "reciprocityError": 0.0,
                        "energyBalanceError": 0.0,
                    },
                }
                for device in ("coupler", "mzi", "phase-shifter", "truth-switch")
            },
        },
        "source-hardware.template.json": {
            "status": "measured",
            "sourceCount": 0,
            "brightness": 0.0,
            "indistinguishability": 0.0,
            "multiphotonProbability": 1.0,
        },
        "detector-hardware.template.json": {
            "status": "measured",
            "detectorCount": 0,
            "efficiency": 0.0,
            "darkCountHz": 1e18,
            "timingJitterPs": 1e18,
            "photonNumberResolving": False,
        },
        "packaging-plan.template.json": {
            "status": "template_not_evidence",
            "fiberPlanLocked": False,
            "edgeCouplerPlanLocked": False,
            "probeCardLocked": False,
            "thermalPlanLocked": False,
            "packageDrawingReleased": False,
            "opticalPortCount": 0,
            "electricalPadCount": 0,
        },
        "control-hardware.template.json": {
            "status": "template_not_evidence",
            "timingFabric": "fpga",
            "tdcChannels": 0,
            "detectorReadoutChannels": 0,
            "phaseDriverChannels": 0,
            "switchDriverChannels": 0,
            "dacResolutionBits": 0,
            "clockJitterPs": 1e18,
        },
        "calibration-report.template.json": {
            "status": "complete",
            "completedCalibrations": {
                "phase": False,
                "loss": False,
                "crosstalk": False,
                "detector_timing": False,
                "source_indistinguishability": False,
                "switch_latency": False,
            },
        },
        "feed-forward-report.template.json": {
            "status": "verified",
            "measuredLatencyNs": 1e18,
            "measuredJitterPs": 1e18,
            "hardwareInLoopShots": 0,
        },
        "hardware-events.template.json": {
            "schemaVersion": f"{SCHEMA_PREFIX}.hardware-events.v1",
            "events": [
                {
                    "category": "source",
                    "status": "measured",
                    "sourceCount": 0,
                    "brightness": 0.0,
                    "indistinguishability": 0.0,
                    "multiphotonProbability": 1.0,
                },
                {
                    "category": "detector",
                    "status": "measured",
                    "detectorCount": 0,
                    "efficiency": 0.0,
                    "darkCountHz": 1e18,
                    "timingJitterPs": 1e18,
                    "photonNumberResolving": False,
                },
                {
                    "category": "packaging",
                    "status": "locked",
                    "fiberPlanLocked": False,
                    "edgeCouplerPlanLocked": False,
                    "probeCardLocked": False,
                    "thermalPlanLocked": False,
                    "packageDrawingReleased": False,
                    "opticalPortCount": 0,
                    "electricalPadCount": 0,
                },
                {
                    "category": "control",
                    "status": "measured",
                    "timingFabric": "fpga",
                    "tdcChannels": 0,
                    "detectorReadoutChannels": 0,
                    "phaseDriverChannels": 0,
                    "switchDriverChannels": 0,
                    "dacResolutionBits": 0,
                    "clockJitterPs": 1e18,
                },
                {
                    "category": "calibration",
                    "status": "complete",
                    "completedCalibrations": {
                        "phase": False,
                        "loss": False,
                        "crosstalk": False,
                        "detector_timing": False,
                        "source_indistinguishability": False,
                        "switch_latency": False,
                    },
                },
                {
                    "category": "feed_forward",
                    "status": "verified",
                    "measuredLatencyNs": 1e18,
                    "measuredJitterPs": 1e18,
                    "hardwareInLoopShots": 0,
                },
            ],
        },
        "decoder-report.template.json": {
            "decoder": "replace-with-decoder-name",
            "implementationStatus": "validated",
            "measuredLatencyNs": 1e18,
            "validatedLogicalErrorRate": 1.0,
            "sampledSyndromeEvents": 0,
        },
        "syndrome-noise-dataset.template.json": {
            "path": str(qc / "syndrome-events.jsonl"),
            "sha256": "replace-with-dataset-sha256",
            "recordCount": 0,
        },
        "primitive-demo-measurement.template.json": {
            "primitive": "two_qubit_heralded_fusion",
            "experimentalStatus": "measured",
            "shotCount": 0,
            "heraldedEventCount": 0,
            "measuredHeraldingSuccessProbability": 0.0,
            "measuredProcessFidelity": 0.0,
            "processFidelityUncertainty": 1.0,
            "measuredFeedForwardLatencyNs": 1e18,
        },
        "primitive-demo-dataset.template.json": {
            "path": str(qc / "primitive-events.jsonl"),
            "sha256": "replace-with-dataset-sha256",
            "recordCount": 0,
        },
        "command-plan.template.json": {
            "commands": [
                f"oqp gds-generate <blueprint> --out-dir {gds}",
                f"oqp pdk-audit <blueprint> --pdk-manifest {gds / 'foundry-pdk-manifest.json'} --out {gds / 'pdk-audit.json'}",
                f"oqp signoff-audit <blueprint> --out {gds / 'signoff-audit.json'}",
                f"oqp sparameter-audit <blueprint> --model-manifest {qc / 'sparameter-models.json'} --out {qc / 'sparameter-audit.json'}",
                f"oqp hardware-ingest <blueprint> --dataset {qc / 'hardware-events.jsonl'}",
                f"oqp hardware-audit <blueprint> --out {qc / 'hardware-audit.json'}",
                f"oqp fault-tolerance-ingest <blueprint> --dataset {qc / 'syndrome-events.jsonl'}",
                f"oqp fault-tolerance-audit <blueprint> --out {qc / 'fault-tolerance-audit.json'}",
                f"oqp primitive-demo-ingest <blueprint> --dataset {qc / 'primitive-events.jsonl'}",
                f"oqp primitive-demo-audit <blueprint> --out {qc / 'primitive-demo-audit.json'}",
                f"oqp prototype-readiness <blueprint> --artifact-root {root} --out {qc / 'prototype-readiness.json'}",
            ]
        },
    }


def _next_steps(
    missing: list[dict[str, Any]],
    hash_gaps: list[dict[str, Any]],
    incomplete: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for artifact in missing[:12]:
        steps.append(
            {
                "action": "produce_artifact",
                "artifactId": artifact["id"],
                "path": artifact["path"],
                "command": artifact["producerCommand"],
            }
        )
    for artifact in hash_gaps[:4]:
        steps.append(
            {
                "action": "verify_dataset_hash",
                "artifactId": artifact["id"],
                "path": artifact["path"],
            }
        )
    for requirement in incomplete[:8]:
        steps.append(
            {
                "action": "close_requirement",
                "requirementId": requirement["id"],
                "blockers": requirement["blockers"],
            }
        )
    return steps
