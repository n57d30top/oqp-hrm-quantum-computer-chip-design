"""Node Alpha closure report for simulation-only OQP-HRM completion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .blueprint import Blueprint
from .design_dossier import generate_design_dossier


def generate_node_alpha_closure(
    blueprint: Blueprint,
    *,
    artifact_root: str | Path = "reports/node-alpha",
) -> dict[str, Any]:
    """Audit everything that can be completed without real-world evidence."""

    root = Path(artifact_root)
    qc = root / "qc-path"
    gds = root / "gds-path"
    dossier = _read_json(qc / "complete-design-dossier.json") or generate_design_dossier(
        blueprint,
        artifact_root=root,
    )
    prototype = _read_json(qc / "prototype-readiness.json")
    evidence = _read_json(qc / "evidence-bundle.json")
    device_acceptance = _read_json(qc / "device-acceptance-audit.json")
    gds_audit = _read_json(gds / "gds-audit.json")
    local_items = _local_items(
        root=root,
        dossier=dossier,
        prototype=prototype,
        evidence=evidence,
        device_acceptance=device_acceptance,
        gds_audit=gds_audit,
    )
    hard_stops = _hard_stops(prototype=prototype, evidence=evidence)
    open_local = [item for item in local_items if item["status"] != "complete"]
    return {
        "schemaVersion": "open-quantum.node-alpha-closure.v1",
        "sourcePath": blueprint.source_path,
        "scope": {
            "node": "node-alpha",
            "allowedInputs": [
                "repository code",
                "local simulations",
                "generated GDS/JSON/SVG artifacts",
                "synthetic test fixtures marked as non-evidence",
            ],
            "excludedInputs": [
                "foundry PDKs and proprietary rule decks",
                "wafer-calibrated S-parameters",
                "DRC/LVS signoff reports",
                "measured source, detector, package, and control hardware reports",
                "hardware-in-the-loop calibration and feed-forward measurements",
                "lab primitive datasets",
            ],
        },
        "localCompletionChecklist": local_items,
        "readinessFlags": {
            "node_alpha_maxed_without_realworld_input": not open_local,
            "architecture_dossier_complete": _flag(dossier, "architecture_dossier_complete"),
            "pre_tapeout_gds_complete": _gds_complete(gds_audit),
            "core_device_gap_quantified": _device_gap_quantified(device_acceptance),
            "prototype_ready": _flag(dossier, "prototype_ready"),
            "complete_quantum_computer": all(
                _flag(dossier, name)
                for name in (
                    "prototype_ready",
                    "tapeout_ready",
                    "hardware_evidence_complete",
                    "fault_tolerance_ready",
                    "experimental_primitive_demonstrated",
                )
            ),
        },
        "summary": {
            "status": "node_alpha_maxed" if not open_local else "node_alpha_open",
            "completeLocalItemCount": len(local_items) - len(open_local),
            "totalLocalItemCount": len(local_items),
            "prototypeCriteriaComplete": (prototype or {}).get("summary", {}).get("completeCriteria"),
            "prototypeCriteriaTotal": (prototype or {}).get("summary", {}).get("totalCriteria"),
            "evidenceRequirementsComplete": (evidence or {}).get("summary", {}).get("completeRequirementCount"),
            "evidenceRequirementsTotal": (evidence or {}).get("summary", {}).get("totalRequirementCount"),
        },
        "hardStopsRequiringRealWorldInput": hard_stops,
        "blockers": [blocker for item in open_local for blocker in item["blockers"]],
        "nextExternalEvidence": _next_external_evidence(hard_stops),
        "completionRule": (
            "Node Alpha is maxed when all localCompletionChecklist items are complete. "
            "Prototype or complete-quantum-computer readiness still requires the hard-stop evidence listed here."
        ),
    }


def _local_items(
    *,
    root: Path,
    dossier: dict[str, Any] | None,
    prototype: dict[str, Any] | None,
    evidence: dict[str, Any] | None,
    device_acceptance: dict[str, Any] | None,
    gds_audit: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    qc = root / "qc-path"
    gds = root / "gds-path"
    return [
        _item(
            "architecture_dossier",
            "Full stack architecture dossier generated and closed.",
            _flag(dossier, "architecture_dossier_complete"),
            [qc / "complete-design-dossier.json"],
            ["Run oqp design-dossier."],
        ),
        _item(
            "generic_pre_tapeout_gds",
            "Generic SiPh GDS, manifest, preview, and audit exist.",
            _gds_complete(gds_audit)
            and (gds / "oqp-hrm-generic-siph.gds").is_file()
            and (gds / "gds-manifest.json").is_file(),
            [gds / "oqp-hrm-generic-siph.gds", gds / "gds-manifest.json", gds / "gds-audit.json"],
            ["Run oqp gds-generate, oqp gds-manifest, and oqp gds-audit."],
        ),
        _item(
            "core_device_gap_quantification",
            "All required core devices have current non-stale local simulation evidence and quantified gaps.",
            _device_gap_quantified(device_acceptance),
            [qc / "device-acceptance-audit.json"],
            ["Run high-resolution device sweep/rerank and oqp device-acceptance."],
        ),
        _item(
            "negative_foundry_signoff_gates",
            "PDK, S-parameter, and signoff audits exist and correctly block without real foundry inputs.",
            (gds / "pdk-audit.json").is_file()
            and (gds / "signoff-audit.json").is_file()
            and (qc / "sparameter-audit.json").is_file(),
            [gds / "pdk-audit.json", gds / "signoff-audit.json", qc / "sparameter-audit.json"],
            ["Run oqp pdk-audit, oqp signoff-audit, and oqp sparameter-audit."],
        ),
        _item(
            "negative_hardware_and_lab_gates",
            "Hardware, primitive-demo, and fault-tolerance audits exist and correctly block without measured datasets.",
            (qc / "hardware-audit.json").is_file()
            and (qc / "fault-tolerance-audit.json").is_file()
            and (qc / "primitive-demo-audit.json").is_file(),
            [qc / "hardware-audit.json", qc / "fault-tolerance-audit.json", qc / "primitive-demo-audit.json"],
            ["Run oqp hardware-audit, oqp fault-tolerance-audit, and oqp primitive-demo-audit."],
        ),
        _item(
            "simulation_models",
            "Compiler, runtime, resource, threshold, primitive, and error-budget reports exist.",
            all(
                (qc / name).is_file()
                for name in (
                    "compiler-trace.json",
                    "runtime-trace.json",
                    "resource-model.json",
                    "threshold-sweep.json",
                    "primitive-spec.json",
                    "fusion-primitive.json",
                    "error-budget.json",
                )
            ),
            [
                qc / "compiler-trace.json",
                qc / "runtime-trace.json",
                qc / "resource-model.json",
                qc / "threshold-sweep.json",
                qc / "primitive-spec.json",
                qc / "fusion-primitive.json",
                qc / "error-budget.json",
            ],
            ["Generate the missing simulation/model reports under reports/node-alpha/qc-path."],
        ),
        _item(
            "evidence_contract_and_templates",
            "Evidence bundle and intake templates exist for the external data that Node Alpha cannot create.",
            bool(evidence and (evidence.get("summary") or {}).get("requiredArtifactCount", 0) >= 24)
            and (root / "evidence-intake" / "templates").is_dir(),
            [qc / "evidence-bundle.json", root / "evidence-intake" / "templates"],
            ["Run oqp evidence-bundle --write-templates."],
        ),
        _item(
            "prototype_gate_map",
            "Prototype readiness report exists and maps all criteria to artifacts.",
            bool(prototype and len(prototype.get("promptToArtifactChecklist", [])) >= 9),
            [qc / "prototype-readiness.json"],
            ["Run oqp prototype-readiness."],
        ),
    ]


def _hard_stops(
    *,
    prototype: dict[str, Any] | None,
    evidence: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    requirement_map = {item.get("id"): item for item in (evidence or {}).get("requirements", [])}
    prototype_map = {item.get("id"): item for item in (prototype or {}).get("promptToArtifactChecklist", [])}
    mapping = [
        ("core_device_models", "core_device_acceptance", "Needs accepted devices plus foundry-calibrated S-parameters."),
        ("foundry_pdk", "foundry_pdk", "Needs a real version-locked foundry PDK manifest and decks."),
        ("drc_lvs_clean_gds", "drc_lvs", "Needs DRC/LVS reports from a real signoff flow."),
        ("hardware_chain", "source_detector_packaging", "Needs measured source, detector, packaging, and control reports."),
        ("automatic_calibration", "automatic_calibration", "Needs calibration results from hardware."),
        ("feed_forward_operation", "control_feed_forward", "Needs hardware-in-the-loop feed-forward timing evidence."),
        ("fault_tolerance_path", "fault_tolerance", "Needs decoder validation and sampled syndrome-noise datasets."),
        ("heralded_primitive_demo", "heralded_primitive_demo", "Needs measured primitive-demo shots and verified dataset hash."),
    ]
    stops = []
    for requirement_id, prototype_id, reason in mapping:
        requirement = requirement_map.get(requirement_id, {})
        proto = prototype_map.get(prototype_id, {})
        if requirement.get("status") == "complete" or proto.get("status") == "complete":
            continue
        blockers = requirement.get("blockers") or proto.get("blockers") or [reason]
        stops.append(
            {
                "requirement": requirement_id,
                "prototypeCriterion": prototype_id,
                "reason": reason,
                "firstBlocker": blockers[0],
                "artifactIds": requirement.get("artifactIds", proto.get("evidenceRefs", [])),
            }
        )
    return stops


def _item(
    item_id: str,
    requirement: str,
    complete: bool,
    evidence_refs: list[Path],
    blockers: list[str],
) -> dict[str, Any]:
    return {
        "id": item_id,
        "requirement": requirement,
        "status": "complete" if complete else "missing",
        "evidenceRefs": [str(path) for path in evidence_refs],
        "blockers": [] if complete else blockers,
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _flag(report: dict[str, Any] | None, name: str) -> bool:
    if not report:
        return False
    for key in ("readinessFlags", "auditFlags"):
        flags = report.get(key)
        if isinstance(flags, dict) and name in flags:
            return bool(flags[name])
    return False


def _gds_complete(gds_audit: dict[str, Any] | None) -> bool:
    flags = (gds_audit or {}).get("auditFlags", {})
    return bool(flags.get("gds_generated") and flags.get("layout_computable"))


def _device_gap_quantified(device_acceptance: dict[str, Any] | None) -> bool:
    summary = (device_acceptance or {}).get("summary", {})
    return bool(
        summary.get("requiredDeviceCount") == 4
        and summary.get("missingEvidenceCount") == 0
        and summary.get("staleEvidenceCount") == 0
        and len((device_acceptance or {}).get("devices", [])) == 4
    )


def _next_external_evidence(hard_stops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return hard_stops[:5]
