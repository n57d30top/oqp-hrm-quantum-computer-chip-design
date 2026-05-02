"""Computational encoding models for OQP-HRM."""

from __future__ import annotations

from typing import Any

from .blueprint import Blueprint


def generate_encoding_spec(blueprint: Blueprint, *, encoding: str = "dual_rail") -> dict[str, Any]:
    spatial = blueprint.spatial_model
    if encoding not in {"dual_rail", "cv_gkp"}:
        raise ValueError("encoding must be dual_rail or cv_gkp")

    if encoding == "dual_rail":
        modes_per_logical = 2
        logical_count = spatial.waveguide_count // modes_per_logical
        primitive = "single_photon_path_qubit"
        non_gaussian = ["single_photon_sources", "photon_number_resolving_detectors"]
        universal_gate_gap = "requires measurement-induced nonlinearity or non-Gaussian ancilla states"
    else:
        modes_per_logical = 1
        logical_count = spatial.waveguide_count
        primitive = "continuous_variable_gkp_mode"
        non_gaussian = ["gkp_state_preparation", "non_gaussian_measurement_or_magic_state_injection"]
        universal_gate_gap = "requires GKP error correction plus non-Gaussian resource injection"

    return {
        "schemaVersion": "open-quantum.encoding-spec.v1",
        "topologyClass": blueprint.topology_class,
        "sourcePath": blueprint.source_path,
        "encoding": encoding,
        "primitive": primitive,
        "waveguideCount": spatial.waveguide_count,
        "modesPerLogicalQubit": modes_per_logical,
        "logicalQubitCapacity": logical_count,
        "physicalModeRoles": [
            {"mode": mode, "logicalQubit": mode // modes_per_logical, "rail": mode % modes_per_logical}
            for mode in range(spatial.waveguide_count)
        ],
        "requiredNonGaussianResources": non_gaussian,
        "universalGateGap": universal_gate_gap,
        "faultToleranceStatus": "architecture_path_only",
    }
