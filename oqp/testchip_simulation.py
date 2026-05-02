"""Simulation-only testchip pipeline for OQP-HRM device and fusion cells."""

from __future__ import annotations

from itertools import product
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

from .blueprint import Blueprint
from .device_sweep import run_device_sweep
from .primitive import generate_fusion_primitive
from .report import write_json_report


TESTCHIP_DEVICES = ("coupler", "mzi", "phase-shifter", "truth-switch")
DEFAULT_WAVELENGTHS_NM = [1520.0, 1550.0, 1580.0]
DEFAULT_WIDTH_ERRORS_NM = [-10.0, 0.0, 10.0]
DEFAULT_GAP_ERRORS_NM = [-10.0, 0.0, 10.0]
DEFAULT_PHASE_ERRORS_RAD = [-0.005, 0.0, 0.005]
DEFAULT_TEMPERATURE_DELTAS_C = [-5.0, 0.0, 5.0]


def run_testchip_simulation(
    blueprint: Blueprint,
    *,
    out_dir: str | Path | None = None,
    device_sweep_path: str | Path | None = None,
    wavelengths_nm: list[float] | None = None,
    width_errors_nm: list[float] | None = None,
    gap_errors_nm: list[float] | None = None,
    phase_errors_rad: list[float] | None = None,
    temperature_deltas_c: list[float] | None = None,
    shots: int = 10000,
) -> dict[str, Any]:
    """Run the full local testchip simulation pipeline.

    The pipeline is intentionally simulation-only. It creates virtual S-parameter
    and yield data for ranking and experiment planning, not foundry signoff.
    """

    out_path = Path(out_dir) if out_dir else None
    wavelengths = wavelengths_nm or DEFAULT_WAVELENGTHS_NM
    width_errors = width_errors_nm or DEFAULT_WIDTH_ERRORS_NM
    gap_errors = gap_errors_nm or DEFAULT_GAP_ERRORS_NM
    phase_errors = phase_errors_rad or DEFAULT_PHASE_ERRORS_RAD
    temp_deltas = temperature_deltas_c or DEFAULT_TEMPERATURE_DELTAS_C

    plan = _testchip_plan(blueprint)
    if device_sweep_path:
        device_sweep = _read_json(Path(device_sweep_path))
        device_sweep_artifact = str(device_sweep_path)
    else:
        device_sweep_out = out_path / "device-sweep" if out_path else None
        device_sweep = run_device_sweep(
            blueprint,
            devices=list(TESTCHIP_DEVICES),
            coupling_gaps_um=[0.10, 0.12, 0.14, 0.16, 0.18, 0.22],
            coupling_lengths_um=[
                0.5,
                5.4186008492,
                6.3587870021,
                7.4621056733,
                8.0,
                8.7568621281,
                10.2762729031,
            ],
            phase_shifts_rad=[0.0, math.pi],
            waveguide_widths_um=[0.45],
            resolution=16,
            until=40,
            max_runs=336,
            out_dir=device_sweep_out,
        )
        device_sweep_artifact = str(device_sweep_out / "device-sweep.json") if device_sweep_out else "in_memory"

    candidates = _per_device_candidates(device_sweep)
    virtual_sparams = _virtual_sparameters(
        blueprint,
        candidates=candidates,
        wavelengths_nm=wavelengths,
    )
    yield_sweep = _yield_sweep(
        blueprint,
        candidates=candidates,
        width_errors_nm=width_errors,
        gap_errors_nm=gap_errors,
        phase_errors_rad=phase_errors,
        temperature_deltas_c=temp_deltas,
    )
    fusion_device = _fusion_device_candidate(candidates, device_sweep.get("champion"))
    fusion = generate_fusion_primitive(
        blueprint,
        device_report=fusion_device,
        source_efficiency=0.85,
        detector_efficiency=0.9,
        feed_forward_latency_ns=5.0,
    )
    fusion_testcell = _fusion_testcell_report(
        fusion=fusion,
        device_report=fusion_device,
        shots=shots,
    )

    artifacts = {
        "testchipPlan": str(out_path / "testchip-plan.json") if out_path else "in_memory",
        "deviceSweep": device_sweep_artifact,
        "virtualSParameters": str(out_path / "virtual-sparameters.json") if out_path else "in_memory",
        "yieldSweep": str(out_path / "yield-sweep.json") if out_path else "in_memory",
        "fusionTestcell": str(out_path / "fusion-testcell-report.json") if out_path else "in_memory",
    }
    checklist = _completion_checklist(
        plan=plan,
        device_sweep=device_sweep,
        virtual_sparams=virtual_sparams,
        yield_sweep=yield_sweep,
        fusion_testcell=fusion_testcell,
        artifacts=artifacts,
    )
    simulation_complete = all(item["status"] == "complete" for item in checklist)
    device_acceptance_complete = device_sweep.get("status") == "all_requested_devices_accepted"
    yield_pass = yield_sweep["summary"]["allDevicesYieldPassing"]
    fusion_pass = fusion_testcell["readinessFlags"]["fusionTestcellPass"]
    report = {
        "schemaVersion": "open-quantum.testchip-simulation.v1",
        "sourcePath": blueprint.source_path,
        "objective": "Simulate the OQP-HRM foundry testchip before fabrication.",
        "scope": {
            "claim": "complete_simulation_only_testchip_package",
            "simulatedOnly": True,
            "virtualFoundry": True,
            "notEvidenceFor": [
                "foundry-calibrated S-parameters",
                "foundry PDK readiness",
                "DRC/LVS signoff",
                "wafer measurement",
                "hardware primitive demonstration",
            ],
        },
        "backendReadiness": _backend_readiness(),
        "materialStack": _material_stack(),
        "testchipPlan": plan,
        "artifacts": artifacts,
        "deviceSweep": _device_sweep_summary(device_sweep),
        "virtualSParameters": virtual_sparams,
        "yieldSweep": yield_sweep,
        "fusionTestcell": fusion_testcell,
        "readinessFlags": {
            "testchipSimulationComplete": simulation_complete,
            "fdtdMpbReadyPlanComplete": True,
            "deviceSweepAccepted": device_acceptance_complete,
            "virtualSparametersGenerated": virtual_sparams["summary"]["modelCount"] == len(TESTCHIP_DEVICES),
            "yieldSweepPassing": yield_pass,
            "fusionTestcellPass": fusion_pass,
            "readyForFabrication": False,
            "requiresRealFoundryPdk": True,
            "requiresMeasuredSparameters": True,
        },
        "completionAudit": {
            "objective": "Build the testchip simulation pipeline: FDTD/MPB-ready device sweeps, virtual S-parameters, yield sweeps, and fusion testcell report.",
            "successCriteria": checklist,
            "missingOrFailedRequirements": [item for item in checklist if item["status"] != "complete"],
        },
        "nextRealWorldInputs": [
            "Install MEEP/MPB and rerun device cells as FDTD/MPB, not Node Alpha surrogate.",
            "Replace generic Si/SiO2 stack with a version-locked foundry PDK.",
            "Generate real Touchstone/compact-model S-parameters from 3D/MPB or measurement.",
            "Run DRC/LVS on the foundry testchip GDS.",
            "Measure wafer/device test structures and replace virtual yield assumptions.",
        ],
        "summary": {
            "status": "testchip_simulation_complete" if simulation_complete else "testchip_simulation_incomplete",
            "deviceStatus": device_sweep.get("status"),
            "deviceRunCount": device_sweep.get("runCount", 0),
            "virtualSparameterModelCount": virtual_sparams["summary"]["modelCount"],
            "yieldAcceptedDeviceCount": yield_sweep["summary"]["acceptedDeviceCount"],
            "yieldRequiredDeviceCount": len(TESTCHIP_DEVICES),
            "fusionStatus": fusion_testcell["status"],
            "fabricationStatus": "not_fabrication_ready_without_real_pdk_and_sparameters",
        },
    }
    if out_path:
        write_json_report(plan, out_path / "testchip-plan.json")
        write_json_report(virtual_sparams, out_path / "virtual-sparameters.json")
        write_json_report(yield_sweep, out_path / "yield-sweep.json")
        write_json_report(fusion_testcell, out_path / "fusion-testcell-report.json")
        write_json_report(report, out_path / "testchip-simulation.json")
    return report


