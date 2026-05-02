"""Non-Gaussian source, detector, and resource-state requirements."""

from __future__ import annotations

from typing import Any

from .blueprint import Blueprint


def generate_resource_model(
    blueprint: Blueprint,
    *,
    encoding: str = "dual_rail",
    logical_qubits: int | None = None,
    target_logical_error_rate: float = 1e-6,
) -> dict[str, Any]:
    spatial = blueprint.spatial_model
    logical = logical_qubits or max(1, spatial.waveguide_count // (2 if encoding == "dual_rail" else 1))
    modes_per_logical = 2 if encoding == "dual_rail" else 1
    source_count = logical * modes_per_logical
    detector_count = spatial.waveguide_count
    ancilla_modes = max(2 * logical, spatial.interferometer_count // 2)

    return {
        "schemaVersion": "open-quantum.resource-model.v1",
        "sourcePath": blueprint.source_path,
        "encoding": encoding,
        "targetLogicalErrorRate": target_logical_error_rate,
        "logicalQubits": logical,
        "physicalModes": spatial.waveguide_count,
        "requiredNonGaussianResources": {
            "singlePhotonSources": {
                "count": source_count,
                "targetIndistinguishability": 0.99,
                "targetBrightness": 0.8,
                "targetMultiphotonProbability": 0.001,
                "interface": {
                    "trigger": "clocked_or_heralded_source_bank",
                    "outputs": ["mode_id", "time_bin", "brightness_estimate", "indistinguishability_estimate"],
                    "calibrationInput": "hong_ou_mandel_visibility_scan",
                },
                "status": "missing_hardware_model",
            },
            "pnrDetectors": {
                "count": detector_count,
                "targetEfficiency": 0.95,
                "targetDarkCountHz": 10,
                "targetTimingJitterPs": 50,
                "interface": {
                    "outputs": ["mode_id", "time_tag_ps", "photon_number", "confidence"],
                    "calibrationInput": "efficiency_dark_count_jitter_sweep",
                    "readout": "tdc_timestamp_stream",
                },
                "status": "modeled_not_integrated",
            },
            "ancillaFactory": {
                "ancillaModesPerCycle": ancilla_modes,
                "factoryType": "fusion_resource_state" if encoding == "dual_rail" else "gkp_magic_state",
                "scheduleInterface": {
                    "inputs": ["source_bank_status", "detector_heralds", "feed_forward_frame"],
                    "outputs": ["accepted_resource_state_id", "failed_attempt_mask", "retry_schedule"],
                },
                "status": "not_implemented",
            },
            "multiplexing": {
                "strategy": "spatial_time_bin_heralded_retry",
                "minimumParallelSourceBanks": max(2, logical),
                "targetHeraldingSuccessProbability": 0.01,
                "status": "modeled_not_scheduled",
            },
            "heraldingModel": {
                "detectorPattern": "two_fold_pnr_coincidence",
                "requiresFastFeedForward": True,
                "requiresLossErasureFlags": True,
                "statistics": {
                    "tracked": ["success_probability", "false_positive_rate", "false_negative_rate", "dead_time_ns"],
                    "calibrationProtocol": "repeat primitive shots with known input occupancy and record PNR coincidence matrix",
                },
                "status": "analytical_model_only",
            },
        },
        "hardwareCalibrationParameters": {
            "sourceBrightness": "required_per_source_bank",
            "sourceIndistinguishability": "required_pairwise_hom_visibility",
            "detectorEfficiency": "required_per_mode",
            "detectorDarkCountRateHz": "required_per_detector",
            "detectorTimingJitterPs": "required_per_detector",
            "switchLatencyNs": "required_per_actuator",
            "phaseDriftRadPerHour": "required_per_phase_shifter",
            "fiberCouplingLossDb": "required_per_port",
        },
        "bottlenecks": [
            "No experimentally calibrated source brightness and indistinguishability model.",
            "No photon-number resolving detector timing and saturation model.",
            "No resource-state factory schedule.",
            "No multiplexing strategy for failed heralded events.",
        ],
    }
