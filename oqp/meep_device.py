"""MEEP device-cell FDTD for directional-coupler/MZI/truth-switch candidates."""

from __future__ import annotations

import time
from typing import Any

from .blueprint import Blueprint


DEVICE_SIMULATION_MODEL_VERSION = "fdtd_device.v2.parallel_waveguides_no_core_cutout"


def run_meep_device(
    blueprint: Blueprint,
    *,
    device: str = "mzi",
    resolution: int = 10,
    until: float = 30.0,
    coupling_gap_um: float = 0.2,
    coupling_length_um: float = 3.0,
    phase_shift_rad: float = 0.0,
    waveguide_width_um: float = 0.45,
) -> dict[str, Any]:
    if device not in {"coupler", "mzi", "truth-switch"}:
        raise ValueError("device must be coupler, mzi, or truth-switch")

    started = time.time()
    import meep as mp

    spatial = blueprint.spatial_model
    frequency = 1 / (spatial.laser_wavelength_nm / 1000)
    width = waveguide_width_um
    lane_sep = width + coupling_gap_um
    cell_x = max(10.0, coupling_length_um + 8.0)
    cell_y = max(4.0, 3.0 * lane_sep + 2.0)
    pml_um = 1.0
    source_x = -cell_x / 2 + pml_um + 1.0
    input_monitor_x = source_x + 0.7
    output_monitor_x = cell_x / 2 - pml_um - 0.8
    lower_y = -lane_sep / 2
    upper_y = lane_sep / 2
    eps_si = 12.0
    phase_eps = eps_si * (1 + min(abs(phase_shift_rad), 3.14159) * 0.01)

    geometry = [
        mp.Block(size=mp.Vector3(mp.inf, width, mp.inf), center=mp.Vector3(0, lower_y, 0), material=mp.Medium(epsilon=eps_si)),
        mp.Block(size=mp.Vector3(mp.inf, width, mp.inf), center=mp.Vector3(0, upper_y, 0), material=mp.Medium(epsilon=eps_si)),
    ]
    if device in {"mzi", "truth-switch"}:
        geometry.append(
            mp.Block(
                size=mp.Vector3(1.5, width, mp.inf),
                center=mp.Vector3(2.0, upper_y, 0),
                material=mp.Medium(epsilon=phase_eps),
            )
        )
    if device == "truth-switch":
        geometry.append(
            mp.Block(
                size=mp.Vector3(0.8, lane_sep + width, mp.inf),
                center=mp.Vector3(-2.0, 0, 0),
                material=mp.Medium(epsilon=1.8),
            )
        )

    sources = [
        mp.Source(
            mp.GaussianSource(frequency=frequency, fwidth=0.2 * frequency),
            component=mp.Ez,
            center=mp.Vector3(source_x, lower_y, 0),
            size=mp.Vector3(0, width, 0),
        )
    ]
    simulation = mp.Simulation(
        cell_size=mp.Vector3(cell_x, cell_y, 0),
        boundary_layers=[mp.PML(pml_um)],
        geometry=geometry,
        sources=sources,
        resolution=resolution,
    )
    reflection = simulation.add_flux(
        frequency,
        0,
        1,
        mp.FluxRegion(center=mp.Vector3(input_monitor_x, lower_y, 0), size=mp.Vector3(0, 0.8, 0)),
    )
    through = simulation.add_flux(
        frequency,
        0,
        1,
        mp.FluxRegion(center=mp.Vector3(output_monitor_x, lower_y, 0), size=mp.Vector3(0, 0.8, 0)),
    )
    cross = simulation.add_flux(
        frequency,
        0,
        1,
        mp.FluxRegion(center=mp.Vector3(output_monitor_x, upper_y, 0), size=mp.Vector3(0, 0.8, 0)),
    )
    simulation.run(until=until)

    reflection_flux = float(mp.get_fluxes(reflection)[0])
    through_flux = float(mp.get_fluxes(through)[0])
    cross_flux = float(mp.get_fluxes(cross)[0])
    total = abs(reflection_flux) + abs(through_flux) + abs(cross_flux)
    through_ratio = abs(through_flux) / total if total else 0.0
    cross_ratio = abs(cross_flux) / total if total else 0.0
    reflection_ratio = abs(reflection_flux) / total if total else 0.0
    insertion_loss_db = -10 * __import__("math").log10(max(through_ratio + cross_ratio, 1e-12))

    return {
        "schemaVersion": "open-quantum.fdtd-device.v1",
        "backend": "meep",
        "meepVersion": getattr(mp, "__version__", "unknown"),
        "sourcePath": blueprint.source_path,
        "device": device,
        "durationSeconds": round(time.time() - started, 6),
        "physicalValidationLevel": "device_cell_first_pass",
        "simulationModelVersion": DEVICE_SIMULATION_MODEL_VERSION,
        "simulationModelChanges": [
            "Removed cladding block that cut through silicon waveguide cores in coupler/MZI regions.",
            "Made cell length and monitor positions depend on coupling length to keep sources and monitors away from PML.",
        ],
        "geometry": {
            "cellXUm": cell_x,
            "cellYUm": cell_y,
            "waveguideWidthUm": width,
            "couplingGapUm": coupling_gap_um,
            "couplingLengthUm": coupling_length_um,
            "phaseShiftRad": phase_shift_rad,
            "laserWavelengthNm": spatial.laser_wavelength_nm,
            "resolution": resolution,
            "until": until,
            "couplingRegionModel": "parallel_waveguides_no_core_cutout",
        },
        "fdtdMetrics": {
            "reflectionFlux": reflection_flux,
            "throughFlux": through_flux,
            "crossFlux": cross_flux,
            "reflectionRatio": reflection_ratio,
            "throughRatio": through_ratio,
            "crossRatio": cross_ratio,
            "insertionLossDb": insertion_loss_db,
            "modeResolvedTransmission": {"through": through_ratio, "cross": cross_ratio},
        },
        "limitations": [
            "2D device-cell model, not full 3D fabrication geometry.",
            "Source/detector are flux monitors, not hardware-calibrated photon devices.",
            "Truth-switch state is represented by a surrogate dielectric perturbation.",
        ],
    }