def _testchip_plan(blueprint: Blueprint) -> dict[str, Any]:
    return {
        "schemaVersion": "open-quantum.testchip-plan.v1",
        "sourcePath": blueprint.source_path,
        "chipClass": "generic_siph_device_and_fusion_testchip",
        "testStructures": [
            _structure("directional_coupler_array", "coupler", ["bar", "cross", "input_reflection"]),
            _structure("mzi_phase_ladder", "mzi", ["through", "cross", "extinction_ratio", "phase_response"]),
            _structure("phase_shifter_linearity", "phase-shifter", ["phase_shift", "insertion_loss", "thermal_drift"]),
            _structure("truth_switch_state_table", "truth-switch", ["truth_state_00", "truth_state_11", "reflection", "crosstalk"]),
            _structure("two_qubit_heralded_fusion_cell", "fusion-testcell", ["herald_ports", "pnr_readout", "feed_forward_marker"]),
        ],
        "fdtdMpbReadyPlan": {
            "deviceCommand": "oqp eigenmode-device-run <blueprint> --device <device> --resolution 16 --until 40",
            "sweepCommand": "oqp device-sweep <blueprint> --devices coupler,mzi,phase-shifter,truth-switch --resolution 16 --until 40",
            "mpbExtraction": "extract mode-overlap and port S-parameters for each accepted local candidate",
            "backendFallback": "Node Alpha surrogate is allowed only for local planning when MEEP/MPB are unavailable.",
        },
        "acceptanceTargets": {
            "maxInsertionLossDb": 1.0,
            "maxReflectionRatio": 0.05,
            "maxCrosstalkRatio": 0.05,
            "minUsefulTransmission": 0.5,
            "minFusionProcessFidelity": 0.99,
            "minHeraldingSuccessProbability": 0.01,
        },
        "layoutEnvelope": {
            "physicalModes": blueprint.spatial_model.waveguide_count,
            "laserWavelengthNm": blueprint.spatial_model.laser_wavelength_nm,
            "nominalWaveguideWidthUm": 0.45,
            "nominalSiThicknessNm": 220,
            "fiberArrayPitchUm": 127,
        },
    }


