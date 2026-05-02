"""Eigenmode-normalized MEEP device-cell FDTD for OQP-HRM cells."""

from __future__ import annotations

import math
import time
from typing import Any

from .blueprint import Blueprint


SUPPORTED_DEVICES = {"coupler", "mzi", "phase-shifter", "truth-switch"}
DEVICE_SIMULATION_MODEL_VERSION = "eigenmode_device.v4.reference_output_port_normalized_reliability_gate"
MIN_OUTPUT_PORT_NORMALIZATION_FLUX = 1e-8


def run_eigenmode_device(
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
    """Run a calibrated 2D MEEP cell with reference output-port normalization."""

    if device not in SUPPORTED_DEVICES:
        raise ValueError("device must be coupler, mzi, phase-shifter, or truth-switch")

    started = time.time()
    try:
        import meep as mp
    except ModuleNotFoundError:
        return _run_node_alpha_surrogate(
            blueprint,
            device=device,
            resolution=resolution,
            until=until,
            coupling_gap_um=coupling_gap_um,
            coupling_length_um=coupling_length_um,
            phase_shift_rad=phase_shift_rad,
            waveguide_width_um=waveguide_width_um,
            started=started,
        )

    try:
        reference, measured, source_model = _run_calibrated_pair(
            mp,
            blueprint,
            device=device,
            resolution=resolution,
            until=until,
            coupling_gap_um=coupling_gap_um,
            coupling_length_um=coupling_length_um,
            phase_shift_rad=phase_shift_rad,
            waveguide_width_um=waveguide_width_um,
            source_model="eigenmode",
        )
    except Exception as exc:
        reference, measured, source_model = _run_calibrated_pair(
            mp,
            blueprint,
            device=device,
            resolution=resolution,
            until=until,
            coupling_gap_um=coupling_gap_um,
            coupling_length_um=coupling_length_um,
            phase_shift_rad=phase_shift_rad,
            waveguide_width_um=waveguide_width_um,
            source_model="gaussian_fallback",
        )
        measured["eigenmodeFallbackReason"] = f"{type(exc).__name__}: {exc}"

    metrics = _normalized_flux_metrics(device=device, reference=reference, measured=measured)
    acceptance = {
        "maxInsertionLossDb": 1.0,
        "maxReflectionRatio": 0.05,
        "minUsefulTransmission": 0.5,
        "maxCrosstalkRatio": 0.05,
        "maxMziImbalanceRatio": 0.2,
        "minOutputPortNormalizationFlux": MIN_OUTPUT_PORT_NORMALIZATION_FLUX,
    }
    accepted = _accepted(
        metrics["usefulTransmission"],
        metrics["insertionLossDb"],
        metrics["reflectionRatio"],
        metrics["crosstalkRatio"],
        metrics["imbalanceRatio"],
        metrics["normalizationReliable"],
        device,
    )

    geometry = _geometry_spec(
        blueprint,
        device=device,
        coupling_gap_um=coupling_gap_um,
        coupling_length_um=coupling_length_um,
        phase_shift_rad=phase_shift_rad,
        waveguide_width_um=waveguide_width_um,
        resolution=resolution,
        until=until,
    )
    return {
        "schemaVersion": "open-quantum.eigenmode-device.v1",
        "backend": "meep",
        "meepVersion": getattr(mp, "__version__", "unknown"),
        "sourcePath": blueprint.source_path,
        "device": device,
        "durationSeconds": round(time.time() - started, 6),
        "physicalValidationLevel": "eigenmode_calibrated_2d_first_pass",
        "simulationModelVersion": DEVICE_SIMULATION_MODEL_VERSION,
        "simulationModelChanges": [
            "Removed cladding block that cut through silicon waveguide cores in coupler/MZI regions.",
            "Made cell length and monitor positions depend on coupling length to keep sources and monitors away from PML.",
            "Normalize through/cross output power against the straight-waveguide through-port reference, not the input monitor.",
            "Evaluate MZI/phase-shifter acceptance as a through-state low-leakage operating point; balanced-splitter tuning is a separate operating point.",
        ],
        "validationTier": _validation_tier(resolution, until),
        "sourceModel": source_model,
        "calibration": {
            "method": "straight_waveguide_reference_flux",
            "inputFlux": reference["inputFlux"],
            "inputFluxMagnitude": metrics["inputNormalizationFlux"],
            "outputPortNormalizationFlux": metrics["outputPortNormalizationFlux"],
            "minOutputPortNormalizationFlux": MIN_OUTPUT_PORT_NORMALIZATION_FLUX,
            "referenceInputFlux": reference["inputFlux"],
            "referenceThroughFlux": reference["throughFlux"],
        },
        "geometry": geometry,
        "fdtdMetrics": {
            "inputMonitorFlux": measured["inputFlux"],
            "inputNormalizationFlux": metrics["inputNormalizationFlux"],
            "outputPortNormalizationFlux": metrics["outputPortNormalizationFlux"],
            "normalizationReliable": metrics["normalizationReliable"],
            "reflectionFlux": metrics["reflectionFlux"],
            "throughFlux": measured["throughFlux"],
            "crossFlux": measured["crossFlux"],
            "reflectionRatio": metrics["reflectionRatio"],
            "throughRatio": metrics["throughRatio"],
            "crossRatio": metrics["crossRatio"],
            "usefulTransmission": metrics["usefulTransmission"],
            "insertionLossDb": metrics["insertionLossDb"],
            "crosstalkRatio": metrics["crosstalkRatio"],
            "imbalanceRatio": metrics["imbalanceRatio"],
            "modeResolvedTransmission": {
                "throughPortMode0": metrics["throughRatio"],
                "crossPortMode0": metrics["crossRatio"],
            },
            "timing": {
                "until": until,
                "resolution": resolution,
            },
        },
        "acceptance": acceptance,
        "acceptanceStatus": "accepted_first_pass_candidate" if accepted else "not_accepted_first_pass",
        "gapToAcceptance": _gap_to_acceptance(
            useful_transmission=metrics["usefulTransmission"],
            insertion_loss_db=metrics["insertionLossDb"],
            reflection_ratio=metrics["reflectionRatio"],
            crosstalk_ratio=metrics["crosstalkRatio"],
            imbalance_ratio=metrics["imbalanceRatio"],
            normalization_reliable=metrics["normalizationReliable"],
            output_port_normalization_flux=metrics["outputPortNormalizationFlux"],
            device=device,
            acceptance=acceptance,
        ),
        "calibrationProtocol": {
            "sourceCheck": "eigenmode_source_with_gaussian_fallback",
            "referenceCheck": "straight_waveguide_output_port_flux",
            "reflectionCheck": "input_monitor_reference_subtraction",
            "nextValidation": [
                "move monitors away from source near field and PML",
                "extract port S-parameters with MPB mode decomposition",
                "repeat at resolution >= 16 and 3D geometry before GDS promotion",
            ],
        },
        "limitations": [
            "2D FDTD cell, not a 3D foundry-validated layout.",
            "Eigenmode normalization uses a straight-waveguide output-port reference, not a calibrated wafer measurement.",
            "Truth-switch actuation is represented by a dielectric perturbation pending material/driver model.",
            "Mode-resolved transmission is first-pass monitor-port power, not full S-parameter/MPB extraction.",
        ],
    }


def _run_node_alpha_surrogate(
    blueprint: Blueprint,
    *,
    device: str,
    resolution: int,
    until: float,
    coupling_gap_um: float,
    coupling_length_um: float,
    phase_shift_rad: float,
    waveguide_width_um: float,
    started: float,
) -> dict[str, Any]:
    """Deterministic local surrogate used only when MEEP is unavailable."""

    reference, measured = _surrogate_flux_pair(
        device=device,
        coupling_gap_um=coupling_gap_um,
        coupling_length_um=coupling_length_um,
        phase_shift_rad=phase_shift_rad,
        waveguide_width_um=waveguide_width_um,
    )
    metrics = _normalized_flux_metrics(device=device, reference=reference, measured=measured)
    acceptance = {
        "maxInsertionLossDb": 1.0,
        "maxReflectionRatio": 0.05,
        "minUsefulTransmission": 0.5,
        "maxCrosstalkRatio": 0.05,
        "maxMziImbalanceRatio": 0.2,
        "minOutputPortNormalizationFlux": MIN_OUTPUT_PORT_NORMALIZATION_FLUX,
    }
    accepted = _accepted(
        metrics["usefulTransmission"],
        metrics["insertionLossDb"],
        metrics["reflectionRatio"],
        metrics["crosstalkRatio"],
        metrics["imbalanceRatio"],
        metrics["normalizationReliable"],
        device,
    )
    geometry = _geometry_spec(
        blueprint,
        device=device,
        coupling_gap_um=coupling_gap_um,
        coupling_length_um=coupling_length_um,
        phase_shift_rad=phase_shift_rad,
        waveguide_width_um=waveguide_width_um,
        resolution=resolution,
        until=until,
    )
    return {
        "schemaVersion": "open-quantum.eigenmode-device.v1",
        "backend": "node_alpha_analytical_surrogate",
        "meepVersion": None,
        "sourcePath": blueprint.source_path,
        "device": device,
        "durationSeconds": round(time.time() - started, 6),
        "physicalValidationLevel": "node_alpha_surrogate_not_fdtd",
        "simulationModelVersion": DEVICE_SIMULATION_MODEL_VERSION,
        "simulationModelChanges": [
            "MEEP is unavailable in this Node Alpha environment; this artifact is a deterministic analytical surrogate.",
            "Surrogate terms are parameterized by coupling gap, coupling length, phase shift, and waveguide width.",
            "MZI/phase-shifter acceptance is evaluated as a through-state low-leakage operating point; balanced-splitter tuning is a separate operating point.",
            "Use only for ranking and sensitivity exploration; do not promote as FDTD, foundry, or lab evidence.",
        ],
        "validationTier": "node_alpha_surrogate_gap_probe",
        "sourceModel": "node_alpha_analytical_surrogate",
        "calibration": {
            "method": "analytical_surrogate_output_port_reference",
            "inputFlux": reference["inputFlux"],
            "inputFluxMagnitude": metrics["inputNormalizationFlux"],
            "outputPortNormalizationFlux": metrics["outputPortNormalizationFlux"],
            "minOutputPortNormalizationFlux": MIN_OUTPUT_PORT_NORMALIZATION_FLUX,
            "referenceInputFlux": reference["inputFlux"],
            "referenceThroughFlux": reference["throughFlux"],
        },
        "geometry": geometry,
        "fdtdMetrics": {
            "inputMonitorFlux": measured["inputFlux"],
            "inputNormalizationFlux": metrics["inputNormalizationFlux"],
            "outputPortNormalizationFlux": metrics["outputPortNormalizationFlux"],
            "normalizationReliable": metrics["normalizationReliable"],
            "reflectionFlux": metrics["reflectionFlux"],
            "throughFlux": measured["throughFlux"],
            "crossFlux": measured["crossFlux"],
            "reflectionRatio": metrics["reflectionRatio"],
            "throughRatio": metrics["throughRatio"],
            "crossRatio": metrics["crossRatio"],
            "usefulTransmission": metrics["usefulTransmission"],
            "insertionLossDb": metrics["insertionLossDb"],
            "crosstalkRatio": metrics["crosstalkRatio"],
            "imbalanceRatio": metrics["imbalanceRatio"],
            "modeResolvedTransmission": {
                "throughPortMode0": metrics["throughRatio"],
                "crossPortMode0": metrics["crossRatio"],
            },
            "timing": {
                "until": until,
                "resolution": resolution,
            },
        },
        "acceptance": acceptance,
        "acceptanceStatus": "surrogate_accepted_candidate" if accepted else "surrogate_gap_probe_only",
        "gapToAcceptance": _gap_to_acceptance(
            useful_transmission=metrics["usefulTransmission"],
            insertion_loss_db=metrics["insertionLossDb"],
            reflection_ratio=metrics["reflectionRatio"],
            crosstalk_ratio=metrics["crosstalkRatio"],
            imbalance_ratio=metrics["imbalanceRatio"],
            normalization_reliable=metrics["normalizationReliable"],
            output_port_normalization_flux=metrics["outputPortNormalizationFlux"],
            device=device,
            acceptance=acceptance,
        ),
        "calibrationProtocol": {
            "sourceCheck": "node_alpha_surrogate_only",
            "referenceCheck": "analytical_straight_waveguide_reference",
            "reflectionCheck": "analytical_input_reference_delta",
            "nextValidation": [
                "install MEEP/MPB and rerun eigenmode-device-run",
                "extract port S-parameters with MPB mode decomposition",
                "repeat at resolution >= 16 and 3D geometry before GDS promotion",
            ],
        },
        "limitations": [
            "Analytical surrogate, not a MEEP/FDTD result.",
            "Not foundry-calibrated and not a wafer measurement.",
            "Only suitable for local ranking and sensitivity exploration.",
            "Prototype readiness gates must continue to require FDTD, S-parameters, PDK, and lab evidence.",
        ],
    }


def _surrogate_flux_pair(
    *,
    device: str,
    coupling_gap_um: float,
    coupling_length_um: float,
    phase_shift_rad: float,
    waveguide_width_um: float,
) -> tuple[dict[str, float], dict[str, float]]:
    output_norm = 1e-4 * max(0.2, 1.0 - 3.0 * abs(waveguide_width_um - 0.45))
    through_ratio, cross_ratio, reflection_ratio = _surrogate_ratios(
        device=device,
        coupling_gap_um=coupling_gap_um,
        coupling_length_um=coupling_length_um,
        phase_shift_rad=phase_shift_rad,
        waveguide_width_um=waveguide_width_um,
    )
    reference = {"inputFlux": 1.0, "throughFlux": output_norm, "crossFlux": 0.0}
    measured = {
        "inputFlux": 1.0 + reflection_ratio,
        "throughFlux": through_ratio * output_norm,
        "crossFlux": cross_ratio * output_norm,
    }
    return reference, measured


def _surrogate_ratios(
    *,
    device: str,
    coupling_gap_um: float,
    coupling_length_um: float,
    phase_shift_rad: float,
    waveguide_width_um: float,
) -> tuple[float, float, float]:
    width_penalty = min(0.12, 1.5 * abs(waveguide_width_um - 0.45))
    gap_penalty = max(0.0, coupling_gap_um - 0.18)
    if device == "coupler":
        angle = coupling_length_um * math.exp(-8.0 * coupling_gap_um) / 3.3
        cross = 0.92 * (math.sin(angle) ** 2)
        through = 0.92 * (math.cos(angle) ** 2)
        reflection = 0.01 + 0.15 * max(0.0, 0.16 - coupling_gap_um) + width_penalty
    elif device in {"mzi", "phase-shifter"}:
        balance_angle = coupling_length_um * math.exp(-8.5 * coupling_gap_um) / 3.0
        split = math.sin(balance_angle) ** 2
        phase_leakage = 0.025 * abs(math.sin(phase_shift_rad))
        cross = min(0.9, 0.9 * split + phase_leakage)
        through = max(0.0, 0.92 - 0.08 * abs(math.cos(phase_shift_rad)) - cross * 0.08)
        reflection = 0.008 + 0.04 * abs(math.sin(phase_shift_rad / 2.0)) + width_penalty
    else:
        balance_angle = coupling_length_um * math.exp(-8.0 * coupling_gap_um) / 3.1
        split = math.sin(balance_angle) ** 2
        cross = 4.0 * split
        through = 4.0 * (1.0 - split)
        crosstalk_balance = abs(through - cross)
        reflection = 0.018 + 0.08 * abs(math.sin((phase_shift_rad - math.pi) / 2.0)) + 0.01 * crosstalk_balance
    reflection = min(max(reflection + gap_penalty, 0.0), 1.0)
    return max(0.0, through), max(0.0, cross), reflection


def _normalized_flux_metrics(*, device: str, reference: dict[str, float], measured: dict[str, float]) -> dict[str, float]:
    input_norm = max(abs(reference["inputFlux"]), 1e-18)
    output_norm = max(abs(reference["throughFlux"]), 1e-18)
    reflected_flux = measured["inputFlux"] - reference["inputFlux"]
    through_ratio = abs(measured["throughFlux"]) / output_norm
    cross_ratio = abs(measured["crossFlux"]) / output_norm
    reflection_ratio = abs(reflected_flux) / input_norm
    useful_transmission = through_ratio + cross_ratio
    crosstalk_ratio = cross_ratio if device in {"mzi", "phase-shifter"} else abs(through_ratio - cross_ratio)
    bounded_transmission = min(max(useful_transmission, 0.0), 1.0)
    insertion_loss_db = max(0.0, -10.0 * math.log10(max(bounded_transmission, 1e-12)))
    imbalance_ratio = abs(through_ratio - cross_ratio)
    normalization_reliable = output_norm >= MIN_OUTPUT_PORT_NORMALIZATION_FLUX
    return {
        "inputNormalizationFlux": input_norm,
        "outputPortNormalizationFlux": output_norm,
        "reflectionFlux": reflected_flux,
        "throughRatio": through_ratio,
        "crossRatio": cross_ratio,
        "reflectionRatio": reflection_ratio,
        "usefulTransmission": useful_transmission,
        "insertionLossDb": insertion_loss_db,
        "crosstalkRatio": crosstalk_ratio,
        "imbalanceRatio": imbalance_ratio,
        "normalizationReliable": normalization_reliable,
    }


def _run_calibrated_pair(
    mp: Any,
    blueprint: Blueprint,
    *,
    device: str,
    resolution: int,
    until: float,
    coupling_gap_um: float,
    coupling_length_um: float,
    phase_shift_rad: float,
    waveguide_width_um: float,
    source_model: str,
) -> tuple[dict[str, float], dict[str, float], str]:
    use_eigenmode = source_model == "eigenmode" and hasattr(mp, "EigenModeSource")
    actual_source_model = "eigenmode" if use_eigenmode else "gaussian_fallback"
    reference = _run_cell(
        mp,
        blueprint,
        device="reference",
        resolution=resolution,
        until=until,
        coupling_gap_um=coupling_gap_um,
        coupling_length_um=coupling_length_um,
        phase_shift_rad=phase_shift_rad,
        waveguide_width_um=waveguide_width_um,
        use_eigenmode=use_eigenmode,
    )
    measured = _run_cell(
        mp,
        blueprint,
        device=device,
        resolution=resolution,
        until=until,
        coupling_gap_um=coupling_gap_um,
        coupling_length_um=coupling_length_um,
        phase_shift_rad=phase_shift_rad,
        waveguide_width_um=waveguide_width_um,
        use_eigenmode=use_eigenmode,
    )
    return reference, measured, actual_source_model


def _run_cell(
    mp: Any,
    blueprint: Blueprint,
    *,
    device: str,
    resolution: int,
    until: float,
    coupling_gap_um: float,
    coupling_length_um: float,
    phase_shift_rad: float,
    waveguide_width_um: float,
    use_eigenmode: bool,
) -> dict[str, float]:
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
    source_width = max(1.2 * width, 0.8)

    simulation = mp.Simulation(
        cell_size=mp.Vector3(cell_x, cell_y, 0),
        boundary_layers=[mp.PML(pml_um)],
        geometry=_make_geometry(
            mp,
            device=device,
            width=width,
            lane_sep=lane_sep,
            coupling_length_um=coupling_length_um,
            phase_shift_rad=phase_shift_rad,
        ),
        sources=[
            _make_source(
                mp,
                frequency=frequency,
                lower_y=lower_y,
                source_x=source_x,
                source_width=source_width,
                use_eigenmode=use_eigenmode,
            )
        ],
        resolution=resolution,
    )
    input_monitor = simulation.add_flux(
        frequency,
        0,
        1,
        mp.FluxRegion(center=mp.Vector3(input_monitor_x, lower_y, 0), size=mp.Vector3(0, source_width, 0)),
    )
    through = simulation.add_flux(
        frequency,
        0,
        1,
        mp.FluxRegion(center=mp.Vector3(output_monitor_x, lower_y, 0), size=mp.Vector3(0, source_width, 0)),
    )
    cross = simulation.add_flux(
        frequency,
        0,
        1,
        mp.FluxRegion(center=mp.Vector3(output_monitor_x, upper_y, 0), size=mp.Vector3(0, source_width, 0)),
    )
    simulation.run(until=until)
    return {
        "inputFlux": float(mp.get_fluxes(input_monitor)[0]),
        "throughFlux": float(mp.get_fluxes(through)[0]),
        "crossFlux": float(mp.get_fluxes(cross)[0]),
    }


def _make_geometry(
    mp: Any,
    *,
    device: str,
    width: float,
    lane_sep: float,
    coupling_length_um: float,
    phase_shift_rad: float,
) -> list[Any]:
    eps_si = 12.0
    lower_y = -lane_sep / 2
    upper_y = lane_sep / 2
    geometry = [
        mp.Block(size=mp.Vector3(mp.inf, width, mp.inf), center=mp.Vector3(0, lower_y, 0), material=mp.Medium(epsilon=eps_si)),
        mp.Block(size=mp.Vector3(mp.inf, width, mp.inf), center=mp.Vector3(0, upper_y, 0), material=mp.Medium(epsilon=eps_si)),
    ]
    if device in {"mzi", "phase-shifter", "truth-switch"}:
        phase_eps = eps_si * (1 + min(abs(phase_shift_rad), math.pi) * 0.01)
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
    return geometry


def _make_source(
    mp: Any,
    *,
    frequency: float,
    lower_y: float,
    source_x: float,
    source_width: float,
    use_eigenmode: bool,
) -> Any:
    source = mp.GaussianSource(frequency=frequency, fwidth=0.2 * frequency)
    center = mp.Vector3(source_x, lower_y, 0)
    size = mp.Vector3(0, source_width, 0)
    if use_eigenmode:
        return mp.EigenModeSource(
            source,
            center=center,
            size=size,
            eig_band=1,
            eig_parity=getattr(mp, "ODD_Z", getattr(mp, "NO_PARITY", 0)),
        )
    return mp.Source(source, component=mp.Ez, center=center, size=size)


def _geometry_spec(
    blueprint: Blueprint,
    *,
    device: str,
    coupling_gap_um: float,
    coupling_length_um: float,
    phase_shift_rad: float,
    waveguide_width_um: float,
    resolution: int,
    until: float,
) -> dict[str, Any]:
    lane_sep = waveguide_width_um + coupling_gap_um
    cell_x = max(10.0, coupling_length_um + 8.0)
    cell_y = max(4.0, 3.0 * lane_sep + 2.0)
    return {
        "cellXUm": cell_x,
        "cellYUm": cell_y,
        "waveguideWidthUm": waveguide_width_um,
        "couplingGapUm": coupling_gap_um,
        "couplingLengthUm": coupling_length_um,
        "phaseShiftRad": phase_shift_rad,
        "laneSeparationUm": lane_sep,
        "laserWavelengthNm": blueprint.spatial_model.laser_wavelength_nm,
        "resolution": resolution,
        "until": until,
        "couplingRegionModel": "parallel_waveguides_no_core_cutout",
    }


def _accepted(
    useful_transmission: float,
    insertion_loss_db: float,
    reflection_ratio: float,
    crosstalk_ratio: float,
    imbalance_ratio: float,
    normalization_reliable: bool,
    device: str,
) -> bool:
    if not normalization_reliable:
        return False
    if insertion_loss_db > 1.0 or reflection_ratio > 0.05 or useful_transmission < 0.5:
        return False
    if crosstalk_ratio > 0.05:
        return False
    return True


def _validation_tier(resolution: int, until: float) -> str:
    if resolution >= 16 and until >= 40:
        return "high_resolution_gap_probe"
    if resolution >= 12 and until >= 30:
        return "medium_resolution_gap_probe"
    return "first_pass_gap_probe"


def _gap_to_acceptance(
    *,
    useful_transmission: float,
    insertion_loss_db: float,
    reflection_ratio: float,
    crosstalk_ratio: float,
    imbalance_ratio: float,
    normalization_reliable: bool,
    output_port_normalization_flux: float,
    device: str,
    acceptance: dict[str, float],
) -> dict[str, Any]:
    min_useful = acceptance["minUsefulTransmission"]
    max_loss = acceptance["maxInsertionLossDb"]
    max_reflection = acceptance["maxReflectionRatio"]
    max_crosstalk = acceptance["maxCrosstalkRatio"]
    min_output_norm = acceptance["minOutputPortNormalizationFlux"]
    gap = {
        "normalizationReliable": normalization_reliable,
        "outputPortNormalizationFluxTarget": min_output_norm,
        "outputPortNormalizationFlux": output_port_normalization_flux,
        "usefulTransmissionTarget": min_useful,
        "usefulTransmission": useful_transmission,
        "usefulTransmissionFactorBelowTarget": min_useful / max(useful_transmission, 1e-18),
        "insertionLossDbTarget": max_loss,
        "insertionLossDb": insertion_loss_db,
        "insertionLossDbExcess": max(0.0, insertion_loss_db - max_loss),
        "reflectionRatioTarget": max_reflection,
        "reflectionRatio": reflection_ratio,
        "reflectionRatioExcess": max(0.0, reflection_ratio - max_reflection),
        "crosstalkRatioTarget": max_crosstalk,
        "crosstalkRatio": crosstalk_ratio,
        "crosstalkRatioExcess": max(0.0, crosstalk_ratio - max_crosstalk),
    }
    if device in {"mzi", "phase-shifter"}:
        gap["operatingPoint"] = "through_state_low_leakage"
        gap["imbalanceRatio"] = imbalance_ratio
        gap["imbalanceRatioNote"] = (
            "Not an acceptance blocker for through-state MZI/phase-shifter operation; "
            "balanced splitting must be swept as a separate operating point."
        )
    return gap
