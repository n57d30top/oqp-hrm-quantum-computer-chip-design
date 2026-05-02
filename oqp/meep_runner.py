"""Surrogate MEEP/FDTD runner for OQP-HRM blueprints."""

from __future__ import annotations

import time
from typing import Any

from .blueprint import Blueprint


def run_meep_blueprint(
    blueprint: Blueprint,
    *,
    resolution: int = 10,
    until: float = 30,
    max_lanes: int = 8,
) -> dict[str, Any]:
    started = time.time()
    import meep as mp

    spatial = blueprint.spatial_model
    metrics = blueprint.metrics
    lanes = min(spatial.waveguide_count, max_lanes)
    lane_pitch = 0.35
    waveguide_width = 0.12
    cell_x = 12
    cell_y = max(4.0, (lanes + 2) * lane_pitch)
    frequency = 1 / (spatial.laser_wavelength_nm / 1000)
    y0 = -((lanes - 1) * lane_pitch) / 2

    geometry = [
        mp.Block(
            size=mp.Vector3(mp.inf, waveguide_width, mp.inf),
            center=mp.Vector3(0, y0 + lane * lane_pitch, 0),
            material=mp.Medium(epsilon=12.0),
        )
        for lane in range(lanes)
    ]
    sources = [
        mp.Source(
            mp.GaussianSource(frequency=frequency, fwidth=0.2 * frequency),
            component=mp.Ez,
            center=mp.Vector3(-4.5, y0, 0),
            size=mp.Vector3(0, waveguide_width, 0),
        )
    ]

    simulation = mp.Simulation(
        cell_size=mp.Vector3(cell_x, cell_y, 0),
        boundary_layers=[mp.PML(1.0)],
        geometry=geometry,
        sources=sources,
        resolution=resolution,
    )
    reflection = simulation.add_flux(
        frequency,
        0,
        1,
        mp.FluxRegion(center=mp.Vector3(-3.8, y0, 0), size=mp.Vector3(0, 1.0, 0)),
    )
    transmission = simulation.add_flux(
        frequency,
        0,
        1,
        mp.FluxRegion(center=mp.Vector3(3.8, y0, 0), size=mp.Vector3(0, 1.0, 0)),
    )
    simulation.run(until=until)

    reflection_flux = float(mp.get_fluxes(reflection)[0])
    transmission_flux = float(mp.get_fluxes(transmission)[0])
    flux_total = abs(reflection_flux) + abs(transmission_flux)
    transmission_ratio = abs(transmission_flux) / flux_total if flux_total else 0.0
    reflection_ratio = abs(reflection_flux) / flux_total if flux_total else 0.0

    return {
        "schemaVersion": "open-quantum.fdtd-surrogate.v1",
        "backend": "meep",
        "meepVersion": getattr(mp, "__version__", "unknown"),
        "topologyClass": blueprint.topology_class,
        "sourcePath": blueprint.source_path,
        "durationSeconds": round(time.time() - started, 6),
        "surrogate": True,
        "surrogateReason": "Representative 2D waveguide-lane FDTD gate; not a full HRM geometry or PDK layout.",
        "spatialModel": {
            "waveguideCount": spatial.waveguide_count,
            "representedLanes": lanes,
            "interferometerCount": spatial.interferometer_count,
            "laserWavelengthNm": spatial.laser_wavelength_nm,
            "cellX": cell_x,
            "cellY": cell_y,
            "resolution": resolution,
            "until": until,
        },
        "inputMetrics": {
            "heraldingYield": metrics.heralding_yield,
            "attenuationLossScore": metrics.attenuation_loss_score,
            "crosstalkRiskScore": metrics.crosstalk_risk_score,
            "hopLatencyScore": metrics.hop_latency_score,
        },
        "fdtdMetrics": {
            "reflectionFlux": reflection_flux,
            "transmissionFlux": transmission_flux,
            "reflectionRatio": reflection_ratio,
            "transmissionRatio": transmission_ratio,
        },
    }