def _structure(name: str, device: str, measurements: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "device": device,
        "ports": ["optical_in", "through_out", "cross_out", "reflection_monitor"],
        "virtualMeasurements": measurements,
    }


def _backend_readiness() -> dict[str, Any]:
    return {
        "meep": _module_probe("meep"),
        "mpb": _module_probe("meep.mpb"),
        "numpy": _module_probe("numpy"),
        "scipy": _module_probe("scipy"),
        "strawberryfields": _module_probe("strawberryfields"),
        "status": "surrogate_only_until_missing_backends_are_installed",
    }


def _module_probe(module: str) -> dict[str, Any]:
    try:
        spec = importlib.util.find_spec(module)
    except ModuleNotFoundError:
        spec = None
    return {
        "available": spec is not None,
        "module": module,
        "requiredFor": _module_requirement(module),
    }


def _module_requirement(module: str) -> str:
    if module == "meep":
        return "FDTD device cells"
    if module == "meep.mpb":
        return "MPB mode decomposition and S-parameter extraction"
    if module == "strawberryfields":
        return "Gaussian topology validation"
    return "numerical simulation backend"


def _material_stack() -> dict[str, Any]:
    return {
        "schemaVersion": "open-quantum.material-stack.v1",
        "name": "generic_si_sio2_220nm_surrogate",
        "validationLevel": "generic_material_approximation_not_foundry_pdk",
        "layers": [
            {"name": "si_device", "thicknessNm": 220, "refractiveIndexAt1550Nm": 3.48},
            {"name": "box_sio2", "thicknessNm": 2000, "refractiveIndexAt1550Nm": 1.44},
            {"name": "cladding_sio2", "thicknessNm": 1500, "refractiveIndexAt1550Nm": 1.44},
            {"name": "heater_metal", "thicknessNm": 100, "model": "lumped_phase_actuator_placeholder"},
        ],
        "limitations": [
            "Not a foundry PDK.",
            "No process-corner tables, CMP, sidewall angle, dopant, metal stack, or package rules.",
        ],
    }


