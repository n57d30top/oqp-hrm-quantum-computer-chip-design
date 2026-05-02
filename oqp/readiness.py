"""Control-system and laboratory readiness reports."""

from __future__ import annotations

from typing import Any

from .blueprint import Blueprint


def generate_control_readiness(
    blueprint: Blueprint,
    *,
    feed_forward_latency_ns: float = 5.0,
    detector_jitter_ps: float = 50.0,
) -> dict[str, Any]:
    spatial = blueprint.spatial_model
    io_channels = spatial.waveguide_count
    phase_channels = spatial.interferometer_count
    blockers = [
        "No FPGA/ASIC timing fabric selected.",
        "No DAC/driver stack selected for phase shifters and truth-switch actuators.",
        "No calibrated detector-to-switch latency measurement.",
        "No hardware-in-the-loop shot scheduler.",
    ]
    return {
        "schemaVersion": "open-quantum.control-readiness.v1",
        "sourcePath": blueprint.source_path,
        "controlReady": False,
        "timingBudget": {
            "feedForwardLatencyNs": feed_forward_latency_ns,
            "detectorJitterPs": detector_jitter_ps,
            "targetDecisionLatencyNs": 10.0,
            "targetClockJitterPs": 10.0,
        },
        "hardwareRequirements": {
            "fpgaOrAsic": "required",
            "tdcChannels": io_channels,
            "detectorReadoutChannels": io_channels,
            "phaseDriverChannels": phase_channels,
            "switchDriverChannels": max(1, phase_channels // 2),
            "shotScheduler": "required",
        },
        "shotSchedulerInterface": {
            "inputs": ["detector_time_tags", "source_bank_state", "active_calibration_frame"],
            "outputs": ["phase_updates", "switch_commands", "accepted_shot_records", "reset_commands"],
            "latencyBudgetNs": feed_forward_latency_ns,
            "hilStatus": "not_verified",
        },
        "driverRequirements": {
            "phaseDriverBandwidthGHz": 1.0,
            "switchDriverRiseTimeNs": 1.0,
            "dacResolutionBits": 14,
            "clockDistributionJitterPs": 10.0,
        },
        "blockers": blockers,
    }


def generate_lab_readiness(
    blueprint: Blueprint,
    *,
    detector_type: str = "SNSPD",
    laser_wavelength_nm: int | None = None,
) -> dict[str, Any]:
    spatial = blueprint.spatial_model
    wavelength = laser_wavelength_nm or spatial.laser_wavelength_nm
    cryo_required = detector_type.upper() in {"SNSPD", "TES"}
    return {
        "schemaVersion": "open-quantum.lab-readiness.v1",
        "sourcePath": blueprint.source_path,
        "labReady": False,
        "opticalBench": {
            "laserWavelengthNm": wavelength,
            "laserLinewidthTargetMHz": 1.0,
            "fiberArrayChannels": spatial.waveguide_count,
            "polarizationControl": "required",
            "thermalStabilization": "required",
        },
        "detectors": {
            "type": detector_type,
            "cryogenicSystemRequired": cryo_required,
            "targetEfficiency": 0.95,
            "targetDarkCountHz": 10,
            "targetTimingJitterPs": 50,
        },
        "measurementStack": {
            "timeTaggerOrTdc": "required",
            "calibrationAutomation": "required",
            "waferOrChipProbeStation": "required",
            "packagingPlan": "fiber_array_or_edge_coupler_required",
        },
        "measurementProtocols": {
            "lossCalibration": "scan each optical port with reference waveguide and normalize to fiber coupling",
            "phaseCalibration": "fit MZI fringes per phase shifter across temperature and drive voltage",
            "detectorCalibration": "measure efficiency, dark counts, dead time, and timing jitter per detector",
            "sourceCalibration": "measure brightness, g2, and HOM visibility per source bank",
            "primitiveCalibration": "run known-occupancy shots and estimate heralding confusion matrix",
        },
        "blockers": [
            "No packaged chip or probe card.",
            "No detector cryostat integration plan.",
            "No automated phase and loss calibration bench.",
            "No source indistinguishability measurement protocol.",
        ],
    }
