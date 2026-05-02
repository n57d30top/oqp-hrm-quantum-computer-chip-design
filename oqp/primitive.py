"""Universal primitive and demonstrator specifications for OQP-HRM."""

from __future__ import annotations

from typing import Any

from .blueprint import Blueprint
from .resource_model import generate_resource_model


def generate_primitive_spec(
    blueprint: Blueprint,
    *,
    encoding: str = "dual_rail",
    primitive: str = "fusion_entangling",
) -> dict[str, Any]:
    if primitive not in {"fusion_entangling", "klm_csign", "gkp_gate_teleportation"}:
        raise ValueError("primitive must be fusion_entangling, klm_csign, or gkp_gate_teleportation")

    spatial = blueprint.spatial_model
    if primitive == "fusion_entangling":
        universality = "conditional_universal_path"
        logical_model = "fusion-based photonic quantum computing"
        required_ops = ["single_photon_prepare", "linear_optics_mesh", "type_ii_fusion", "pnr_measurement", "feed_forward"]
        demonstrator = {
            "name": "two_qubit_heralded_fusion_cell",
            "physicalModes": min(spatial.waveguide_count, 4),
            "logicalQubits": 2,
            "successCondition": "two-fold herald with dual-rail occupancy parity check",
        }
    elif primitive == "klm_csign":
        universality = "conditional_universal_path"
        logical_model = "KLM-style linear optical quantum computing"
        required_ops = ["single_photon_prepare", "ancilla_prepare", "linear_optics_mesh", "pnr_measurement", "adaptive_feed_forward"]
        demonstrator = {
            "name": "heralded_csign_ancilla_cell",
            "physicalModes": min(spatial.waveguide_count, 6),
            "logicalQubits": 2,
            "successCondition": "ancilla-conditioned controlled-sign event",
        }
    else:
        universality = "architecture_path_only"
        logical_model = "continuous-variable GKP photonic quantum computing"
        required_ops = ["squeezed_state_prepare", "gkp_state_prepare", "homodyne_measurement", "non_gaussian_injection", "feed_forward"]
        demonstrator = {
            "name": "single_mode_gkp_teleportation_cell",
            "physicalModes": min(spatial.waveguide_count, 2),
            "logicalQubits": 1,
            "successCondition": "finite-squeezing syndrome below correction radius",
        }

    blockers = [
        "Need experimentally characterized source and detector model.",
        "Need calibrated low-loss entangling/fusion cell.",
        "Need threshold simulation that includes loss, detector inefficiency, dark counts, and feed-forward latency.",
        "Need scalable resource-state factory and decoder integration.",
    ]
    return {
        "schemaVersion": "open-quantum.primitive-spec.v1",
        "sourcePath": blueprint.source_path,
        "encoding": encoding,
        "primitive": primitive,
        "logicalModel": logical_model,
        "universalityStatus": universality,
        "requiredOperations": required_ops,
        "minimalDemonstrator": demonstrator,
        "acceptanceMetrics": {
            "maxInsertionLossDb": 1.0,
            "maxReflectionRatio": 0.05,
            "minHeraldingSuccessProbability": 0.01,
            "minProcessFidelity": 0.99,
            "maxFeedForwardLatencyNs": 10.0,
        },
        "blockers": blockers,
    }