def _virtual_sparameters(
    blueprint: Blueprint,
    *,
    candidates: dict[str, dict[str, Any]],
    wavelengths_nm: list[float],
) -> dict[str, Any]:
    models = {}
    for device in TESTCHIP_DEVICES:
        candidate = candidates.get(device)
        if not candidate:
            continue
        metrics = candidate.get("fdtdMetrics", {})
        samples = []
        for wavelength in wavelengths_nm:
            offset = abs(wavelength - blueprint.spatial_model.laser_wavelength_nm)
            reflection = min(0.95, float(metrics.get("reflectionRatio", 1.0)) + 1e-5 * offset)
            crosstalk = min(0.95, float(metrics.get("crosstalkRatio", 1.0)) + 2e-5 * offset)
            available_transmission = max(0.0, 1.0 - reflection - crosstalk - 0.001 * offset / 30.0)
            useful = min(float(metrics.get("usefulTransmission", 0.0)), available_transmission)
            samples.append(
                {
                    "wavelengthNm": wavelength,
                    "s11ReflectionPower": reflection,
                    "s21ThroughPower": useful,
                    "s31CrosstalkPower": crosstalk,
                    "insertionLossDb": _loss_db(useful),
                    "passivePowerSum": reflection + useful + crosstalk,
                }
            )
        models[device] = {
            "device": device,
            "candidateId": candidate.get("candidateId"),
            "validationLevel": "virtual_surrogate_sparameter_not_foundry",
            "foundryCalibrated": False,
            "wavelengthRangeNm": [min(wavelengths_nm), max(wavelengths_nm)],
            "samples": samples,
            "acceptance": _sparam_acceptance(samples),
        }
    accepted = [device for device, model in models.items() if model["acceptance"]["accepted"]]
    return {
        "schemaVersion": "open-quantum.virtual-sparameters.v1",
        "sourcePath": blueprint.source_path,
        "models": models,
        "summary": {
            "modelCount": len(models),
            "acceptedModelCount": len(accepted),
            "requiredModelCount": len(TESTCHIP_DEVICES),
            "allVirtualModelsAccepted": len(accepted) == len(TESTCHIP_DEVICES),
        },
        "limitations": [
            "Virtual S-parameters are generated from Node Alpha device metrics.",
            "These are not Touchstone files and not foundry-calibrated compact models.",
        ],
    }


def _yield_sweep(
    blueprint: Blueprint,
    *,
    candidates: dict[str, dict[str, Any]],
    width_errors_nm: list[float],
    gap_errors_nm: list[float],
    phase_errors_rad: list[float],
    temperature_deltas_c: list[float],
) -> dict[str, Any]:
    device_results = {}
    for device in TESTCHIP_DEVICES:
        candidate = candidates.get(device)
        if not candidate:
            device_results[device] = {"device": device, "status": "missing_candidate", "accepted": False}
            continue
        variants = []
        for width_error, gap_error, phase_error, temp_delta in product(
            width_errors_nm,
            gap_errors_nm,
            phase_errors_rad,
            temperature_deltas_c,
        ):
            metrics = _perturbed_metrics(
                candidate.get("fdtdMetrics", {}),
                width_error_nm=width_error,
                gap_error_nm=gap_error,
                phase_error_rad=phase_error,
                temperature_delta_c=temp_delta,
            )
            variants.append(
                {
                    "widthErrorNm": width_error,
                    "gapErrorNm": gap_error,
                    "phaseErrorRad": phase_error,
                    "temperatureDeltaC": temp_delta,
                    "metrics": metrics,
                    "accepted": _accepted_metrics(metrics),
                }
            )
        accepted_count = sum(1 for item in variants if item["accepted"])
        device_results[device] = {
            "device": device,
            "candidateId": candidate.get("candidateId"),
            "variantCount": len(variants),
            "acceptedVariantCount": accepted_count,
            "estimatedYield": accepted_count / max(1, len(variants)),
            "accepted": accepted_count == len(variants),
            "worstCase": _worst_variant(variants),
        }
    accepted_devices = [item for item in device_results.values() if item.get("accepted")]
    return {
        "schemaVersion": "open-quantum.testchip-yield-sweep.v1",
        "sourcePath": blueprint.source_path,
        "sweepAxes": {
            "widthErrorsNm": width_errors_nm,
            "gapErrorsNm": gap_errors_nm,
            "phaseErrorsRad": phase_errors_rad,
            "temperatureDeltasC": temperature_deltas_c,
        },
        "deviceResults": device_results,
        "summary": {
            "requiredDeviceCount": len(TESTCHIP_DEVICES),
            "acceptedDeviceCount": len(accepted_devices),
            "allDevicesYieldPassing": len(accepted_devices) == len(TESTCHIP_DEVICES),
            "systemYieldEstimate": min((item.get("estimatedYield", 0.0) for item in device_results.values()), default=0.0),
        },
        "limitations": [
            "Deterministic tolerance grid, not wafer statistics.",
            "No lithography, etch-depth, sidewall, CMP, package, or temperature-controller distributions from a foundry.",
        ],
    }


