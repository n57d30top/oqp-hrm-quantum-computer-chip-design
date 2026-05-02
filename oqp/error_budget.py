"""Noise, calibration, and error-budget models for OQP-HRM."""

from __future__ import annotations

from typing import Any

from .blueprint import Blueprint
from .metrics import transmission_to_db


def generate_error_budget(
    blueprint: Blueprint,
    *,
    source_efficiency: float = 0.85,
    detector_efficiency: float = 0.9,
    dark_count_rate_hz: float = 25.0,
    feed_forward_latency_ns: float = 5.0,
    phase_error_rad: float = 0.01,
) -> dict[str, Any]:
    metrics = blueprint.metrics
    total_efficiency = source_efficiency * detector_efficiency * metrics.heralding_yield
    total_loss_db = transmission_to_db(total_efficiency)
    noise_terms = {
        "sourceInefficiency": 1 - source_efficiency,
        "detectorInefficiency": 1 - detector_efficiency,
        "meshLoss": 1 - metrics.heralding_yield,
        "darkCountProbabilityPerMicrosecond": dark_count_rate_hz / 1_000_000,
        "phaseErrorRad": phase_error_rad,
        "feedForwardLatencyNs": feed_forward_latency_ns,
    }
    return {
        "schemaVersion": "open-quantum.error-budget.v1",
        "sourcePath": blueprint.source_path,
        "faultToleranceStatus": "not_fault_tolerant",
        "totalEndToEndEfficiency": total_efficiency,
        "totalEndToEndLossDb": total_loss_db,
        "noiseTerms": noise_terms,
        "calibrationLoops": [
            "phase_sweep_calibration",
            "detector_dark_count_baseline",
            "source_brightness_scan",
            "feed_forward_latency_measurement",
            "mzi_balance_scan",
        ],
        "faultToleranceBlockers": [
            "No logical qubit code selected.",
            "No syndrome extraction circuit.",
            "No threshold estimate for source, detector, loss, and phase noise.",
            "No non-Gaussian resource factory.",
        ],
    }