def generate_fusion_primitive(
    blueprint: Blueprint,
    *,
    device_report: dict[str, Any] | None = None,
    encoding: str = "dual_rail",
    feed_forward_latency_ns: float = 5.0,
    source_efficiency: float = 0.85,
    detector_efficiency: float = 0.9,
) -> dict[str, Any]:
    """Build an executable two-qubit heralded-fusion primitive report."""

    spec = generate_primitive_spec(blueprint, encoding=encoding, primitive="fusion_entangling")
    resources = generate_resource_model(blueprint, encoding=encoding, logical_qubits=2)
    metrics = _device_metrics(device_report)
    useful_transmission = metrics["usefulTransmission"]
    heralding_success = min(
        1.0,
        max(
            0.0,
            useful_transmission
            * source_efficiency
            * source_efficiency
            * detector_efficiency
            * detector_efficiency
            * max(0.0, min(1.0, blueprint.metrics.heralding_yield)),
        ),
    )
    process_fidelity = max(
        0.0,
        min(
            1.0,
            1.0
            - (0.5 * metrics["reflectionRatio"])
            - (0.25 * metrics["crosstalkRatio"])
            - (0.25 * max(0.0, 1.0 - useful_transmission))
            - (0.02 if feed_forward_latency_ns > 10.0 else 0.0),
        ),
    )
    acceptance = spec["acceptanceMetrics"]
    blockers = _fusion_blockers(
        metrics=metrics,
        process_fidelity=process_fidelity,
        heralding_success=heralding_success,
        feed_forward_latency_ns=feed_forward_latency_ns,
        acceptance=acceptance,
        device_report=device_report,
    )
    primitive_ready = not blockers
    return {
        "schemaVersion": "open-quantum.fusion-primitive.v1",
        "sourcePath": blueprint.source_path,
        "encoding": encoding,
        "primitive": "two_qubit_heralded_fusion",
        "status": "primitive_ready" if primitive_ready else "not_primitive_ready",
        "executionPath": [
            "PREPARE dual-rail qubit A",
            "PREPARE dual-rail qubit B",
            "ROUTE into calibrated MZI/truth-switch fusion cell",
            "APPLY linear-optical interference",
            "MEASURE PNR herald ports",
            "HERALD_WAIT and conditional feed-forward",
            "RESULT_DECODE dual-rail occupancy/parity",
        ],
        "deviceEvidence": {
            "schemaVersion": device_report.get("schemaVersion") if device_report else None,
            "device": device_report.get("device") if device_report else "modeled_without_fdtd_artifact",
            "physicalValidationLevel": device_report.get("physicalValidationLevel") if device_report else "modeled_only",
            "sourceModel": device_report.get("sourceModel") if device_report else "none",
            "fdtdMetrics": metrics,
        },
        "nonGaussianResources": resources["requiredNonGaussianResources"],
        "heraldingModel": {
            "sourceEfficiency": source_efficiency,
            "detectorEfficiency": detector_efficiency,
            "blueprintHeraldingYield": blueprint.metrics.heralding_yield,
            "estimatedHeraldingSuccessProbability": heralding_success,
        },
        "qualityModel": {
            "estimatedProcessFidelity": process_fidelity,
            "feedForwardLatencyNs": feed_forward_latency_ns,
        },
        "acceptance": acceptance,
        "readinessFlags": {
            "simulated": True,
            "fdtdValidated": bool(device_report),
            "primitiveReady": primitive_ready,
            "requiresNonGaussianHardware": True,
            "requiresFastFeedForward": True,
        },
        "blockers": blockers,
    }


def _device_metrics(device_report: dict[str, Any] | None) -> dict[str, float]:
    if not device_report:
        return {
            "throughRatio": 0.25,
            "crossRatio": 0.25,
            "reflectionRatio": 0.2,
            "usefulTransmission": 0.5,
            "insertionLossDb": 3.0,
            "crosstalkRatio": 0.25,
        }
    raw = device_report.get("fdtdMetrics", {})
    through = float(raw.get("throughRatio", 0.0))
    cross = float(raw.get("crossRatio", 0.0))
    useful = float(raw.get("usefulTransmission", through + cross))
    return {
        "throughRatio": through,
        "crossRatio": cross,
        "reflectionRatio": float(raw.get("reflectionRatio", 1.0)),
        "usefulTransmission": useful,
        "insertionLossDb": float(raw.get("insertionLossDb", 120.0)),
        "crosstalkRatio": float(raw.get("crosstalkRatio", raw.get("imbalanceRatio", abs(through - cross)))),
    }


def _fusion_blockers(
    *,
    metrics: dict[str, float],
    process_fidelity: float,
    heralding_success: float,
    feed_forward_latency_ns: float,
    acceptance: dict[str, float],
    device_report: dict[str, Any] | None,
) -> list[str]:
    blockers: list[str] = []
    if not device_report:
        blockers.append("No calibrated FDTD device artifact was supplied for the fusion cell.")
    if metrics["insertionLossDb"] > acceptance["maxInsertionLossDb"]:
        blockers.append(
            f"Insertion loss {metrics['insertionLossDb']:.3f} dB exceeds {acceptance['maxInsertionLossDb']:.3f} dB."
        )
    if metrics["reflectionRatio"] > acceptance["maxReflectionRatio"]:
        blockers.append(
            f"Reflection ratio {metrics['reflectionRatio']:.4f} exceeds {acceptance['maxReflectionRatio']:.4f}."
        )
    if heralding_success < acceptance["minHeraldingSuccessProbability"]:
        blockers.append(
            "Heralding success "
            f"{heralding_success:.6f} is below {acceptance['minHeraldingSuccessProbability']:.6f}."
        )
    if process_fidelity < acceptance["minProcessFidelity"]:
        blockers.append(f"Estimated process fidelity {process_fidelity:.6f} is below {acceptance['minProcessFidelity']:.6f}.")
    if feed_forward_latency_ns > acceptance["maxFeedForwardLatencyNs"]:
        blockers.append(
            f"Feed-forward latency {feed_forward_latency_ns:.3f} ns exceeds {acceptance['maxFeedForwardLatencyNs']:.3f} ns."
        )
    return blockers