def _fusion_testcell_report(
    *,
    fusion: dict[str, Any],
    device_report: dict[str, Any] | None,
    shots: int,
) -> dict[str, Any]:
    success_probability = float((fusion.get("heraldingModel") or {}).get("estimatedHeraldingSuccessProbability", 0.0))
    process_fidelity = float((fusion.get("qualityModel") or {}).get("estimatedProcessFidelity", 0.0))
    heralded_events = int(round(shots * success_probability))
    accepted = fusion.get("status") == "primitive_ready" and process_fidelity >= 0.99 and success_probability >= 0.01
    return {
        "schemaVersion": "open-quantum.fusion-testcell-simulation.v1",
        "status": "fusion_testcell_pass" if accepted else "fusion_testcell_gap",
        "deviceCandidateId": device_report.get("candidateId") if device_report else None,
        "device": device_report.get("device") if device_report else None,
        "shots": shots,
        "virtualMeasurement": {
            "heraldedEvents": heralded_events,
            "estimatedHeraldingSuccessProbability": success_probability,
            "estimatedProcessFidelity": process_fidelity,
            "feedForwardLatencyNs": (fusion.get("qualityModel") or {}).get("feedForwardLatencyNs"),
        },
        "readinessFlags": {
            "fusionTestcellPass": accepted,
            "simulatedOnly": True,
            "experimentallyDemonstrated": False,
        },
        "fusionPrimitive": fusion,
        "limitations": [
            "Virtual fusion measurement generated from analytical device evidence.",
            "No measured shots, no detector data, and no verified primitive-demo dataset.",
        ],
    }


def _completion_checklist(
    *,
    plan: dict[str, Any],
    device_sweep: dict[str, Any],
    virtual_sparams: dict[str, Any],
    yield_sweep: dict[str, Any],
    fusion_testcell: dict[str, Any],
    artifacts: dict[str, str],
) -> list[dict[str, Any]]:
    return [
        _check("testchip_plan", "Define test structures, virtual measurements, material stack, and FDTD/MPB-ready plan.", bool(plan), [artifacts["testchipPlan"]], []),
        _check(
            "device_sweep",
            "Run testchip Device sweep for coupler, MZI, phase-shifter, and truth-switch.",
            device_sweep.get("status") == "all_requested_devices_accepted",
            [artifacts["deviceSweep"]],
            [] if device_sweep.get("status") == "all_requested_devices_accepted" else [str(device_sweep.get("status"))],
        ),
        _check(
            "virtual_sparameters",
            "Generate virtual S-parameter-like models for all four core devices.",
            virtual_sparams["summary"]["modelCount"] == len(TESTCHIP_DEVICES),
            [artifacts["virtualSParameters"]],
            virtual_sparams.get("limitations", []),
        ),
        _check(
            "yield_sweep",
            "Run deterministic tolerance/yield sweep across width, gap, phase, and temperature axes.",
            yield_sweep["summary"]["allDevicesYieldPassing"],
            [artifacts["yieldSweep"]],
            yield_sweep.get("limitations", []),
        ),
        _check(
            "fusion_testcell",
            "Simulate two-qubit heralded fusion testcell and virtual measurement.",
            fusion_testcell["readinessFlags"]["fusionTestcellPass"],
            [artifacts["fusionTestcell"]],
            fusion_testcell.get("limitations", []),
        ),
        _check(
            "real_world_boundaries",
            "Mark missing real PDK, MEEP/MPB, Touchstone/S-parameter, DRC/LVS, wafer, and lab evidence.",
            True,
            [artifacts["testchipPlan"], artifacts["virtualSParameters"]],
            ["Simulation-only package; not fabrication readiness."],
        ),
    ]


def _device_sweep_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": report.get("schemaVersion"),
        "status": report.get("status"),
        "runCount": report.get("runCount"),
        "validationTier": report.get("validationTier"),
        "perDeviceChampions": {
            device: {
                "candidateId": candidate.get("candidateId"),
                "acceptanceStatus": candidate.get("acceptanceStatus"),
                "physicalValidationLevel": candidate.get("physicalValidationLevel"),
                "sourceModel": candidate.get("sourceModel"),
                "metrics": {
                    key: (candidate.get("fdtdMetrics") or {}).get(key)
                    for key in ("usefulTransmission", "insertionLossDb", "reflectionRatio", "crosstalkRatio")
                },
            }
            for device, candidate in (report.get("perDeviceChampions") or {}).items()
            if isinstance(candidate, dict)
        },
    }


