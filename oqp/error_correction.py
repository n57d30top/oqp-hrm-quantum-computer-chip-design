"""Fault-tolerance, syndrome extraction, and decoder planning for OQP-HRM."""

from __future__ import annotations

import math
from typing import Any

from .blueprint import Blueprint


def generate_error_correction_plan(
    blueprint: Blueprint,
    *,
    code: str = "fusion_surface_code",
    distance: int = 3,
    physical_error_rate: float = 0.01,
    threshold: float = 0.005,
) -> dict[str, Any]:
    if distance < 3 or distance % 2 == 0:
        raise ValueError("distance must be an odd integer >= 3")

    spatial = blueprint.spatial_model
    logical_capacity = max(1, spatial.waveguide_count // 2)
    below_threshold = physical_error_rate < threshold
    exponent = (distance + 1) // 2
    logical_error_rate = 0.1 * (physical_error_rate / threshold) ** exponent if below_threshold else min(1.0, physical_error_rate)
    cycle_modes = logical_capacity * distance * distance * 2
    decoder_complexity = "matching_graph" if code == "fusion_surface_code" else "belief_propagation_plus_lookup"

    return {
        "schemaVersion": "open-quantum.error-correction-plan.v1",
        "sourcePath": blueprint.source_path,
        "code": code,
        "distance": distance,
        "physicalErrorRate": physical_error_rate,
        "thresholdAssumption": threshold,
        "belowThreshold": below_threshold,
        "estimatedLogicalErrorRatePerCycle": logical_error_rate,
        "logicalQubitCapacity": logical_capacity,
        "estimatedPhysicalModesPerCorrectionCycle": cycle_modes,
        "syndromeExtraction": {
            "method": "fusion_parity_measurements",
            "measurementRounds": distance,
            "requiresFastFeedForward": True,
            "requiresLossErasureFlags": True,
        },
        "decoder": {
            "type": decoder_complexity,
            "latencyBudgetNs": 1000.0,
            "status": "specified_not_implemented",
        },
        "resourceScaling": {
            "modeScaling": "O(distance^2 * logical_qubits)",
            "decoderScaling": "O(nodes log nodes)",
            "estimatedCycleDepth": int(math.ceil(distance * 1.5)),
        },
        "blockers": [
            "Need physical error model from calibrated source, detector, MZI, switch, and loss data.",
            "Need syndrome graph generator and decoder implementation.",
            "Need threshold sweep over loss, dark counts, phase error, and feed-forward latency.",
        ],
    }
