"""Full-stack design dossier for the OQP-HRM quantum-computer architecture."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .blueprint import Blueprint
from .compiler import compile_blueprint, runtime_trace
from .encoding import generate_encoding_spec
from .error_correction import generate_error_correction_plan
from .error_budget import generate_error_budget
from .evidence_bundle import generate_evidence_bundle
from .primitive import generate_primitive_spec
from .prototype_readiness import generate_prototype_readiness
from .resource_model import generate_resource_model


def generate_design_dossier(
    blueprint: Blueprint,
    *,
    artifact_root: str | Path = "reports/node-alpha",
    encoding: str = "dual_rail",
    primitive: str = "fusion_entangling",
    shots: int = 1000,
    feed_forward_latency_ns: float = 5.0,
    target_logical_error_rate: float = 1e-6,
) -> dict[str, Any]:
    """Generate the highest-level design closure report without fabricating evidence."""

    artifact_root_path = Path(artifact_root)
    encoding_spec = generate_encoding_spec(blueprint, encoding=encoding)
    primitive_spec = generate_primitive_spec(blueprint, encoding=encoding, primitive=primitive)
    resources = generate_resource_model(
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
    prototype = _read_existing_report(artifact_root_path / "qc-path" / "prototype-readiness.json") or generate_prototype_readiness(
        blueprint,
        artifact_root=artifact_root_path,
        evidence_dir=artifact_root_path / "qc-path",
        sparameter_audit_path=artifact_root_path / "qc-path" / "sparameter-audit.json",
        gds_audit_path=artifact_root_path / "gds-path" / "gds-audit.json",
        pdk_audit_path=artifact_root_path / "gds-path" / "pdk-audit.json",
        signoff_audit_path=artifact_root_path / "gds-path" / "signoff-audit.json",
        hardware_audit_path=artifact_root_path / "qc-path" / "hardware-audit.json",
        primitive_demo_audit_path=artifact_root_path / "qc-path" / "primitive-demo-audit.json",
        fault_tolerance_audit_path=artifact_root_path / "qc-path" / "fault-tolerance-audit.json",
        threshold_report_path=artifact_root_path / "qc-path" / "threshold-sweep.json",
        control_report_path=artifact_root_path / "qc-path" / "control-readiness.json",
        lab_report_path=artifact_root_path / "qc-path" / "lab-readiness.json",
        fusion_report_path=artifact_root_path / "qc-path" / "fusion-primitive.json",
    )
    evidence = _read_existing_report(artifact_root_path / "qc-path" / "evidence-bundle.json") or generate_evidence_bundle(
        blueprint,
        artifact_root=artifact_root_path,
    )
    layer_closure = _layer_closure(
        encoding_spec=encoding_spec,
        primitive_spec=primitive_spec,
        resources=resources,
        compiled=compiled,
        runtime=runtime,
        error_budget=error_budget,
        error_correction=error_correction,
        prototype=prototype,
        evidence=evidence,
    )
    open_layers = [item for item in layer_closure if item["status"] != "closed"]
    roadmap = _roadmap(prototype=prototype, evidence=evidence)
    return {
        "schemaVersion": "open-quantum.design-dossier.v1",
        "sourcePath": blueprint.source_path,
        "objective": "Finish the OQP-HRM design as a full-stack, auditable quantum-computer architecture dossier.",
        "scopeBoundary": {
            "claim": "complete_architecture_dossier",
            "notClaimed": [
                "foundry-ready tapeout",
                "experimentally validated quantum computer",
                "fault-tolerant logical-qubit machine",
            ],
            "reason": "The dossier composes existing design artifacts and audit gates; it does not replace missing measured evidence.",
        },
        "systemModel": {
            "topologyClass": blueprint.topology_class,
            "solverTarget": blueprint.solver_target,
            "encoding": encoding,
            "primitive": primitive,
            "physicalModes": blueprint.spatial_model.waveguide_count,
            "logicalQubitCapacity": encoding_spec["logicalQubitCapacity"],
            "interferometers": blueprint.spatial_model.interferometer_count,
            "laserWavelengthNm": blueprint.spatial_model.laser_wavelength_nm,
            "pairingStride": blueprint.spatial_model.pairing_stride,
        },
        "designArtifacts": {
            "encoding": encoding_spec,
            "primitive": primitive_spec,
            "resourceModel": resources,
            "compilerTrace": _compiler_summary(compiled),
            "runtimeTrace": runtime,
            "errorBudget": error_budget,
            "errorCorrectionPlan": error_correction,
            "prototypeReadiness": prototype,
            "evidenceBundle": evidence,
        },
        "layerClosure": layer_closure,
        "readinessFlags": {
            "architecture_dossier_complete": not open_layers,
            "prototype_ready": prototype["readinessFlags"]["prototype_ready"],
            "tapeout_ready": prototype["readinessFlags"]["foundry_ready"]
            and prototype["readinessFlags"]["drc_lvs_ready"],
            "hardware_evidence_complete": evidence["readinessFlags"]["prototype_evidence_complete"],
            "fault_tolerance_ready": prototype["readinessFlags"]["fault_tolerance_ready"],
            "experimental_primitive_demonstrated": prototype["readinessFlags"]["primitive_demonstrated"],
        },
        "summary": {
            "status": "architecture_dossier_complete" if not open_layers else "architecture_dossier_open",
            "closedLayerCount": len(layer_closure) - len(open_layers),
            "totalLayerCount": len(layer_closure),
            "prototypeStatus": prototype["summary"]["status"],
            "completePrototypeCriteria": prototype["summary"]["completeCriteria"],
            "totalPrototypeCriteria": prototype["summary"]["totalCriteria"],
            "missingEvidenceArtifacts": evidence["summary"]["missingArtifactCount"],
            "completeEvidenceRequirements": evidence["summary"]["completeRequirementCount"],
            "totalEvidenceRequirements": evidence["summary"]["totalRequirementCount"],
        },
        "blockers": [blocker for item in open_layers for blocker in item["blockers"]],
        "prioritizedRoadmap": roadmap,
        "completionRule": (
            "Treat the design as a finished architecture dossier when all layerClosure items are closed. "
            "Treat it as a complete quantum computer only when prototype_ready, tapeout_ready, "
            "hardware_evidence_complete, fault_tolerance_ready, and experimental_primitive_demonstrated are all true."
        ),
    }


def _layer_closure(
    *,
    encoding_spec: dict[str, Any],
    primitive_spec: dict[str, Any],
    resources: dict[str, Any],
    compiled: dict[str, Any],
    runtime: dict[str, Any],
    error_budget: dict[str, Any],
    error_correction: dict[str, Any],
    prototype: dict[str, Any],
    evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    checklist = prototype["promptToArtifactChecklist"]
    return [
        _closed_item(
            "computational_encoding",
            "Dual-rail logical encoding and mode-to-qubit map are specified.",
            encoding_spec["logicalQubitCapacity"] > 0 and bool(encoding_spec["physicalModeRoles"]),
            ["oqp.encoding.generate_encoding_spec"],
            [],
        ),
        _closed_item(
            "universal_primitive_path",
            "A conditional universal primitive path and demonstrator target are specified.",
            primitive_spec["universalityStatus"] == "conditional_universal_path"
            and bool(primitive_spec["requiredOperations"]),
            ["oqp.primitive.generate_primitive_spec"],
            primitive_spec.get("blockers", []),
        ),
        _closed_item(
            "non_gaussian_resources",
            "Source, detector, ancilla, multiplexing, and calibration resources are enumerated.",
            _resource_model_complete(resources),
            ["oqp.resource_model.generate_resource_model"],
            resources.get("bottlenecks", []),
        ),
        _closed_item(
            "isa_and_runtime",
            "Executable ISA trace and feed-forward runtime envelope are generated.",
            compiled["instructionCount"] > 0 and runtime["totalProgramTimeNsPerShot"] > 0,
            ["oqp.compiler.compile_blueprint", "oqp.compiler.runtime_trace"],
            [],
        ),
        _closed_item(
            "physical_error_model",
            "Noise terms and first-pass error budget are available.",
            _estimated_physical_error_rate(error_budget) >= 0,
            ["oqp.error_budget.generate_error_budget"],
            error_budget.get("faultToleranceBlockers", []),
        ),
        _closed_item(
            "fault_tolerance_design_path",
            "A code, decoder interface, and threshold plan are specified.",
            "decoder" in error_correction and "syndromeExtraction" in error_correction,
            ["oqp.error_correction.generate_error_correction_plan"],
            [] if error_correction.get("belowThreshold") else error_correction.get("blockers", []),
        ),
        _closed_item(
            "prototype_gate_map",
            "Prototype readiness gates map every quantum-computer requirement to concrete artifacts.",
            len(checklist) >= 9 and all(item.get("evidenceRefs") for item in checklist),
            ["oqp.prototype_readiness.generate_prototype_readiness"],
            prototype.get("blockers", []),
        ),
        _closed_item(
            "evidence_intake_contract",
            "Required measured, foundry, signoff, hardware, decoder, and demo artifacts are enumerated.",
            evidence["summary"]["requiredArtifactCount"] >= 24
            and evidence["summary"]["totalRequirementCount"] >= 9,
            ["oqp.evidence_bundle.generate_evidence_bundle"],
            evidence.get("blockers", []),
        ),
    ]


def _closed_item(
    item_id: str,
    requirement: str,
    complete: bool,
    evidence_refs: list[str],
    blockers: list[str],
) -> dict[str, Any]:
    return {
        "id": item_id,
        "requirement": requirement,
        "status": "closed" if complete else "open",
        "evidenceRefs": evidence_refs,
        "blockers": [] if complete else blockers,
    }


def _resource_model_complete(resources: dict[str, Any]) -> bool:
    required = resources.get("requiredNonGaussianResources", {})
    return all(
        key in required
        for key in (
            "singlePhotonSources",
            "pnrDetectors",
            "ancillaFactory",
            "multiplexing",
            "heraldingModel",
        )
    )


def _compiler_summary(compiled: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": compiled["schemaVersion"],
        "instructionCount": compiled["instructionCount"],
        "shots": compiled["shots"],
        "encoding": compiled["encoding"],
        "ops": sorted({instruction["op"] for instruction in compiled["instructions"]}),
        "resultDecoding": compiled["resultDecoding"],
    }


def _estimated_physical_error_rate(error_budget: dict[str, Any]) -> float:
    terms = error_budget.get("noiseTerms", {})
    components = [
        float(terms.get("sourceInefficiency", 0.0)),
        float(terms.get("detectorInefficiency", 0.0)),
        float(terms.get("meshLoss", 0.0)),
        float(terms.get("darkCountProbabilityPerMicrosecond", 0.0)),
        abs(float(terms.get("phaseErrorRad", 0.0))),
    ]
    return min(1.0, max(0.0, sum(components) / max(1, len(components))))


def _read_existing_report(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _roadmap(*, prototype: dict[str, Any], evidence: dict[str, Any]) -> list[dict[str, Any]]:
    requirement_order = [
        "core_device_models",
        "foundry_pdk",
        "drc_lvs_clean_gds",
        "hardware_chain",
        "automatic_calibration",
        "feed_forward_operation",
        "fault_tolerance_path",
        "heralded_primitive_demo",
        "prototype_gate",
    ]
    requirement_reports = {item["id"]: item for item in evidence.get("requirements", [])}
    prototype_items = {item["id"]: item for item in prototype.get("promptToArtifactChecklist", [])}
    roadmap = []
    for priority, requirement_id in enumerate(requirement_order, start=1):
        requirement = requirement_reports.get(requirement_id)
        if not requirement or requirement["status"] == "complete":
            continue
        blockers = requirement.get("blockers", [])
        evidence_refs = requirement.get("artifactIds", [])
        if requirement_id == "core_device_models":
            prototype_item = prototype_items.get("core_device_acceptance", {})
            blockers = prototype_item.get("blockers", blockers)
            evidence_refs = prototype_item.get("evidenceRefs", evidence_refs)
        roadmap.append(
            {
                "priority": f"P{priority}",
                "requirement": requirement_id,
                "status": requirement["status"],
                "nextAction": blockers[0] if blockers else "Collect missing evidence and rerun the relevant audit.",
                "evidenceToProduce": evidence_refs,
                "acceptanceGate": requirement["description"],
            }
        )
    return roadmap