def _per_device_candidates(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    champions = report.get("perDeviceChampions")
    return {device: candidate for device, candidate in champions.items()} if isinstance(champions, dict) else {}


def _fusion_device_candidate(candidates: dict[str, dict[str, Any]], champion: dict[str, Any] | None) -> dict[str, Any] | None:
    fusion_candidates = [
        candidate
        for device in ("truth-switch", "mzi", "coupler")
        if isinstance((candidate := candidates.get(device)), dict)
    ]
    if fusion_candidates:
        return max(fusion_candidates, key=_fusion_candidate_rank)
    return champion if isinstance(champion, dict) else None


def _fusion_candidate_rank(candidate: dict[str, Any]) -> tuple[int, int, float]:
    metrics = candidate.get("fdtdMetrics", {})
    through = float(metrics.get("throughRatio", 0.0))
    cross = float(metrics.get("crossRatio", 0.0))
    useful = float(metrics.get("usefulTransmission", through + cross))
    reflection = float(metrics.get("reflectionRatio", 1.0))
    crosstalk = float(metrics.get("crosstalkRatio", metrics.get("imbalanceRatio", abs(through - cross))))
    fidelity_penalty = (0.5 * reflection) + (0.25 * crosstalk) + (0.25 * max(0.0, 1.0 - useful))
    accepted = _accepted_metrics(
        {
            "usefulTransmission": useful,
            "insertionLossDb": float(metrics.get("insertionLossDb", 120.0)),
            "reflectionRatio": reflection,
            "crosstalkRatio": crosstalk,
        }
    )
    return (1 if accepted else 0, 1 if metrics.get("normalizationReliable") is not False else 0, -fidelity_penalty)


def _sparam_acceptance(samples: list[dict[str, float]]) -> dict[str, Any]:
    accepted = all(
        sample["insertionLossDb"] <= 1.0
        and sample["s11ReflectionPower"] <= 0.05
        and sample["s31CrosstalkPower"] <= 0.05
        and sample["passivePowerSum"] <= 1.000001
        for sample in samples
    )
    return {
        "accepted": accepted,
        "maxInsertionLossDb": max((sample["insertionLossDb"] for sample in samples), default=math.inf),
        "maxReflectionPower": max((sample["s11ReflectionPower"] for sample in samples), default=math.inf),
        "maxCrosstalkPower": max((sample["s31CrosstalkPower"] for sample in samples), default=math.inf),
    }


def _perturbed_metrics(
    metrics: dict[str, Any],
    *,
    width_error_nm: float,
    gap_error_nm: float,
    phase_error_rad: float,
    temperature_delta_c: float,
) -> dict[str, float]:
    base_useful = min(1.0, float(metrics.get("usefulTransmission", 0.0)))
    width_term = abs(width_error_nm)
    gap_term = abs(gap_error_nm)
    phase_term = abs(phase_error_rad)
    temp_term = abs(temperature_delta_c)
    transmission_penalty = 0.0015 * width_term + 0.001 * gap_term + 0.35 * phase_term + 0.0005 * temp_term
    useful = max(0.0, base_useful * (1.0 - transmission_penalty))
    reflection = min(
        1.0,
        float(metrics.get("reflectionRatio", 1.0))
        + 0.00025 * width_term
        + 0.00015 * gap_term
        + 0.00008 * temp_term,
    )
    crosstalk = min(
        1.0,
        float(metrics.get("crosstalkRatio", 1.0))
        + 0.00045 * width_term
        + 0.00045 * gap_term
        + 0.04 * phase_term
        + 0.00005 * temp_term,
    )
    return {
        "usefulTransmission": useful,
        "insertionLossDb": _loss_db(useful),
        "reflectionRatio": reflection,
        "crosstalkRatio": crosstalk,
    }


def _accepted_metrics(metrics: dict[str, float]) -> bool:
    return (
        metrics["usefulTransmission"] >= 0.5
        and metrics["insertionLossDb"] <= 1.0
        and metrics["reflectionRatio"] <= 0.05
        and metrics["crosstalkRatio"] <= 0.05
    )


def _worst_variant(variants: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not variants:
        return None
    return max(
        variants,
        key=lambda item: (
            item["metrics"]["crosstalkRatio"],
            item["metrics"]["reflectionRatio"],
            item["metrics"]["insertionLossDb"],
        ),
    )


def _loss_db(transmission: float) -> float:
    return max(0.0, -10.0 * math.log10(max(transmission, 1e-12)))


def _check(
    criterion_id: str,
    requirement: str,
    passed: bool,
    evidence: list[str],
    caveats: list[str],
) -> dict[str, Any]:
    return {
        "id": criterion_id,
        "requirement": requirement,
        "status": "complete" if passed else "missing_or_failed",
        "evidence": evidence,
        "caveats": caveats,
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}
