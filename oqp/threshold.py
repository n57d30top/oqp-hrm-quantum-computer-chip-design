"""Threshold sweeps for the OQP-HRM fault-tolerance path."""

from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Any

from .blueprint import Blueprint
from .error_correction import generate_error_correction_plan
from .report import write_json_report


def run_threshold_sweep(
    blueprint: Blueprint,
    *,
    code: str = "fusion_surface_code",
    device_report: dict[str, Any] | None = None,
    decoder_backend: str = "analytical_erasure_matching",
    distances: list[int] | None = None,
    physical_error_rates: list[float] | None = None,
    loss_values_db: list[float] | None = None,
    detector_efficiencies: list[float] | None = None,
    dark_count_rates_hz: list[float] | None = None,
    phase_errors_rad: list[float] | None = None,
    feed_forward_latencies_ns: list[float] | None = None,
    threshold: float = 0.005,
    max_runs: int = 64,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    distances = distances or [3, 5, 7]
    physical_error_rates = physical_error_rates or [0.001, 0.003, 0.005, 0.01]
    loss_values_db = loss_values_db or [0.5, 1.0, 3.0]
    detector_efficiencies = detector_efficiencies or [0.9, 0.95]
    dark_count_rates_hz = dark_count_rates_hz or [10.0, 25.0]
    phase_errors_rad = phase_errors_rad or [0.005, 0.01]
    feed_forward_latencies_ns = feed_forward_latencies_ns or [5.0, 10.0]
    device_terms = _device_error_terms(device_report)

    results: list[dict[str, Any]] = []
    for index, values in enumerate(
        product(
            distances,
            physical_error_rates,
            loss_values_db,
            detector_efficiencies,
            dark_count_rates_hz,
            phase_errors_rad,
            feed_forward_latencies_ns,
        )
    ):
        if index >= max_runs:
            break
        distance, base_error, loss_db, detector_efficiency, dark_count, phase_error, feed_forward_latency = values
        effective_error = _effective_physical_error_rate(
            base_error=base_error,
            loss_db=loss_db,
            detector_efficiency=detector_efficiency,
            dark_count_rate_hz=dark_count,
            phase_error_rad=phase_error,
            feed_forward_latency_ns=feed_forward_latency,
            device_terms=device_terms,
        )
        plan = generate_error_correction_plan(
            blueprint,
            code=code,
            distance=distance,
            physical_error_rate=effective_error,
            threshold=threshold,
        )
        result = {
            "candidateId": (
                f"d{distance}_p{base_error:g}_loss{loss_db:g}_eta{detector_efficiency:g}_"
                f"dark{dark_count:g}_phase{phase_error:g}_ff{feed_forward_latency:g}"
            ).replace(".", "p"),
            "code": code,
            "distance": distance,
            "basePhysicalErrorRate": base_error,
            "effectivePhysicalErrorRate": effective_error,
            "lossDb": loss_db,
            "detectorEfficiency": detector_efficiency,
            "darkCountRateHz": dark_count,
            "phaseErrorRad": phase_error,
            "feedForwardLatencyNs": feed_forward_latency,
            "deviceErrorTerms": device_terms,
            "belowThreshold": plan["belowThreshold"],
            "estimatedLogicalErrorRatePerCycle": plan["estimatedLogicalErrorRatePerCycle"],
            "estimatedPhysicalModesPerCorrectionCycle": plan["estimatedPhysicalModesPerCorrectionCycle"],
            "decoder": plan["decoder"],
            "score": _score_candidate(plan["belowThreshold"], plan["estimatedLogicalErrorRatePerCycle"], plan["estimatedPhysicalModesPerCorrectionCycle"]),
        }
        results.append(result)
        if out_dir:
            write_json_report(result, Path(out_dir) / f"{result['candidateId']}.json")

    ranked = sorted(results, key=lambda item: (item["belowThreshold"], item["score"]), reverse=True)
    champion = ranked[0] if ranked else None
    accepted = [item for item in ranked if item["belowThreshold"]]
    syndrome_graph = _syndrome_graph(blueprint, max(distances) if distances else 3)
    decoder = _decoder_backend_report(decoder_backend, syndrome_graph, accepted)
    summary = {
        "schemaVersion": "open-quantum.threshold-sweep.v1",
        "sourcePath": blueprint.source_path,
        "code": code,
        "deviceEvidence": _device_evidence(device_report, device_terms),
        "thresholdAssumption": threshold,
        "runCount": len(ranked),
        "champion": champion,
        "acceptedCandidates": accepted[:10],
        "alternatives": ranked[1:10],
        "syndromeExtractionGraph": syndrome_graph,
        "decoderInterface": {
            "input": ["detector_events", "loss_erasure_flags", "time_ordered_syndromes"],
            "output": ["correction_frame", "logical_observable_update", "confidence"],
            "targetLatencyNs": 1000.0,
            "status": decoder["interfaceStatus"],
        },
        "decoderBackend": decoder,
        "resourceEstimate": _resource_estimate(blueprint, champion),
        "status": "below_threshold_candidate_found" if accepted else "no_below_threshold_candidate",
        "blockers": _blockers(accepted),
    }
    if out_dir:
        write_json_report(summary, Path(out_dir) / "threshold-sweep.json")
        if champion:
            write_json_report(champion, Path(out_dir) / "champion.json")
    return summary


def _effective_physical_error_rate(
    *,
    base_error: float,
    loss_db: float,
    detector_efficiency: float,
    dark_count_rate_hz: float,
    phase_error_rad: float,
    feed_forward_latency_ns: float,
    device_terms: dict[str, float],
) -> float:
    loss_probability = max(0.0, min(1.0, 1.0 - 10 ** (-loss_db / 10.0)))
    detector_loss = max(0.0, 1.0 - detector_efficiency)
    dark_error = min(0.05, dark_count_rate_hz * 1e-9)
    phase_error = min(0.05, phase_error_rad * phase_error_rad)
    latency_error = max(0.0, feed_forward_latency_ns - 5.0) * 1e-4
    device_loss = 0.2 * device_terms["lossProbability"]
    device_reflection = 0.25 * device_terms["reflectionRatio"]
    device_crosstalk = 0.1 * device_terms["crosstalkRatio"]
    return min(
        1.0,
        base_error
        + 0.25 * loss_probability
        + 0.2 * detector_loss
        + dark_error
        + phase_error
        + latency_error
        + device_loss
        + device_reflection
        + device_crosstalk,
    )


def _score_candidate(below_threshold: bool, logical_error_rate: float, modes_per_cycle: int) -> float:
    threshold_bonus = 1000.0 if below_threshold else 0.0
    return threshold_bonus - (1e6 * logical_error_rate) - (0.001 * modes_per_cycle)


def _syndrome_graph(blueprint: Blueprint, distance: int) -> dict[str, Any]:
    logical_capacity = max(1, blueprint.spatial_model.waveguide_count // 2)
    node_count = logical_capacity * distance * distance
    return {
        "type": "fusion_surface_code_matching_graph",
        "distance": distance,
        "logicalQubitsRepresented": logical_capacity,
        "nodeCount": node_count,
        "edgeCountEstimate": int(node_count * 2.5),
        "lossErasureEdges": True,
        "timeLikeEdges": True,
    }


def _resource_estimate(blueprint: Blueprint, champion: dict[str, Any] | None) -> dict[str, Any]:
    distance = int(champion["distance"]) if champion else 3
    logical_capacity = max(1, blueprint.spatial_model.waveguide_count // 2)
    modes_per_logical = distance * distance * 2
    return {
        "distance": distance,
        "logicalQubitCapacity": logical_capacity,
        "physicalModesPerLogicalQubit": modes_per_logical,
        "sourceAttemptsPerLogicalCycle": modes_per_logical * 2,
        "detectorEventsPerLogicalCycle": modes_per_logical,
    }


def _blockers(accepted: list[dict[str, Any]]) -> list[str]:
    if accepted:
        return [
            "Below-threshold candidate is analytical only; decoder implementation and calibrated device data are still required.",
            "Need hardware-calibrated loss, detector inefficiency, dark count, phase error, and feed-forward latency distributions.",
        ]
    return [
        "No candidate in this sweep falls below the threshold assumption.",
        "Reduce loss, detector inefficiency, dark counts, phase error, and feed-forward latency before fault-tolerance readiness.",
        "Implement decoder and validate the syndrome graph against sampled circuit noise.",
    ]


def _device_error_terms(device_report: dict[str, Any] | None) -> dict[str, float]:
    if not device_report:
        return {
            "lossDb": 0.0,
            "lossProbability": 0.0,
            "usefulTransmission": 1.0,
            "reflectionRatio": 0.0,
            "crosstalkRatio": 0.0,
        }
    metrics = device_report.get("fdtdMetrics", {})
    useful = float(metrics.get("usefulTransmission", float(metrics.get("throughRatio", 0.0)) + float(metrics.get("crossRatio", 0.0))))
    loss_db = float(metrics.get("insertionLossDb", -10.0 * __import__("math").log10(max(useful, 1e-12))))
    return {
        "lossDb": loss_db,
        "lossProbability": max(0.0, min(1.0, 1.0 - useful)),
        "usefulTransmission": useful,
        "reflectionRatio": float(metrics.get("reflectionRatio", 0.0)),
        "crosstalkRatio": float(metrics.get("crosstalkRatio", abs(float(metrics.get("throughRatio", 0.0)) - float(metrics.get("crossRatio", 0.0))))),
    }


def _device_evidence(device_report: dict[str, Any] | None, device_terms: dict[str, float]) -> dict[str, Any]:
    return {
        "provided": device_report is not None,
        "schemaVersion": device_report.get("schemaVersion") if device_report else None,
        "device": device_report.get("device") if device_report else None,
        "physicalValidationLevel": device_report.get("physicalValidationLevel") if device_report else None,
        "acceptanceStatus": device_report.get("acceptanceStatus") if device_report else None,
        "deviceErrorTerms": device_terms,
    }


def _decoder_backend_report(
    decoder_backend: str,
    syndrome_graph: dict[str, Any],
    accepted: list[dict[str, Any]],
) -> dict[str, Any]:
    if decoder_backend != "analytical_erasure_matching":
        return {
            "name": decoder_backend,
            "interfaceStatus": "specified_not_implemented",
            "implementationStatus": "missing_backend",
            "missingForProduction": [
                "decoder package or service binding",
                "sampled syndrome event parser",
                "latency benchmark against target hardware",
            ],
        }
    return {
        "name": decoder_backend,
        "interfaceStatus": "analytical_backend_available",
        "implementationStatus": "toy_backend_not_production_decoder",
        "algorithm": "loss_erasure_weighted_matching_score",
        "graphNodes": syndrome_graph["nodeCount"],
        "graphEdgesEstimate": syndrome_graph["edgeCountEstimate"],
        "belowThresholdCandidates": len(accepted),
        "missingForProduction": [
            "replace analytical score with real MWPM/union-find decoder",
            "feed sampled detector events from circuit-level noise simulation",
            "measure decode latency on FPGA/CPU target",
        ],
    }
