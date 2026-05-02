"""Layout planning artifact for future OQP-HRM GDS export."""

from __future__ import annotations

from typing import Any

from .blueprint import Blueprint
from .topology import connected_component_count, mzi_pairs


def generate_layout_plan(blueprint: Blueprint, *, lane_pitch_um: float = 4.0, mzi_pitch_um: float = 30.0) -> dict[str, Any]:
    spatial = blueprint.spatial_model
    pairs = mzi_pairs(spatial.waveguide_count, spatial.interferometer_count, spatial.pairing_stride)
    lanes = [
        {
            "mode": mode,
            "x0Um": 0.0,
            "x1Um": max(1, spatial.interferometer_count) * mzi_pitch_um,
            "yUm": mode * lane_pitch_um,
        }
        for mode in range(spatial.waveguide_count)
    ]
    mzi_cells = [
        {
            "index": index,
            "modeA": mode_a,
            "modeB": mode_b,
            "xUm": (index + 0.5) * mzi_pitch_um,
            "yUm": ((mode_a + mode_b) / 2) * lane_pitch_um,
            "cellType": "mzi_truth_switch_candidate",
        }
        for index, (mode_a, mode_b) in enumerate(pairs)
    ]
    return {
        "schemaVersion": "open-quantum.layout-plan.v1",
        "topologyClass": blueprint.topology_class,
        "sourcePath": blueprint.source_path,
        "gdsReady": False,
        "gdsBlockers": [
            "No PDK target selected.",
            "No bend radius, coupler, phase shifter, detector, or metal routing rules declared.",
            "MZI truth-switch cell geometry is still abstract.",
        ],
        "units": "um",
        "spatialModel": {
            "waveguideCount": spatial.waveguide_count,
            "interferometerCount": spatial.interferometer_count,
            "pairingStride": spatial.pairing_stride,
            "connectedComponents": connected_component_count(spatial.waveguide_count, pairs),
            "lanePitchUm": lane_pitch_um,
            "mziPitchUm": mzi_pitch_um,
        },
        "lanes": lanes,
        "mziCells": mzi_cells,
    }
