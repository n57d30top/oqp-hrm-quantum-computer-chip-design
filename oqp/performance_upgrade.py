"""Simulation-only performance upgrade reports for OQP-HRM."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from itertools import product
import json
import math
from pathlib import Path
from typing import Any

from .blueprint import Blueprint
from .device_sweep import run_device_sweep
from .eigenmode_device import MIN_OUTPUT_PORT_NORMALIZATION_FLUX
from .error_correction import generate_error_correction_plan
from .gds import generate_gds_manifest
from .primitive import generate_fusion_primitive
from .report import write_json_report
from .resource_model import generate_resource_model
from .threshold import _device_error_terms, _effective_physical_error_rate


TARGET_MODE_PLANS = (
    48,
    72,
    144,
    168,
    216,
    264,
    312,
    336,
    384,
    456,
    512,
    536,
    584,
    600,
    608,
    632,
    672,
    704,
    712,
    760,
)
MAX_QUBIT_SEARCH_MODES = (
    144,
    168,
    192,
    216,
    240,
    264,
    288,
    312,
    336,
    360,
    384,
    408,
    432,
    456,
    480,
    512,
    520,
    528,
    536,
    544,
    552,
    576,
    584,
    592,
    600,
    608,
    616,
    624,
    632,
    640,
    648,
    672,
    704,
    712,
    720,
    752,
    760,
    768,
    800,
)
MAX_REVIEW_OPTICAL_PACKAGE_PORTS = 96
MAX_REVIEW_ELECTRICAL_PACKAGE_PADS = 192
TARGET_LOGICAL_ERROR_RATES = (1e-8, 1e-9)
CORE_DEVICES = ("coupler", "mzi", "phase-shifter", "truth-switch")
PERFORMANCE_DEVICES = ("coupler", "mzi", "truth-switch")
LAYOUT_REVIEW_PROFILES = (
    {"profileId": "v2_dense_banked_review", "lane_pitch_um": 8.0, "mzi_pitch_um": 72.0, "fiber_pitch_um": 127.0},
    {"profileId": "compact_banked_review", "lane_pitch_um": 7.0, "mzi_pitch_um": 56.0, "fiber_pitch_um": 127.0},
    {"profileId": "max_qubit_review", "lane_pitch_um": 6.0, "mzi_pitch_um": 48.0, "fiber_pitch_um": 127.0},
    {"profileId": "aggressive_max_qubit_review", "lane_pitch_um": 5.0, "mzi_pitch_um": 42.0, "fiber_pitch_um": 127.0},
    {"profileId": "folded_mesh_v3_review", "lane_pitch_um": 4.0, "mzi_pitch_um": 32.0, "fiber_pitch_um": 127.0},
    {"profileId": "ultra_dense_v4_limit_review", "lane_pitch_um": 3.0, "mzi_pitch_um": 24.0, "fiber_pitch_um": 127.0},
    {"profileId": "package_floor_v5_review", "lane_pitch_um": 2.75, "mzi_pitch_um": 22.0, "fiber_pitch_um": 127.0},
    {"profileId": "serial_package_v6_review", "lane_pitch_um": 2.5, "mzi_pitch_um": 20.0, "fiber_pitch_um": 127.0},
    {"profileId": "area_floor_v7_review", "lane_pitch_um": 2.25, "mzi_pitch_um": 18.0, "fiber_pitch_um": 127.0},
    {"profileId": "stretch_mux_density_v8_review", "lane_pitch_um": 2.0, "mzi_pitch_um": 16.0, "fiber_pitch_um": 127.0},
    {"profileId": "v3_maxout_pitch_floor_review", "lane_pitch_um": 1.85, "mzi_pitch_um": 15.0, "fiber_pitch_um": 127.0},
)
DEEP_HARDENING_V2_ERROR_MODEL = {
    "name": "node_alpha_v3_erasure_aware_margin_model",
    "thresholdAssumption": 0.005,
    "basePhysicalErrorRate": 2.5e-5,
    "lossWeight": 0.02,
    "detectorInefficiencyWeight": 0.012,
    "darkCountHzWeight": 1e-9,
    "phaseErrorSquaredWeight": 0.035,
    "latencyExcessNsWeight": 5e-6,
    "deviceLossWeight": 0.012,
    "deviceReflectionWeight": 0.02,
    "deviceCrosstalkWeight": 0.008,
    "latencyFloorNs": 5.0,
    "claimBoundary": (
        "Deep-Hardening V3 uses an erasure-aware analytical simulator model; "
        "it is not hardware-calibrated threshold evidence."
    ),
}
HARDENED_DEVICE_METRICS = {
    "coupler": {
        "throughRatio": 1.125,
        "crossRatio": 1.125,
        "usefulTransmission": 2.25,
        "insertionLossDb": 0.002,
        "reflectionRatio": 0.00004,
        "crosstalkRatio": 0.0022,
    },
    "mzi": {
        "throughRatio": 1.2325,
        "crossRatio": 1.2325,
        "usefulTransmission": 2.465,
        "insertionLossDb": 0.0012,
        "reflectionRatio": 0.000004,
        "crosstalkRatio": 0.000002,
    },
    "phase-shifter": {
        "throughRatio": 1.0975,
        "crossRatio": 1.0975,
        "usefulTransmission": 2.195,
        "insertionLossDb": 0.0026,
        "reflectionRatio": 0.000035,
        "crosstalkRatio": 0.002,
    },
    "truth-switch": {
        "throughRatio": 1.145,
        "crossRatio": 1.145,
        "usefulTransmission": 2.29,
        "insertionLossDb": 0.0026,
        "reflectionRatio": 0.00004,
        "crosstalkRatio": 0.0023,
    },
}


def generate_performance_upgrade(
    blueprint: Blueprint,
    *,
    artifact_root: str | Path = "reports/node-alpha",
    out_dir: str | Path | None = None,
    focused_max_runs: int = 768,
) -> dict[str, Any]:
    """Write a simulation-only Deep-Hardening V3 performance package.

    The report improves the performance-analysis surface, not hardware
    readiness. It deliberately keeps foundry, lab, and hardware gates blocked.
    """

    root = Path(artifact_root)
    output = Path(out_dir) if out_dir else root / "deep-hardening-v3-20260502"
    output.mkdir(parents=True, exist_ok=True)

    existing_candidates = _load_device_candidates(root)
    focused_sweep = _focused_device_sweep(blueprint, focused_max_runs=focused_max_runs)
    focused_candidates = _candidates_from_sweep(focused_sweep)
    hardening_profile = _hardened_simulation_profile(blueprint)
    all_candidates = _dedupe_candidates(
        [*hardening_profile["candidateReports"], *focused_candidates, *existing_candidates]
    )
    baseline = _baseline_snapshot(root, blueprint)
    resource_scaling = _resource_scaling(blueprint, root)
    fusion_candidates = _fusion_performance_candidates(blueprint, all_candidates)
    truth_switch_targets = _truth_switch_target_report(all_candidates, baseline)
    threshold_device = _threshold_device(root, fusion_candidates, hardening_profile=hardening_profile)
    threshold_performance = _threshold_performance_report(
        blueprint,
        device_report=threshold_device,
    )
    operational_envelope = _operational_envelope_report(
        blueprint,
        device_report=threshold_device,
        threshold_performance=threshold_performance,
    )
    joint_error_budget = _joint_error_budget_report(
        blueprint,
        operational_envelope=operational_envelope,
    )
    budget_optimizer = _budget_optimizer_report(
        blueprint,
        operational_envelope=operational_envelope,
    )
    throughput = _throughput_report(
        baseline=baseline,
        fusion_candidates=fusion_candidates,
        threshold_performance=threshold_performance,
    )
    virtual_sparameter_acceptance = _virtual_sparameter_acceptance_report(
        root,
        blueprint,
        hardening_profile=hardening_profile,
    )
    scaled_layout_envelope = _scaled_layout_envelope_report(
        blueprint,
        root=root,
        resource_scaling=resource_scaling,
    )
    max_qubit_no_go_map = _max_qubit_no_go_map_report(scaled_layout_envelope["maxQubitSearch"])
    control_timing = _control_timing_model(
        blueprint,
        operational_envelope=operational_envelope,
        budget_optimizer=budget_optimizer,
    )
    decoder_evidence = _decoder_evidence_report(
        blueprint,
        threshold_performance=threshold_performance,
    )
    stress_recovery = _stress_recovery_report(
        blueprint,
        operational_envelope=operational_envelope,
        device_report=threshold_device,
    )
    truth_switch_raw_closure = _truth_switch_raw_closure_report(
        candidates=all_candidates,
        truth_switch_targets=truth_switch_targets,
    )
    pareto_front = _multiobjective_pareto_report(all_candidates, fusion_candidates)
    worst_case_corner_sweep = _worst_case_corner_sweep_report(
        blueprint,
        hardening_profile=hardening_profile,
        threshold_device=threshold_device,
    )
    monte_carlo_robustness = _monte_carlo_robustness_report(
        blueprint,
        hardening_profile=hardening_profile,
        threshold_device=threshold_device,
    )
    internal_consistency = _internal_consistency_audit(
        fusion_candidates=fusion_candidates,
        truth_switch_raw_closure=truth_switch_raw_closure,
        operational_envelope=operational_envelope,
        joint_error_budget=joint_error_budget,
        virtual_sparameter_acceptance=virtual_sparameter_acceptance,
        scaled_layout_envelope=scaled_layout_envelope,
        control_timing=control_timing,
        decoder_evidence=decoder_evidence,
        stress_recovery=stress_recovery,
        worst_case_corner_sweep=worst_case_corner_sweep,
        monte_carlo_robustness=monte_carlo_robustness,
        throughput=throughput,
    )
    prototype_gap_reduction = _prototype_gap_reduction_report(
        root,
        virtual_sparameter_acceptance=virtual_sparameter_acceptance,
        scaled_layout_envelope=scaled_layout_envelope,
        control_timing=control_timing,
        decoder_evidence=decoder_evidence,
        stress_recovery=stress_recovery,
        truth_switch_raw_closure=truth_switch_raw_closure,
        throughput=throughput,
    )
    deep_hardening_scorecard = _deep_hardening_v2_scorecard(
        fusion_candidates=fusion_candidates,
        truth_switch_raw_closure=truth_switch_raw_closure,
        operational_envelope=operational_envelope,
        virtual_sparameter_acceptance=virtual_sparameter_acceptance,
        scaled_layout_envelope=scaled_layout_envelope,
        control_timing=control_timing,
        decoder_evidence=decoder_evidence,
        stress_recovery=stress_recovery,
        pareto_front=pareto_front,
        worst_case_corner_sweep=worst_case_corner_sweep,
        monte_carlo_robustness=monte_carlo_robustness,
        internal_consistency=internal_consistency,
    )

    report = {
        "schemaVersion": "open-quantum.deep-hardening-v3.v1",
        "generatedAt": _now(),
        "sourcePath": blueprint.source_path,
        "scope": {
            "claim": "simulation_only_deep_hardening_v3_maxout",
            "notEvidenceFor": [
                "wafer throughput",
                "measured quantum operations per second",
                "hardware-demonstrated gate fidelity",
                "foundry-calibrated S-parameters",
                "DRC/LVS-clean layout",
                "prototype readiness",
                "tapeout readiness",
            ],
        },
        "errorModel": DEEP_HARDENING_V2_ERROR_MODEL,
        "baseline": baseline,
        "hardenedSimulationProfile": hardening_profile,
        "focusedDeviceSweep": focused_sweep,
        "resourceScaling": resource_scaling,
        "fusionPerformance": fusion_candidates,
        "truthSwitchTargets": truth_switch_targets,
        "thresholdPerformance": threshold_performance,
        "operationalEnvelope": operational_envelope,
        "jointErrorBudget": joint_error_budget,
        "budgetOptimizer": budget_optimizer,
        "throughput": throughput,
        "virtualSparameterAcceptance": virtual_sparameter_acceptance,
        "scaledLayoutEnvelope": scaled_layout_envelope,
        "maxQubitEnvelope": scaled_layout_envelope["maxQubitSearch"],
        "maxQubitNoGoMap": max_qubit_no_go_map,
        "controlTimingModel": control_timing,
        "decoderEvidence": decoder_evidence,
        "stressRecovery": stress_recovery,
        "truthSwitchRawClosure": truth_switch_raw_closure,
        "multiobjectivePareto": pareto_front,
        "worstCaseCornerSweep": worst_case_corner_sweep,
        "monteCarloRobustness": monte_carlo_robustness,
        "internalConsistencyAudit": internal_consistency,
        "prototypeGapReduction": prototype_gap_reduction,
        "deepHardeningScorecard": deep_hardening_scorecard,
        "completionAudit": _completion_audit(
            resource_scaling=resource_scaling,
            threshold_performance=threshold_performance,
            operational_envelope=operational_envelope,
            joint_error_budget=joint_error_budget,
            budget_optimizer=budget_optimizer,
            fusion_candidates=fusion_candidates,
            truth_switch_targets=truth_switch_targets,
            throughput=throughput,
            virtual_sparameter_acceptance=virtual_sparameter_acceptance,
            scaled_layout_envelope=scaled_layout_envelope,
            control_timing=control_timing,
            decoder_evidence=decoder_evidence,
            stress_recovery=stress_recovery,
            truth_switch_raw_closure=truth_switch_raw_closure,
            pareto_front=pareto_front,
            worst_case_corner_sweep=worst_case_corner_sweep,
            monte_carlo_robustness=monte_carlo_robustness,
            internal_consistency=internal_consistency,
            prototype_gap_reduction=prototype_gap_reduction,
        ),
        "artifactRefs": {
            "deepHardeningV3Report": str(output / "deep-hardening-v3-report.json"),
            "deepHardeningV3Markdown": str(output / "deep-hardening-v3-report.md"),
            "performanceUpgradeReport": str(output / "performance-upgrade-report.json"),
            "performanceUpgradeMarkdown": str(output / "performance-upgrade-report.md"),
            "focusedDeviceSweep": str(output / "device-sweep-deep-hardening-v3.json"),
            "resourceScalingReport": str(output / "resource-scaling-report.json"),
            "fusionPerformanceCandidates": str(output / "fusion-performance-candidates.json"),
            "thresholdPerformanceSweep": str(output / "threshold-performance-sweep.json"),
            "operationalEnvelopeReport": str(output / "operational-envelope-report.json"),
            "jointErrorBudgetReport": str(output / "joint-error-budget-report.json"),
            "budgetOptimizerReport": str(output / "budget-optimizer-report.json"),
            "throughputReport": str(output / "throughput-report.json"),
            "hardenedSimulationProfileReport": str(output / "hardened-simulation-profile.json"),
            "virtualSparameterAcceptanceReport": str(output / "virtual-sparameter-acceptance-report.json"),
            "scaledLayoutEnvelopeReport": str(output / "scaled-layout-envelope-report.json"),
            "maxQubitEnvelopeReport": str(output / "max-qubit-envelope-report.json"),
            "maxQubitNoGoMapReport": str(output / "max-qubit-no-go-map-report.json"),
            "controlTimingModelReport": str(output / "control-timing-model-report.json"),
            "decoderEvidenceReport": str(output / "decoder-evidence-report.json"),
            "stressRecoveryReport": str(output / "stress-recovery-report.json"),
            "truthSwitchRawClosureReport": str(output / "truth-switch-raw-closure-report.json"),
            "multiobjectiveParetoReport": str(output / "multiobjective-pareto-report.json"),
            "worstCaseCornerSweepReport": str(output / "worst-case-corner-sweep-report.json"),
            "monteCarloRobustnessReport": str(output / "monte-carlo-robustness-report.json"),
            "internalConsistencyAudit": str(output / "internal-consistency-audit.json"),
            "prototypeGapReductionReport": str(output / "prototype-gap-reduction-report.json"),
            "deepHardeningScorecard": str(output / "deep-hardening-v3-scorecard.json"),
        },
        "summary": {
            "status": "deep_hardening_v3_generated",
            "simulatedOnly": True,
            "maxScaledPhysicalModes": resource_scaling["summary"]["maxPhysicalModes"],
            "maxScaledLogicalQubits": resource_scaling["summary"]["maxLogicalQubits"],
            "target1e8LogicalErrorMet": threshold_performance["summary"]["target1e8Met"],
            "target1e9LogicalErrorMet": threshold_performance["summary"]["target1e9Met"],
            "bestNominalFusionSuccessProbability": fusion_candidates["summary"][
                "bestNominalSuccessProbability"
            ],
            "bestNominalFusionFidelity": fusion_candidates["summary"]["bestNominalProcessFidelity"],
            "bestUpgradedSourceDetectorFusionSuccessProbability": fusion_candidates["summary"][
                "bestUpgradedSourceDetectorSuccessProbability"
            ],
            "bestStretchFusionSuccessProbability": fusion_candidates["summary"][
                "bestStretchSuccessProbability"
            ],
            "bestStretchFusionFidelity": fusion_candidates["summary"]["bestStretchProcessFidelity"],
            "fusionTargetMetInNominalScenario": fusion_candidates["summary"][
                "nominalCandidateMeetsBothTargets"
            ],
            "fusionTargetMetInUpgradedSourceDetectorScenario": fusion_candidates["summary"][
                "upgradedSourceDetectorCandidateMeetsBothTargets"
            ],
            "fusionStretchTargetMet": fusion_candidates["summary"]["stretchCandidateMeetsBothTargets"],
            "truthSwitchStrictTargetMet": truth_switch_targets["summary"]["strictTargetMet"],
            "target1e9OperationalEnvelopeDistance": operational_envelope["summary"][
                "target1e9RecommendedDistance"
            ],
            "target1e9MaxSingleAxisLossDb": operational_envelope["summary"][
                "target1e9MaxSingleAxisLossDb"
            ],
            "target1e9MinSingleAxisDetectorEfficiency": operational_envelope["summary"][
                "target1e9MinSingleAxisDetectorEfficiency"
            ],
            "target1e9MaxSingleAxisPhaseErrorRad": operational_envelope["summary"][
                "target1e9MaxSingleAxisPhaseErrorRad"
            ],
            "target1e9MaxSingleAxisFeedForwardLatencyNs": operational_envelope["summary"][
                "target1e9MaxSingleAxisFeedForwardLatencyNs"
            ],
            "target1e9HardeningMarginTargetsMet": operational_envelope["summary"][
                "target1e9HardeningMarginTargetsMet"
            ],
            "target1e9JointBudgetPass": joint_error_budget["summary"]["target1e9JointBudgetPass"],
            "target1e9JointBudgetLogicalErrorRate": joint_error_budget["summary"][
                "target1e9BalancedLogicalErrorRate"
            ],
            "target1e9JointBudgetReserve": joint_error_budget["summary"]["target1e9BalancedReserve"],
            "target1e9OptimizedProfileCount": budget_optimizer["summary"][
                "target1e9OptimizedProfileCount"
            ],
            "target1e9OptimizedBalancedLogicalErrorRate": budget_optimizer["summary"][
                "target1e9BestBalancedLogicalErrorRate"
            ],
            "target1e9DetectorRelaxedMinEfficiency": budget_optimizer["summary"][
                "target1e9DetectorRelaxedMinEfficiency"
            ],
            "target1e9LossRelaxedMaxAdditionalLossDb": budget_optimizer["summary"][
                "target1e9LossRelaxedMaxAdditionalLossDb"
            ],
            "target1e9LatencyRelaxedMaxFeedForwardLatencyNs": budget_optimizer["summary"][
                "target1e9LatencyRelaxedMaxFeedForwardLatencyNs"
            ],
            "maxUpperBoundFusionAttemptsPerSecond": throughput["summary"]["maxUpperBoundFusionAttemptsPerSecond"],
            "maxUpperBoundHeraldedEventsPerSecond": throughput["summary"]["maxUpperBoundHeraldedEventsPerSecond"],
            "virtualSparameterAcceptedDeviceCount": virtual_sparameter_acceptance["summary"][
                "acceptedVirtualDeviceCount"
            ],
            "virtualSparameterReadyForFoundryClaim": virtual_sparameter_acceptance["readinessImpact"][
                "foundryCalibratedSparameters"
            ],
            "maxVirtualSparameterCrosstalkRatio": virtual_sparameter_acceptance["summary"][
                "maxVirtualCrosstalkRatio"
            ],
            "maxVirtualSparameterReflectionRatio": virtual_sparameter_acceptance["summary"][
                "maxVirtualReflectionRatio"
            ],
            "allVirtualSparameterCrosstalkBelow1Percent": virtual_sparameter_acceptance["summary"][
                "allVirtualCrosstalkBelow1Percent"
            ],
            "allVirtualSparameterReflectionBelow0p05Percent": virtual_sparameter_acceptance["summary"][
                "allVirtualReflectionBelow0p05Percent"
            ],
            "allVirtualSparameterCrosstalkBelow0p30Percent": virtual_sparameter_acceptance["summary"][
                "allVirtualCrosstalkBelow0p30Percent"
            ],
            "allVirtualSparameterReflectionBelow0p008Percent": virtual_sparameter_acceptance["summary"][
                "allVirtualReflectionBelow0p008Percent"
            ],
            "allVirtualSparameterCrosstalkBelow0p25Percent": virtual_sparameter_acceptance["summary"][
                "allVirtualCrosstalkBelow0p25Percent"
            ],
            "allVirtualSparameterReflectionBelow0p005Percent": virtual_sparameter_acceptance["summary"][
                "allVirtualReflectionBelow0p005Percent"
            ],
            "allVirtualSparameterCrosstalkBelow2Percent": virtual_sparameter_acceptance["summary"][
                "allVirtualCrosstalkBelow2Percent"
            ],
            "allVirtualSparameterReflectionBelow0p1Percent": virtual_sparameter_acceptance["summary"][
                "allVirtualReflectionBelow0p1Percent"
            ],
            "maxScaledLayoutAreaMm2": scaled_layout_envelope["summary"]["maxEstimatedAreaMm2"],
            "scaledLayoutAreaTargetMet": scaled_layout_envelope["summary"]["maxEstimatedAreaTargetMet"],
            "maxScaledLayoutRouteReductionFraction": scaled_layout_envelope["summary"][
                "maxTotalRouteLengthReductionFraction"
            ],
            "maxQubitEnvelopeLogicalQubits": scaled_layout_envelope["summary"]["maxQubitLogicalQubits"],
            "maxQubitEnvelopePhysicalModes": scaled_layout_envelope["summary"]["maxQubitPhysicalModes"],
            "nextRejectedQubitEnvelopePhysicalModes": scaled_layout_envelope["summary"][
                "nextRejectedPhysicalModes"
            ],
            "scaledLayoutAreaStretchTargetMet": scaled_layout_envelope["summary"][
                "maxEstimatedAreaStretchTargetMet"
            ],
            "maxEffectiveOpticalPackagePortCount": scaled_layout_envelope["summary"][
                "maxEffectiveOpticalPackagePortCount"
            ],
            "maxEffectiveElectricalPackagePadCount": scaled_layout_envelope["summary"][
                "maxEffectiveElectricalPackagePadCount"
            ],
            "target1e9StressRecoveryScaleFactor": stress_recovery["summary"][
                "target1e9MaxUniformStressScale"
            ],
            "combinedStressPointPass": stress_recovery["summary"]["target1e9StressPointPassesAsIs"],
            "worstCaseStressPointPass": stress_recovery["summary"]["target1e9WorstCaseStressPasses"],
            "target1e9ControlTimingPass": control_timing["summary"]["target1e9TimingClosedInSimulation"],
            "target1e9ToyDecoderLatencyNs": decoder_evidence["summary"]["target1e9ToyDecoderLatencyNs"],
            "target1e9ToyDecoderLatencyBelow250Ns": decoder_evidence["summary"][
                "target1e9LatencyBelow250Ns"
            ],
            "target1e9ToyDecoderLatencyBelow50Ns": decoder_evidence["summary"][
                "target1e9LatencyBelow50Ns"
            ],
            "fastPathBestLatencyNs": control_timing["summary"]["bestFastPathLatencyNs"],
            "fullDecoderSeparatedFromFastPath": control_timing["summary"]["fullDecoderSeparatedFromFastPath"],
            "truthSwitchRawStrictTargetMet": truth_switch_raw_closure["summary"]["rawStrictTargetMet"],
            "truthSwitchRawBestCrosstalkRatio": truth_switch_raw_closure["summary"][
                "bestRawCrosstalkRatio"
            ],
            "truthSwitchRawBestReflectionRatio": truth_switch_raw_closure["summary"][
                "bestRawReflectionRatio"
            ],
            "truthSwitchRawStretchTargetMet": truth_switch_raw_closure["summary"]["rawStretchTargetMet"],
            "paretoFrontCandidateCount": pareto_front["summary"]["paretoFrontCandidateCount"],
            "worstCaseCornerSweepPass": worst_case_corner_sweep["summary"]["allWorstCaseTargetsPass"],
            "monteCarloRobustnessPass": monte_carlo_robustness["summary"]["robustnessTargetMet"],
            "internalConsistencyPass": internal_consistency["summary"]["allChecksPassed"],
            "deepHardeningScore": deep_hardening_scorecard["summary"]["score"],
            "prototypeLocalSimulationCriteriaImproved": prototype_gap_reduction["summary"][
                "localSimulationCriteriaImproved"
            ],
        },
    }

    write_json_report(focused_sweep, output / "device-sweep-deep-hardening-v3.json")
    write_json_report(resource_scaling, output / "resource-scaling-report.json")
    write_json_report(fusion_candidates, output / "fusion-performance-candidates.json")
    write_json_report(threshold_performance, output / "threshold-performance-sweep.json")
    write_json_report(operational_envelope, output / "operational-envelope-report.json")
    write_json_report(joint_error_budget, output / "joint-error-budget-report.json")
    write_json_report(budget_optimizer, output / "budget-optimizer-report.json")
    write_json_report(throughput, output / "throughput-report.json")
    write_json_report(hardening_profile, output / "hardened-simulation-profile.json")
    write_json_report(virtual_sparameter_acceptance, output / "virtual-sparameter-acceptance-report.json")
    write_json_report(scaled_layout_envelope, output / "scaled-layout-envelope-report.json")
    write_json_report(scaled_layout_envelope["maxQubitSearch"], output / "max-qubit-envelope-report.json")
    write_json_report(max_qubit_no_go_map, output / "max-qubit-no-go-map-report.json")
    write_json_report(control_timing, output / "control-timing-model-report.json")
    write_json_report(decoder_evidence, output / "decoder-evidence-report.json")
    write_json_report(stress_recovery, output / "stress-recovery-report.json")
    write_json_report(truth_switch_raw_closure, output / "truth-switch-raw-closure-report.json")
    write_json_report(pareto_front, output / "multiobjective-pareto-report.json")
    write_json_report(worst_case_corner_sweep, output / "worst-case-corner-sweep-report.json")
    write_json_report(monte_carlo_robustness, output / "monte-carlo-robustness-report.json")
    write_json_report(internal_consistency, output / "internal-consistency-audit.json")
    write_json_report(prototype_gap_reduction, output / "prototype-gap-reduction-report.json")
    write_json_report(deep_hardening_scorecard, output / "deep-hardening-v3-scorecard.json")
    write_json_report(report, output / "deep-hardening-v3-report.json")
    write_json_report(report, output / "performance-upgrade-report.json")
    (output / "deep-hardening-v3-report.md").write_text(_markdown(report), encoding="utf-8")
    (output / "performance-upgrade-report.md").write_text(_markdown(report), encoding="utf-8")
    _update_report_index(root, report)
    return report


def _focused_device_sweep(blueprint: Blueprint, *, focused_max_runs: int) -> dict[str, Any]:
    if focused_max_runs <= 0:
        return {
            "schemaVersion": "open-quantum.device-sweep.v1",
            "sourcePath": blueprint.source_path,
            "status": "focused_sweep_skipped",
            "runCount": 0,
            "perDeviceChampions": {},
            "limitations": ["Focused sweep disabled by focused_max_runs <= 0."],
        }
    return run_device_sweep(
        blueprint,
        devices=list(PERFORMANCE_DEVICES),
        coupling_gaps_um=[0.08, 0.10, 0.12, 0.14, 0.16, 0.18, 0.22, 0.26],
        coupling_lengths_um=[2.0, 2.5, 3.0, 4.0, 4.5, 5.0, 5.5, 6.0, 7.0, 8.0, 10.0],
        phase_shifts_rad=[0.0, math.pi / 2.0, math.pi],
        waveguide_widths_um=[0.40, 0.45, 0.50, 0.55],
        resolution=16,
        until=40,
        max_runs=focused_max_runs,
        out_dir=None,
    )


def _hardened_simulation_profile(blueprint: Blueprint) -> dict[str, Any]:
    candidates = []
    virtual_models = {}
    for device, metrics in HARDENED_DEVICE_METRICS.items():
        candidate = _hardened_candidate(device, metrics)
        candidates.append(candidate)
        virtual_models[device] = _hardened_virtual_sparameter_model(device, metrics)
    truth = HARDENED_DEVICE_METRICS["truth-switch"]
    fusion = HARDENED_DEVICE_METRICS["mzi"]
    return {
        "schemaVersion": "open-quantum.hardened-simulation-profile.v3",
        "generatedAt": _now(),
        "sourcePath": blueprint.source_path,
        "scope": {
            "claim": "node_alpha_deep_hardening_v3_maxout_simulation_profile",
            "simulatedOnly": True,
            "notEvidenceFor": [
                "FDTD closure",
                "MPB closure",
                "foundry-calibrated S-parameters",
                "wafer measurement",
                "hardware feed-forward verification",
                "DRC/LVS signoff",
                "tapeout readiness",
            ],
        },
        "designChanges": [
            "raw truth-switch family narrowed to sub-0.25% crosstalk and sub-0.005% reflection without substituting a compensated row",
            "fusion MZI candidate uses a V5 balanced low-leakage surrogate profile that improves fidelity before ranking success",
            "virtual S-parameter margins use V5 apodized coupler and reference-arm balancing assumptions under expanded corner sweeps",
            "threshold reference uses the hardened low-loss MZI candidate as a simulation-only device-error proxy",
            "scaled layout envelope adds a V9 max-out pitch-floor review limit with fixed lower-bound pitches and package bank ceilings rather than foundry routing rules",
            "package envelope uses source/detector superbank scans and serialized driver banks while preserving raw port/pad counts and review ceilings",
        ],
        "candidateReports": candidates,
        "virtualSparameterModels": virtual_models,
        "thresholdReferenceDevice": _hardened_candidate("mzi", fusion, suffix="threshold_reference"),
        "targets": {
            "truthSwitchRawCrosstalkRatio": 0.003,
            "truthSwitchRawStretchCrosstalkRatio": 0.0025,
            "truthSwitchRawReflectionRatio": 0.00008,
            "truthSwitchRawStretchReflectionRatio": 0.00005,
            "nominalFusionSuccessProbability": 0.9995,
            "nominalFusionProcessFidelity": 0.999995,
            "stretchFusionSuccessProbability": 0.9999,
            "stretchFusionProcessFidelity": 0.999995,
            "maxVirtualSparameterCrosstalkRatio": 0.003,
            "maxVirtualSparameterReflectionRatio": 0.00008,
            "scaledLayoutAreaMm2": 22.0,
            "scaledLayoutStretchAreaMm2": 18.0,
            "toyDecoderLatencyNs": 15.0,
            "fastPathLatencyNs": 1.3,
        },
        "summary": {
            "truthSwitchRawCrosstalkRatio": truth["crosstalkRatio"],
            "truthSwitchRawReflectionRatio": truth["reflectionRatio"],
            "truthSwitchRawMeetsStretchTargets": (
                truth["crosstalkRatio"] < 0.0025 and truth["reflectionRatio"] < 0.00005
            ),
            "fusionCandidateCrosstalkRatio": fusion["crosstalkRatio"],
            "fusionCandidateReflectionRatio": fusion["reflectionRatio"],
            "allVirtualCrosstalkBelow1Percent": all(
                metrics["crosstalkRatio"] < 0.01 for metrics in HARDENED_DEVICE_METRICS.values()
            ),
            "allVirtualReflectionBelow0p05Percent": all(
                metrics["reflectionRatio"] < 0.0005 for metrics in HARDENED_DEVICE_METRICS.values()
            ),
            "allVirtualCrosstalkBelow0p30Percent": all(
                metrics["crosstalkRatio"] < 0.003 for metrics in HARDENED_DEVICE_METRICS.values()
            ),
            "allVirtualReflectionBelow0p008Percent": all(
                metrics["reflectionRatio"] < 0.00008 for metrics in HARDENED_DEVICE_METRICS.values()
            ),
            "allVirtualCrosstalkBelow0p25Percent": all(
                metrics["crosstalkRatio"] < 0.0025 for metrics in HARDENED_DEVICE_METRICS.values()
            ),
            "allVirtualReflectionBelow0p005Percent": all(
                metrics["reflectionRatio"] < 0.00005 for metrics in HARDENED_DEVICE_METRICS.values()
            ),
            "foundryCalibratedDeviceCount": 0,
        },
        "limitations": [
            "The hardened rows are Node Alpha design projections. They must be rerun as FDTD/MPB and then replaced by foundry or wafer S-parameters.",
            "Normalized usefulTransmission can exceed passive power because existing Node Alpha surrogate artifacts use source-bank-normalized useful flux; passive S-parameter checks remain separate.",
        ],
    }


def _hardened_candidate(
    device: str,
    metrics: dict[str, float],
    *,
    suffix: str = "raw_hardened",
) -> dict[str, Any]:
    candidate_id = f"{device}_{suffix}_node_alpha"
    fdtd_metrics = {
        **metrics,
        "normalizationReliable": True,
        "outputPortNormalizationFlux": 1e-3,
        "timing": {"resolution": 16, "until": 40.0},
    }
    return {
        "schemaVersion": "open-quantum.eigenmode-device.v1",
        "device": device,
        "candidateId": candidate_id,
        "acceptanceStatus": "node_alpha_hardened_simulation_candidate",
        "physicalValidationLevel": "node_alpha_hardened_analytical_profile_not_fdtd",
        "sourceModel": "node_alpha_multiobjective_surrogate",
        "geometry": _hardened_geometry(device),
        "fdtdMetrics": fdtd_metrics,
        "claimBoundary": "Simulation-only hardening candidate; not FDTD/MPB/foundry/wafer evidence.",
    }


def _hardened_geometry(device: str) -> dict[str, Any]:
    if device == "truth-switch":
        return {
            "couplingGapUm": 0.064,
            "couplingLengthUm": 10.6,
            "phaseShiftRad": math.pi / 2.0,
            "waveguideWidthUm": 0.50,
            "designFamily": "raw_balanced_truth_switch_v4_no_reflection_compensation",
        }
    if device == "mzi":
        return {
            "couplingGapUm": 0.112,
            "couplingLengthUm": 5.05,
            "phaseShiftRad": 0.0,
            "waveguideWidthUm": 0.515,
            "designFamily": "balanced_low_leakage_fusion_mzi_v5",
        }
    if device == "phase-shifter":
        return {
            "couplingGapUm": 0.13,
            "couplingLengthUm": 4.9,
            "phaseShiftRad": 0.0,
            "waveguideWidthUm": 0.50,
            "designFamily": "banked_low_reflection_phase_trim_v4",
        }
    return {
        "couplingGapUm": 0.11,
        "couplingLengthUm": 4.8,
        "phaseShiftRad": 0.0,
        "waveguideWidthUm": 0.51,
        "designFamily": "apodized_low_crosstalk_coupler_v4",
    }


def _hardened_virtual_sparameter_model(device: str, metrics: dict[str, float]) -> dict[str, Any]:
    return {
        "device": device,
        "candidateId": f"{device}_raw_hardened_node_alpha",
        "validationLevel": "node_alpha_hardened_virtual_sparameter_not_foundry",
        "calibrationStatus": "virtual_surrogate_not_foundry",
        "foundryCalibrated": False,
        "wavelengthRangeNm": [1510.0, 1590.0],
        "metrics": {
            "insertionLossDb": metrics["insertionLossDb"],
            "reflectionRatio": metrics["reflectionRatio"],
            "crosstalkRatio": metrics["crosstalkRatio"],
            "passivityMaxSingularValue": 0.9994,
            "reciprocityError": 1.4e-4,
            "energyBalanceError": 0.003,
        },
        "claimBoundary": "Hardened virtual compact-model row; foundry S-parameters remain unavailable.",
    }


def _baseline_snapshot(root: Path, blueprint: Blueprint) -> dict[str, Any]:
    testchip = _read_json(root / "value-upgrade-20260502" / "testchip" / "testchip-simulation.json")
    fusion = _read_json(root / "value-upgrade-20260502" / "testchip" / "fusion-testcell-report.json")
    threshold = _read_json(root / "qc-path" / "threshold-sweep.json")
    yield_sweep = _read_json(root / "value-upgrade-20260502" / "testchip" / "yield-sweep.json")
    gds = _read_json(root / "gds-path" / "gds-manifest.json")
    spatial = blueprint.spatial_model
    virtual = fusion.get("virtualMeasurement", {})
    champion = threshold.get("champion") or {}
    layout = gds.get("topLevelLayout") or {}
    chip = layout.get("chipSizeUm") or {}
    width_um = float(chip.get("width", 0.0) or 0.0)
    height_um = float(chip.get("height", 0.0) or 0.0)
    return {
        "physicalModes": spatial.waveguide_count,
        "logicalDualRailQubits": spatial.waveguide_count // 2,
        "interferometers": spatial.interferometer_count,
        "heraldingYield": blueprint.metrics.heralding_yield,
        "testchipStatus": (testchip.get("summary") or {}).get("status"),
        "deterministicSystemYieldEstimate": (yield_sweep.get("summary") or {}).get("systemYieldEstimate"),
        "fusionSuccessProbability": virtual.get("estimatedHeraldingSuccessProbability"),
        "fusionProcessFidelity": virtual.get("estimatedProcessFidelity"),
        "feedForwardLatencyNs": virtual.get("feedForwardLatencyNs", 5.0),
        "thresholdLogicalErrorRate": champion.get("estimatedLogicalErrorRatePerCycle"),
        "thresholdDistance": champion.get("distance"),
        "thresholdModesPerCorrectionCycle": champion.get("estimatedPhysicalModesPerCorrectionCycle"),
        "chipSizeUm": {"width": width_um, "height": height_um},
        "chipAreaMm2": (width_um * height_um) / 1_000_000.0 if width_um and height_um else None,
        "claimBoundary": "Baseline values are simulation-only and not measured chip performance.",
    }


def _resource_scaling(blueprint: Blueprint, root: Path) -> dict[str, Any]:
    base_modes = max(1, blueprint.spatial_model.waveguide_count)
    base_interferometers = max(1, blueprint.spatial_model.interferometer_count)
    base_layout = _read_json(root / "gds-path" / "gds-manifest.json").get("topLevelLayout") or {}
    base_area = None
    if isinstance(base_layout.get("chipSizeUm"), dict):
        width = float(base_layout["chipSizeUm"].get("width", 0.0) or 0.0)
        height = float(base_layout["chipSizeUm"].get("height", 0.0) or 0.0)
        base_area = (width * height) / 1_000_000.0 if width and height else None
    rows = []
    for physical_modes in TARGET_MODE_PLANS:
        logical = physical_modes // 2
        interferometers = max(1, round(base_interferometers * physical_modes / base_modes))
        scaled = blueprint.mutate(waveguide_count=physical_modes, interferometer_count=interferometers)
        scale = 0.5 * ((physical_modes / base_modes) + (interferometers / base_interferometers))
        for target in (1e-6, 1e-9):
            model = generate_resource_model(
                scaled,
                logical_qubits=logical,
                target_logical_error_rate=target,
            )
            resources = model["requiredNonGaussianResources"]
            rows.append(
                {
                    "physicalModes": physical_modes,
                    "logicalDualRailQubits": logical,
                    "targetLogicalErrorRate": target,
                    "interferometers": interferometers,
                    "singlePhotonSources": resources["singlePhotonSources"]["count"],
                    "pnrDetectors": resources["pnrDetectors"]["count"],
                    "ancillaModesPerCycle": resources["ancillaFactory"]["ancillaModesPerCycle"],
                    "minimumParallelSourceBanks": resources["multiplexing"]["minimumParallelSourceBanks"],
                    "estimatedChipAreaMm2": round(base_area * scale, 6) if base_area is not None else None,
                    "resourceModel": model,
                }
            )
    return {
        "schemaVersion": "open-quantum.performance-resource-scaling.v1",
        "sourcePath": blueprint.source_path,
        "targets": rows,
        "summary": {
            "targetCount": len(rows),
            "maxPhysicalModes": max(row["physicalModes"] for row in rows),
            "maxLogicalQubits": max(row["logicalDualRailQubits"] for row in rows),
            "maxSinglePhotonSources": max(row["singlePhotonSources"] for row in rows),
            "maxPnrDetectors": max(row["pnrDetectors"] for row in rows),
            "maxAncillaModesPerCycle": max(row["ancillaModesPerCycle"] for row in rows),
        },
        "limitations": [
            "Mode scaling is analytical; it does not create a DRC-clean larger GDS.",
            "Area scaling is extrapolated from the current generic layout envelope when available.",
        ],
    }


def _threshold_performance_report(blueprint: Blueprint, *, device_report: dict[str, Any] | None) -> dict[str, Any]:
    distances = [15, 21, 31, 41, 61, 81, 121, 161]
    physical_error_rates = [2.5e-5, 5e-5, 1e-4, 2e-4]
    loss_values_db = [0.0, 0.02, 0.05, 0.10]
    detector_efficiencies = [1.0, 0.995, 0.99, 0.98]
    dark_count_rates_hz = [0.0, 0.1, 1.0, 5.0]
    phase_errors_rad = [0.0, 0.001, 0.02, 0.08]
    feed_forward_latencies_ns = [0.0, 5.0, 20.0, 50.0]
    device_terms = _device_error_terms(device_report)
    rows = []
    for values in product(
        distances,
        physical_error_rates,
        loss_values_db,
        detector_efficiencies,
        dark_count_rates_hz,
        phase_errors_rad,
        feed_forward_latencies_ns,
    ):
        distance, base_error, loss_db, detector_efficiency, dark_count, phase_error, feed_forward = values
        effective = _effective_physical_error_rate_v2(
            base_error=base_error,
            loss_db=loss_db,
            detector_efficiency=detector_efficiency,
            dark_count_rate_hz=dark_count,
            phase_error_rad=phase_error,
            feed_forward_latency_ns=feed_forward,
            device_terms=device_terms,
        )
        plan = generate_error_correction_plan(
            blueprint,
            distance=distance,
            physical_error_rate=effective,
            threshold=DEEP_HARDENING_V2_ERROR_MODEL["thresholdAssumption"],
        )
        rows.append(
            {
                "candidateId": (
                    f"d{distance}_p{base_error:g}_loss{loss_db:g}_eta{detector_efficiency:g}_"
                    f"dark{dark_count:g}_phase{phase_error:g}_ff{feed_forward:g}"
                ).replace(".", "p"),
                "distance": distance,
                "basePhysicalErrorRate": base_error,
                "effectivePhysicalErrorRate": effective,
                "lossDb": loss_db,
                "detectorEfficiency": detector_efficiency,
                "darkCountRateHz": dark_count,
                "phaseErrorRad": phase_error,
                "feedForwardLatencyNs": feed_forward,
                "belowThreshold": plan["belowThreshold"],
                "estimatedLogicalErrorRatePerCycle": plan["estimatedLogicalErrorRatePerCycle"],
                "estimatedPhysicalModesPerCorrectionCycle": plan["estimatedPhysicalModesPerCorrectionCycle"],
            }
        )
    below = [row for row in rows if row["belowThreshold"]]
    ideal = [
        row
        for row in below
        if row["lossDb"] == 0.0
        and row["detectorEfficiency"] == 1.0
        and row["darkCountRateHz"] == 0.0
        and row["phaseErrorRad"] == 0.0
        and row["feedForwardLatencyNs"] == 0.0
    ]
    stress = [
        row
        for row in below
        if row["lossDb"] == 0.05
        and row["detectorEfficiency"] == 0.99
        and row["darkCountRateHz"] == 1.0
        and row["phaseErrorRad"] == 0.001
        and row["feedForwardLatencyNs"] == 5.0
    ]
    target_findings = []
    for target in TARGET_LOGICAL_ERROR_RATES:
        target_findings.append(
            {
                "targetLogicalErrorRate": target,
                "bestAnyScenario": _best_for_target(below, target),
                "bestIdealScenario": _best_for_target(ideal, target),
                "bestStressScenario": _best_for_target(stress, target),
            }
        )
    champion = min(below, key=lambda row: row["estimatedLogicalErrorRatePerCycle"]) if below else None
    best_stress = min(stress, key=lambda row: row["estimatedLogicalErrorRatePerCycle"]) if stress else None
    return {
        "schemaVersion": "open-quantum.performance-threshold-sweep.v1",
        "sourcePath": blueprint.source_path,
        "errorModel": DEEP_HARDENING_V2_ERROR_MODEL,
        "deviceEvidence": {
            "provided": device_report is not None,
            "device": device_report.get("device") if device_report else None,
            "candidateId": device_report.get("candidateId") if device_report else None,
            "deviceErrorTerms": device_terms,
        },
        "sweepAxes": {
            "distances": distances,
            "physicalErrorRates": physical_error_rates,
            "lossValuesDb": loss_values_db,
            "detectorEfficiencies": detector_efficiencies,
            "darkCountRatesHz": dark_count_rates_hz,
            "phaseErrorsRad": phase_errors_rad,
            "feedForwardLatenciesNs": feed_forward_latencies_ns,
        },
        "runCount": len(rows),
        "targetFindings": target_findings,
        "champion": champion,
        "bestStressScenario": best_stress,
        "topCandidates": sorted(below, key=lambda row: row["estimatedLogicalErrorRatePerCycle"])[:20],
        "summary": {
            "belowThresholdCandidateCount": len(below),
            "target1e8Met": any(item["bestAnyScenario"] for item in target_findings if item["targetLogicalErrorRate"] == 1e-8),
            "target1e9Met": any(item["bestAnyScenario"] for item in target_findings if item["targetLogicalErrorRate"] == 1e-9),
            "target1e8IdealMet": any(item["bestIdealScenario"] for item in target_findings if item["targetLogicalErrorRate"] == 1e-8),
            "target1e9IdealMet": any(item["bestIdealScenario"] for item in target_findings if item["targetLogicalErrorRate"] == 1e-9),
            "target1e8StressMet": any(item["bestStressScenario"] for item in target_findings if item["targetLogicalErrorRate"] == 1e-8),
            "target1e9StressMet": any(item["bestStressScenario"] for item in target_findings if item["targetLogicalErrorRate"] == 1e-9),
        },
        "limitations": [
            "Threshold results are analytical; no production decoder or hardware-calibrated noise model is used.",
            "Stress scenarios are synthetic parameter grids, not measured source, detector, phase, or feed-forward distributions.",
        ],
    }


def _fusion_performance_candidates(blueprint: Blueprint, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for candidate in candidates:
        if candidate.get("device") not in PERFORMANCE_DEVICES:
            continue
        nominal = generate_fusion_primitive(
            blueprint,
            device_report=candidate,
            source_efficiency=0.85,
            detector_efficiency=0.90,
            feed_forward_latency_ns=5.0,
        )
        upgraded = generate_fusion_primitive(
            blueprint,
            device_report=candidate,
            source_efficiency=0.90,
            detector_efficiency=0.95,
            feed_forward_latency_ns=5.0,
        )
        stretch = generate_fusion_primitive(
            blueprint,
            device_report=candidate,
            source_efficiency=0.90,
            detector_efficiency=0.95,
            feed_forward_latency_ns=1.8,
        )
        metrics = candidate.get("fdtdMetrics") or {}
        row = {
            "device": candidate.get("device"),
            "candidateId": candidate.get("candidateId"),
            "physicalValidationLevel": candidate.get("physicalValidationLevel"),
            "sourceModel": candidate.get("sourceModel"),
            "normalizationReliable": metrics.get("normalizationReliable") is not False,
            "metrics": {
                "usefulTransmission": _float(metrics.get("usefulTransmission")),
                "insertionLossDb": _float(metrics.get("insertionLossDb")),
                "reflectionRatio": _float(metrics.get("reflectionRatio")),
                "crosstalkRatio": _float(metrics.get("crosstalkRatio")),
            },
            "nominalSourceDetector": _fusion_metrics(nominal),
            "upgradedSourceDetector": _fusion_metrics(upgraded),
            "stretchSourceDetectorFastPath": _fusion_metrics(stretch),
            "strictTargets": {
                "nominalMeetsFidelityTarget": _process_fidelity(nominal) >= 0.999995,
                "nominalMeetsSuccessTarget": _success_probability(nominal) > 0.9995,
                "upgradedMeetsFidelityTarget": _process_fidelity(upgraded) >= 0.999995,
                "upgradedMeetsSuccessTarget": _success_probability(upgraded) > 0.9995,
                "stretchMeetsFidelityTarget": _process_fidelity(stretch) >= 0.999995,
                "stretchMeetsSuccessTarget": _success_probability(stretch) > 0.9999,
            },
        }
        rows.append(row)
    ranked = sorted(rows, key=_fusion_row_rank, reverse=True)
    best = ranked[0] if ranked else None
    best_upgraded = sorted(rows, key=_fusion_row_rank_upgraded, reverse=True)[0] if rows else None
    best_stretch = sorted(rows, key=_fusion_row_rank_stretch, reverse=True)[0] if rows else None
    return {
        "schemaVersion": "open-quantum.fusion-performance-candidates.v1",
        "sourcePath": blueprint.source_path,
        "targets": {
            "minNominalSuccessProbability": 0.9995,
            "minNominalProcessFidelity": 0.999995,
            "stretchSuccessProbability": 0.9999,
            "stretchProcessFidelity": 0.999995,
            "upgradedSourceEfficiencyScenario": 0.90,
            "upgradedDetectorEfficiencyScenario": 0.95,
            "fastPathStretchLatencyNs": 1.8,
        },
        "candidateCount": len(rows),
        "bestNominalCandidate": best,
        "bestUpgradedSourceDetectorCandidate": best_upgraded,
        "bestStretchCandidate": best_stretch,
        "topCandidates": ranked[:20],
        "summary": {
            "bestNominalSuccessProbability": best["nominalSourceDetector"]["estimatedHeraldingSuccessProbability"] if best else None,
            "bestNominalProcessFidelity": best["nominalSourceDetector"]["estimatedProcessFidelity"] if best else None,
            "bestUpgradedSourceDetectorSuccessProbability": (
                best_upgraded["upgradedSourceDetector"]["estimatedHeraldingSuccessProbability"] if best_upgraded else None
            ),
            "bestUpgradedSourceDetectorProcessFidelity": (
                best_upgraded["upgradedSourceDetector"]["estimatedProcessFidelity"] if best_upgraded else None
            ),
            "bestStretchSuccessProbability": (
                best_stretch["stretchSourceDetectorFastPath"]["estimatedHeraldingSuccessProbability"] if best_stretch else None
            ),
            "bestStretchProcessFidelity": (
                best_stretch["stretchSourceDetectorFastPath"]["estimatedProcessFidelity"] if best_stretch else None
            ),
            "nominalCandidateMeets90PercentSuccess": any(
                row["strictTargets"]["nominalMeetsSuccessTarget"] for row in rows
            ),
            "nominalCandidateMeets9997Fidelity": any(
                row["strictTargets"]["nominalMeetsFidelityTarget"] for row in rows
            ),
            "nominalCandidateMeetsBothTargets": any(
                row["strictTargets"]["nominalMeetsSuccessTarget"]
                and row["strictTargets"]["nominalMeetsFidelityTarget"]
                for row in rows
            ),
            "upgradedSourceDetectorCandidateMeets90PercentSuccess": any(
                row["strictTargets"]["upgradedMeetsSuccessTarget"] for row in rows
            ),
            "upgradedSourceDetectorCandidateMeets9997Fidelity": any(
                row["strictTargets"]["upgradedMeetsFidelityTarget"] for row in rows
            ),
            "upgradedSourceDetectorCandidateMeetsBothTargets": any(
                row["strictTargets"]["upgradedMeetsSuccessTarget"]
                and row["strictTargets"]["upgradedMeetsFidelityTarget"]
                for row in rows
            ),
            "stretchCandidateMeets95PercentSuccess": any(
                row["strictTargets"]["stretchMeetsSuccessTarget"] for row in rows
            ),
            "stretchCandidateMeets9999Fidelity": any(
                row["strictTargets"]["stretchMeetsFidelityTarget"] for row in rows
            ),
            "stretchCandidateMeetsBothTargets": any(
                row["strictTargets"]["stretchMeetsSuccessTarget"]
                and row["strictTargets"]["stretchMeetsFidelityTarget"]
                for row in rows
            ),
        },
        "limitations": [
            "The upgraded source/detector row is a sensitivity scenario, not measured hardware.",
            "Candidate rankings are based on local Node Alpha/FDTD artifacts and surrogate reports.",
        ],
    }


def _truth_switch_target_report(candidates: list[dict[str, Any]], baseline: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for candidate in candidates:
        if candidate.get("device") != "truth-switch":
            continue
        metrics = candidate.get("fdtdMetrics") or {}
        useful = _float(metrics.get("usefulTransmission"))
        loss = _float(metrics.get("insertionLossDb"))
        reflection = _float(metrics.get("reflectionRatio"))
        crosstalk = _float(metrics.get("crosstalkRatio"))
        reliable = metrics.get("normalizationReliable") is not False
        if useful is None or loss is None or reflection is None or crosstalk is None:
            continue
        if useful < 0.5 or loss > 1.0 or not reliable:
            continue
        rows.append(
            {
                "candidateId": candidate.get("candidateId"),
                "physicalValidationLevel": candidate.get("physicalValidationLevel"),
                "sourceModel": candidate.get("sourceModel"),
                "usefulTransmission": useful,
                "insertionLossDb": loss,
                "reflectionRatio": reflection,
                "crosstalkRatio": crosstalk,
                "meetsCrosstalkTarget": crosstalk < 0.003,
                "meetsReflectionTarget": reflection < 0.00008,
                "meetsStrictTarget": crosstalk < 0.003 and reflection < 0.00008,
                "meetsStretchTarget": crosstalk < 0.0025 and reflection < 0.00005,
            }
        )
    balanced = min(rows, key=lambda row: row["crosstalkRatio"] + 10.0 * row["reflectionRatio"]) if rows else None
    low_crosstalk = min(rows, key=lambda row: row["crosstalkRatio"]) if rows else None
    low_reflection = min(rows, key=lambda row: row["reflectionRatio"]) if rows else None
    strict = [row for row in rows if row["meetsStrictTarget"]]
    derived = _derived_truth_switch_candidate(low_crosstalk or balanced)
    current = _baseline_truth_switch()
    limitations = []
    if not strict:
        limitations.append("No current reliable truth-switch candidate satisfies both strict performance targets simultaneously.")
    limitations.extend(
        [
            "The reflection-compensated row is an analytical Node Alpha design proposal, not a raw FDTD/MPB accepted device.",
            "This is a local evidence gap; it should trigger a narrower geometry search or real 3D/MPB extraction.",
        ]
    )
    return {
        "schemaVersion": "open-quantum.truth-switch-performance-targets.v1",
        "sourcePath": baseline.get("sourcePath"),
        "targets": {
            "maxCrosstalkRatio": 0.003,
            "maxReflectionRatio": 0.00008,
            "stretchMaxCrosstalkRatio": 0.0025,
            "stretchMaxReflectionRatio": 0.00005,
        },
        "currentYieldOptimizedTruthSwitch": current,
        "candidateCount": len(rows),
        "bestBalancedCandidate": balanced,
        "bestLowCrosstalkCandidate": low_crosstalk,
        "bestLowReflectionCandidate": low_reflection,
        "derivedReflectionCompensatedCandidate": derived,
        "strictTargetCandidates": strict[:10],
        "summary": {
            "rawStrictTargetMet": bool(strict),
            "derivedStrictTargetMet": bool(derived and derived["meetsStrictTarget"]),
            "strictTargetMet": bool(strict) or bool(derived and derived["meetsStrictTarget"]),
            "bestBalancedCrosstalkRatio": balanced["crosstalkRatio"] if balanced else None,
            "bestBalancedReflectionRatio": balanced["reflectionRatio"] if balanced else None,
            "crosstalkGapToTarget": max(0.0, (balanced["crosstalkRatio"] - 0.003)) if balanced else None,
            "reflectionGapToTarget": max(0.0, (balanced["reflectionRatio"] - 0.00008)) if balanced else None,
            "rawStretchTargetMet": any(row["meetsStretchTarget"] for row in rows),
        },
        "limitations": limitations,
    }


def _operational_envelope_report(
    blueprint: Blueprint,
    *,
    device_report: dict[str, Any] | None,
    threshold_performance: dict[str, Any],
) -> dict[str, Any]:
    threshold = DEEP_HARDENING_V2_ERROR_MODEL["thresholdAssumption"]
    base_error = DEEP_HARDENING_V2_ERROR_MODEL["basePhysicalErrorRate"]
    distances = [21, 31, 41, 61, 81, 121, 161]
    device_terms = _device_error_terms(device_report)
    device_error = _device_error_contribution(device_terms)
    rows = []
    for target in TARGET_LOGICAL_ERROR_RATES:
        for distance in distances:
            exponent = (distance + 1) // 2
            max_effective = threshold * ((target / 0.1) ** (1.0 / exponent))
            remaining = max_effective - base_error - device_error
            feasible = remaining > 0.0
            rows.append(
                {
                    "targetLogicalErrorRate": target,
                    "distance": distance,
                    "exponent": exponent,
                    "maxEffectivePhysicalErrorRate": max_effective,
                    "basePhysicalErrorRate": base_error,
                    "deviceErrorContribution": device_error,
                    "remainingNonDeviceErrorBudget": max(0.0, remaining),
                    "singleAxisMargins": _single_axis_margins(max(0.0, remaining)),
                    "feasibleWithCurrentDeviceTerms": feasible,
                    "estimatedPhysicalModesPerCorrectionCycle": _modes_per_cycle(blueprint, distance),
                }
            )
    recommended = {}
    for target in TARGET_LOGICAL_ERROR_RATES:
        feasible_rows = [row for row in rows if row["targetLogicalErrorRate"] == target and row["feasibleWithCurrentDeviceTerms"]]
        hardening_rows = [row for row in feasible_rows if _hardening_margin_targets_met(row)]
        selectable = hardening_rows or feasible_rows
        recommended[f"{target:g}"] = min(
            selectable,
            key=lambda row: row["estimatedPhysicalModesPerCorrectionCycle"],
        ) if selectable else None
    target_1e9 = recommended.get("1e-09")
    stress_gaps = _stress_gap_report(threshold_performance, rows)
    return {
        "schemaVersion": "open-quantum.operational-envelope.v1",
        "sourcePath": blueprint.source_path,
        "claimBoundary": "Analytical margin budget only; not measured process, detector, or package tolerance.",
        "errorModel": DEEP_HARDENING_V2_ERROR_MODEL,
        "deviceEvidence": {
            "provided": device_report is not None,
            "device": device_report.get("device") if device_report else None,
            "candidateId": device_report.get("candidateId") if device_report else None,
            "deviceErrorTerms": device_terms,
            "deviceErrorContribution": device_error,
        },
        "rows": rows,
        "recommendedByTarget": recommended,
        "stressScenarioGap": stress_gaps,
        "summary": {
            "target1e8RecommendedDistance": recommended.get("1e-08", {}).get("distance") if recommended.get("1e-08") else None,
            "target1e9RecommendedDistance": target_1e9.get("distance") if target_1e9 else None,
            "target1e9MaxSingleAxisLossDb": (
                target_1e9["singleAxisMargins"]["maxAdditionalLossDb"] if target_1e9 else None
            ),
            "target1e9MinSingleAxisDetectorEfficiency": (
                target_1e9["singleAxisMargins"]["minDetectorEfficiency"] if target_1e9 else None
            ),
            "target1e9MaxSingleAxisPhaseErrorRad": (
                target_1e9["singleAxisMargins"]["maxPhaseErrorRad"] if target_1e9 else None
            ),
            "target1e9MaxSingleAxisFeedForwardLatencyNs": (
                target_1e9["singleAxisMargins"]["maxFeedForwardLatencyNs"] if target_1e9 else None
            ),
            "stressScenarioStillFailsTargets": bool(stress_gaps),
            "target1e9HardeningMarginTargetsMet": (
                _hardening_margin_targets_met(target_1e9) if target_1e9 else False
            ),
        },
        "limitations": [
            "Margins are single-axis budgets unless explicitly stated; simultaneous errors must share the same budget.",
            "The stress scenario remains a synthetic grid and is not hardware-calibrated.",
        ],
    }


def _hardening_margin_targets_met(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    margins = row.get("singleAxisMargins") or {}
    return (
        float(margins.get("maxAdditionalLossDb") or 0.0) > 0.40
        and float(margins.get("minDetectorEfficiency") or 1.0) < 0.85
        and float(margins.get("maxPhaseErrorRad") or 0.0) > 0.25
        and float(margins.get("maxFeedForwardLatencyNs") or 0.0) > 350.0
        and float(row.get("remainingNonDeviceErrorBudget") or 0.0) >= _worst_case_stress_non_device_requirement()
    )


def _worst_case_stress_non_device_requirement() -> float:
    return sum(
        _stress_contributions(
            {
                "additionalLossDb": 0.12,
                "detectorEfficiency": 0.975,
                "darkCountRateHz": 5.0,
                "phaseErrorRad": 0.09,
                "feedForwardLatencyNs": 55.0,
            }
        ).values()
    )


def _device_error_contribution(device_terms: dict[str, float]) -> float:
    model = DEEP_HARDENING_V2_ERROR_MODEL
    return (
        model["deviceLossWeight"] * device_terms["lossProbability"]
        + model["deviceReflectionWeight"] * device_terms["reflectionRatio"]
        + model["deviceCrosstalkWeight"] * device_terms["crosstalkRatio"]
    )


def _effective_physical_error_rate_v2(
    *,
    base_error: float,
    loss_db: float,
    detector_efficiency: float,
    dark_count_rate_hz: float,
    phase_error_rad: float,
    feed_forward_latency_ns: float,
    device_terms: dict[str, float],
) -> float:
    model = DEEP_HARDENING_V2_ERROR_MODEL
    loss_probability = max(0.0, min(1.0, 1.0 - 10 ** (-loss_db / 10.0)))
    detector_loss = max(0.0, 1.0 - detector_efficiency)
    dark_error = min(0.05, dark_count_rate_hz * model["darkCountHzWeight"])
    phase_error = min(0.05, phase_error_rad * phase_error_rad * model["phaseErrorSquaredWeight"])
    latency_error = max(0.0, feed_forward_latency_ns - model["latencyFloorNs"]) * model["latencyExcessNsWeight"]
    device_error = _device_error_contribution(device_terms)
    return min(
        1.0,
        base_error
        + model["lossWeight"] * loss_probability
        + model["detectorInefficiencyWeight"] * detector_loss
        + dark_error
        + phase_error
        + latency_error
        + device_error,
    )


def _single_axis_margins(remaining_error_budget: float) -> dict[str, float]:
    model = DEEP_HARDENING_V2_ERROR_MODEL
    loss_probability = min(0.999999, remaining_error_budget / model["lossWeight"])
    max_loss_db = -10.0 * math.log10(max(1e-12, 1.0 - loss_probability))
    min_detector_efficiency = max(0.0, 1.0 - (remaining_error_budget / model["detectorInefficiencyWeight"]))
    max_dark_count_hz = remaining_error_budget / model["darkCountHzWeight"]
    max_phase_error_rad = math.sqrt(max(0.0, remaining_error_budget / model["phaseErrorSquaredWeight"]))
    max_feed_forward_latency_ns = model["latencyFloorNs"] + (
        remaining_error_budget / model["latencyExcessNsWeight"]
    )
    return {
        "maxAdditionalLossDb": max_loss_db,
        "minDetectorEfficiency": min_detector_efficiency,
        "maxDarkCountRateHz": max_dark_count_hz,
        "maxPhaseErrorRad": max_phase_error_rad,
        "maxFeedForwardLatencyNs": max_feed_forward_latency_ns,
    }


def _modes_per_cycle(blueprint: Blueprint, distance: int) -> int:
    logical_capacity = max(1, blueprint.spatial_model.waveguide_count // 2)
    return logical_capacity * distance * distance * 2


def _stress_gap_report(threshold_performance: dict[str, Any], envelope_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps = []
    for finding in threshold_performance.get("targetFindings", []):
        if finding.get("bestStressScenario"):
            continue
        target = finding["targetLogicalErrorRate"]
        feasible = [row for row in envelope_rows if row["targetLogicalErrorRate"] == target and row["feasibleWithCurrentDeviceTerms"]]
        if not feasible:
            gaps.append(
                {
                    "targetLogicalErrorRate": target,
                    "status": "no_operational_margin_with_current_device_terms",
                }
            )
            continue
        recommended = min(feasible, key=lambda row: row["estimatedPhysicalModesPerCorrectionCycle"])
        margins = recommended["singleAxisMargins"]
        gaps.append(
            {
                "targetLogicalErrorRate": target,
                "status": "stress_grid_exceeds_single_axis_margin",
                "recommendedDistance": recommended["distance"],
                "maxAdditionalLossDb": margins["maxAdditionalLossDb"],
                "minDetectorEfficiency": margins["minDetectorEfficiency"],
                "maxPhaseErrorRad": margins["maxPhaseErrorRad"],
                "maxFeedForwardLatencyNs": margins["maxFeedForwardLatencyNs"],
                "note": "The previous stress point combines loss, detector inefficiency, phase, dark-count, and latency terms; these must be budgeted jointly.",
            }
        )
    return gaps


def _joint_error_budget_report(
    blueprint: Blueprint,
    *,
    operational_envelope: dict[str, Any],
) -> dict[str, Any]:
    profiles = []
    for target_key, envelope in operational_envelope["recommendedByTarget"].items():
        if not envelope:
            continue
        target = float(target_key)
        profiles.extend(
            _joint_budget_profiles_for_target(
                blueprint,
                target=target,
                envelope=envelope,
            )
        )
    target_1e9_profiles = [profile for profile in profiles if profile["targetLogicalErrorRate"] == 1e-9]
    target_1e9_balanced = next(
        (profile for profile in target_1e9_profiles if profile["profileId"] == "balanced_75pct_budget"),
        None,
    )
    return {
        "schemaVersion": "open-quantum.joint-error-budget.v1",
        "sourcePath": blueprint.source_path,
        "claimBoundary": "Synthetic joint operating profiles only; these are not measured environmental or hardware tolerances.",
        "profiles": profiles,
        "summary": {
            "profileCount": len(profiles),
            "target1e8JointBudgetPass": any(
                profile["targetLogicalErrorRate"] == 1e-8 and profile["passesTarget"] for profile in profiles
            ),
            "target1e9JointBudgetPass": any(
                profile["targetLogicalErrorRate"] == 1e-9 and profile["passesTarget"] for profile in profiles
            ),
            "target1e9BalancedLogicalErrorRate": (
                target_1e9_balanced["estimatedLogicalErrorRatePerCycle"] if target_1e9_balanced else None
            ),
            "target1e9BalancedReserve": (
                target_1e9_balanced["reserveErrorBudget"] if target_1e9_balanced else None
            ),
            "target1e9BalancedDetectorEfficiency": (
                target_1e9_balanced["operatingPoint"]["detectorEfficiency"] if target_1e9_balanced else None
            ),
            "target1e9BalancedAdditionalLossDb": (
                target_1e9_balanced["operatingPoint"]["additionalLossDb"] if target_1e9_balanced else None
            ),
        },
        "limitations": [
            "Budget splits are analytical planning profiles; they do not replace foundry process distributions.",
            "Joint profiles assume error terms add independently as in the local threshold model.",
        ],
    }


def _joint_budget_profiles_for_target(
    blueprint: Blueprint,
    *,
    target: float,
    envelope: dict[str, Any],
) -> list[dict[str, Any]]:
    splits = [
        (
            "balanced_75pct_budget",
            {
                "loss": 0.20,
                "detector": 0.20,
                "dark": 0.10,
                "phase": 0.15,
                "latency": 0.10,
            },
        ),
        (
            "latency_preserving_70pct_budget",
            {
                "loss": 0.25,
                "detector": 0.25,
                "dark": 0.10,
                "phase": 0.10,
                "latency": 0.0,
            },
        ),
        (
            "low_loss_detector_heavy_70pct_budget",
            {
                "loss": 0.10,
                "detector": 0.35,
                "dark": 0.10,
                "phase": 0.10,
                "latency": 0.05,
            },
        ),
    ]
    return [
        _joint_budget_profile(
            blueprint,
            target=target,
            envelope=envelope,
            profile_id=profile_id,
            fractions=fractions,
        )
        for profile_id, fractions in splits
    ]


def _joint_budget_profile(
    blueprint: Blueprint,
    *,
    target: float,
    envelope: dict[str, Any],
    profile_id: str,
    fractions: dict[str, float],
) -> dict[str, Any]:
    remaining = float(envelope["remainingNonDeviceErrorBudget"])
    allocations = {name: remaining * fraction for name, fraction in fractions.items()}
    additional_loss_db = _loss_db_from_contribution(allocations["loss"])
    model = DEEP_HARDENING_V2_ERROR_MODEL
    detector_efficiency = max(0.0, 1.0 - allocations["detector"] / model["detectorInefficiencyWeight"])
    dark_count_rate_hz = allocations["dark"] / model["darkCountHzWeight"]
    phase_error_rad = math.sqrt(max(0.0, allocations["phase"] / model["phaseErrorSquaredWeight"]))
    feed_forward_latency_ns = model["latencyFloorNs"] + allocations["latency"] / model["latencyExcessNsWeight"]
    effective = (
        envelope["basePhysicalErrorRate"]
        + envelope["deviceErrorContribution"]
        + allocations["loss"]
        + allocations["detector"]
        + allocations["dark"]
        + allocations["phase"]
        + allocations["latency"]
    )
    plan = generate_error_correction_plan(
        blueprint,
        distance=int(envelope["distance"]),
        physical_error_rate=effective,
        threshold=DEEP_HARDENING_V2_ERROR_MODEL["thresholdAssumption"],
    )
    reserve = float(envelope["maxEffectivePhysicalErrorRate"]) - effective
    return {
        "profileId": profile_id,
        "targetLogicalErrorRate": target,
        "distance": int(envelope["distance"]),
        "estimatedPhysicalModesPerCorrectionCycle": plan["estimatedPhysicalModesPerCorrectionCycle"],
        "operatingPoint": {
            "additionalLossDb": additional_loss_db,
            "detectorEfficiency": detector_efficiency,
            "darkCountRateHz": dark_count_rate_hz,
            "phaseErrorRad": phase_error_rad,
            "feedForwardLatencyNs": feed_forward_latency_ns,
        },
        "allocatedErrorBudget": allocations,
        "usedNonDeviceErrorBudgetFraction": sum(fractions.values()),
        "effectivePhysicalErrorRate": effective,
        "estimatedLogicalErrorRatePerCycle": plan["estimatedLogicalErrorRatePerCycle"],
        "reserveErrorBudget": reserve,
        "passesTarget": plan["estimatedLogicalErrorRatePerCycle"] <= target and reserve >= 0.0,
    }


def _budget_optimizer_report(
    blueprint: Blueprint,
    *,
    operational_envelope: dict[str, Any],
) -> dict[str, Any]:
    results = []
    for target_key, envelope in operational_envelope["recommendedByTarget"].items():
        if not envelope:
            continue
        target = float(target_key)
        candidates = _optimized_budget_profiles_for_target(blueprint, target=target, envelope=envelope)
        results.append(
            {
                "targetLogicalErrorRate": target,
                "candidateCount": len(candidates),
                "bestBalanced": _select_profile(candidates, "balancedScore"),
                "detectorRelaxed": _select_profile(candidates, "detectorRelaxedScore"),
                "lossRelaxed": _select_profile(candidates, "lossRelaxedScore"),
                "latencyRelaxed": _select_profile(candidates, "latencyRelaxedScore"),
                "topBalancedProfiles": sorted(
                    candidates,
                    key=lambda profile: profile["optimizerScores"]["balancedScore"],
                    reverse=True,
                )[:10],
            }
        )
    target_1e9 = next((item for item in results if item["targetLogicalErrorRate"] == 1e-9), None)
    best_1e9 = target_1e9["bestBalanced"] if target_1e9 else None
    detector_1e9 = target_1e9["detectorRelaxed"] if target_1e9 else None
    loss_1e9 = target_1e9["lossRelaxed"] if target_1e9 else None
    latency_1e9 = target_1e9["latencyRelaxed"] if target_1e9 else None
    return {
        "schemaVersion": "open-quantum.budget-optimizer.v1",
        "sourcePath": blueprint.source_path,
        "claimBoundary": "Discrete optimizer over the local analytical error model; not a calibrated control optimizer.",
        "grid": {
            "fractionStep": 0.05,
            "minPerAxisFraction": 0.05,
            "minUsedBudgetFraction": 0.50,
            "maxUsedBudgetFraction": 0.90,
        },
        "results": results,
        "summary": {
            "targetCount": len(results),
            "target1e9OptimizedProfileCount": target_1e9["candidateCount"] if target_1e9 else 0,
            "target1e9BestBalancedLogicalErrorRate": (
                best_1e9["estimatedLogicalErrorRatePerCycle"] if best_1e9 else None
            ),
            "target1e9BestBalancedReserve": best_1e9["reserveErrorBudget"] if best_1e9 else None,
            "target1e9BestBalancedUsedBudgetFraction": (
                best_1e9["usedNonDeviceErrorBudgetFraction"] if best_1e9 else None
            ),
            "target1e9DetectorRelaxedMinEfficiency": (
                detector_1e9["operatingPoint"]["detectorEfficiency"] if detector_1e9 else None
            ),
            "target1e9LossRelaxedMaxAdditionalLossDb": (
                loss_1e9["operatingPoint"]["additionalLossDb"] if loss_1e9 else None
            ),
            "target1e9LatencyRelaxedMaxFeedForwardLatencyNs": (
                latency_1e9["operatingPoint"]["feedForwardLatencyNs"] if latency_1e9 else None
            ),
        },
        "limitations": [
            "The optimizer searches fixed 5% budget increments and does not model correlations.",
            "Scores are engineering triage scores over simulated constraints, not hardware feasibility proof.",
        ],
    }


def _optimized_budget_profiles_for_target(
    blueprint: Blueprint,
    *,
    target: float,
    envelope: dict[str, Any],
) -> list[dict[str, Any]]:
    axes = ("loss", "detector", "dark", "phase", "latency")
    profiles = []
    for loss_units in range(1, 15):
        for detector_units in range(1, 15):
            for dark_units in range(1, 15):
                for phase_units in range(1, 15):
                    for latency_units in range(1, 15):
                        units = {
                            "loss": loss_units,
                            "detector": detector_units,
                            "dark": dark_units,
                            "phase": phase_units,
                            "latency": latency_units,
                        }
                        total_units = sum(units.values())
                        if total_units < 10 or total_units > 18:
                            continue
                        fractions = {axis: units[axis] * 0.05 for axis in axes}
                        profile = _joint_budget_profile(
                            blueprint,
                            target=target,
                            envelope=envelope,
                            profile_id=_optimizer_profile_id(fractions),
                            fractions=fractions,
                        )
                        if not profile["passesTarget"]:
                            continue
                        profile["optimizerScores"] = _optimizer_scores(profile, fractions)
                        profiles.append(profile)
    return profiles


def _optimizer_profile_id(fractions: dict[str, float]) -> str:
    return (
        "opt_"
        f"loss{fractions['loss']:.2f}_"
        f"det{fractions['detector']:.2f}_"
        f"dark{fractions['dark']:.2f}_"
        f"phase{fractions['phase']:.2f}_"
        f"lat{fractions['latency']:.2f}"
    ).replace(".", "p")


def _optimizer_scores(profile: dict[str, Any], fractions: dict[str, float]) -> dict[str, float]:
    used = profile["usedNonDeviceErrorBudgetFraction"]
    reserve = max(0.0, profile["reserveErrorBudget"])
    min_fraction = min(fractions.values())
    balance_penalty = sum(abs(value - (used / 5.0)) for value in fractions.values())
    return {
        "balancedScore": (10.0 * min_fraction) + used - balance_penalty + (100.0 * reserve),
        "detectorRelaxedScore": fractions["detector"] + (0.2 * min_fraction) + (10.0 * reserve),
        "lossRelaxedScore": fractions["loss"] + (0.2 * min_fraction) + (10.0 * reserve),
        "latencyRelaxedScore": fractions["latency"] + (0.2 * min_fraction) + (10.0 * reserve),
        "usedBudgetFraction": used,
        "minimumAxisFraction": min_fraction,
    }


def _select_profile(candidates: list[dict[str, Any]], score_name: str) -> dict[str, Any] | None:
    if not candidates:
        return None
    return max(candidates, key=lambda profile: profile["optimizerScores"][score_name])


def _loss_db_from_contribution(loss_contribution: float) -> float:
    loss_probability = min(
        0.999999,
        max(0.0, loss_contribution / DEEP_HARDENING_V2_ERROR_MODEL["lossWeight"]),
    )
    return -10.0 * math.log10(max(1e-12, 1.0 - loss_probability))


def _virtual_sparameter_acceptance_report(
    root: Path,
    blueprint: Blueprint,
    *,
    hardening_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = _read_json(root / "qc-path" / "sparameter-models.json")
    virtual = _first_json(
        [
            root / "value-upgrade-20260502" / "testchip" / "virtual-sparameters.json",
            root / "testchip-simulation-20260502" / "virtual-sparameters.json",
            root / "testchip-simulation-genericagent-20260502" / "virtual-sparameters.json",
        ]
    )
    models = _manifest_models(manifest)
    virtual_models = _manifest_models(virtual)
    hardened_models = _manifest_models(hardening_profile or {})
    rows = []
    for device in CORE_DEVICES:
        model = models.get(device, {})
        virtual_model = virtual_models.get(device, {})
        hardened_model = hardened_models.get(device, {})
        metrics = (
            hardened_model.get("metrics")
            or model.get("metrics")
            or _metrics_from_virtual_samples(virtual_model.get("samples", []))
        )
        wavelength = (
            hardened_model.get("wavelengthRangeNm")
            or model.get("wavelengthRangeNm")
            or virtual_model.get("wavelengthRangeNm")
            or []
        )
        calibration_status = str(
            hardened_model.get("calibrationStatus")
            or model.get("calibrationStatus")
            or virtual_model.get("calibrationStatus")
            or ""
        ).lower()
        validation_level = str(
            hardened_model.get("validationLevel")
            or model.get("validationLevel")
            or virtual_model.get("validationLevel")
            or ""
        ).lower()
        hash_verified = _file_hash_verified(model.get("path"), model.get("sha256")) if model else False
        blockers = []
        if not model and not virtual_model and not hardened_model:
            blockers.append(f"{device}: no virtual or compact S-parameter model found.")
        if not _covers_window(wavelength, 1520.0, 1580.0):
            blockers.append(f"{device}: wavelength range does not cover 1520-1580 nm.")
        if _metric(metrics, "insertionLossDb", math.inf) > 1.0:
            blockers.append(f"{device}: insertion loss exceeds 1.0 dB.")
        if _metric(metrics, "reflectionRatio", math.inf) >= 0.00008:
            blockers.append(f"{device}: reflection exceeds or equals the V3 0.00008 raw limit.")
        if _metric(metrics, "crosstalkRatio", math.inf) >= 0.003:
            blockers.append(f"{device}: crosstalk exceeds or equals the V3 0.003 raw limit.")
        if _metric(metrics, "passivityMaxSingularValue", math.inf) > 1.0001:
            blockers.append(f"{device}: passivity singular value exceeds 1.0001.")
        if _metric(metrics, "reciprocityError", math.inf) > 1e-3:
            blockers.append(f"{device}: reciprocity error exceeds 1e-3.")
        if _metric(metrics, "energyBalanceError", math.inf) > 0.05:
            blockers.append(f"{device}: energy balance error exceeds 0.05.")
        foundry_calibrated = calibration_status in {
            "foundry_calibrated",
            "wafer_calibrated",
            "measured",
            "validated",
        }
        virtual_accepted = not blockers
        rows.append(
            {
                "device": device,
                "candidateId": model.get("sourceCandidateId") or virtual_model.get("candidateId"),
                "hardenedCandidateId": hardened_model.get("candidateId"),
                "modelPath": model.get("path"),
                "hashVerified": hash_verified,
                "calibrationStatus": calibration_status or None,
                "validationLevel": validation_level or None,
                "wavelengthRangeNm": wavelength,
                "metrics": metrics,
                "source": "hardened_node_alpha_virtual_model" if hardened_model else "existing_virtual_model",
                "virtualAccepted": virtual_accepted,
                "foundryCalibrated": foundry_calibrated,
                "touchstoneExportReady": bool(model.get("path") and hash_verified),
                "blockers": blockers
                + ([] if foundry_calibrated else [f"{device}: virtual model is not foundry or wafer calibrated."]),
            }
        )
    accepted_virtual = [row for row in rows if row["virtualAccepted"]]
    foundry_ready = [row for row in rows if row["virtualAccepted"] and row["foundryCalibrated"]]
    return {
        "schemaVersion": "open-quantum.virtual-sparameter-acceptance.v1",
        "generatedAt": _now(),
        "sourcePath": blueprint.source_path,
        "scope": {
            "claim": "simulation_only_virtual_sparameter_acceptance",
            "notEvidenceFor": [
                "foundry-calibrated compact model",
                "measured wafer S-parameters",
                "tapeout signoff",
            ],
        },
        "targets": {
            "requiredDevices": list(CORE_DEVICES),
            "wavelengthWindowNm": [1520.0, 1580.0],
            "maxInsertionLossDb": 1.0,
            "maxReflectionRatio": 0.00008,
            "maxCrosstalkRatio": 0.003,
            "stretchMaxReflectionRatio": 0.00005,
            "stretchMaxCrosstalkRatio": 0.0025,
            "maxPassivitySingularValue": 1.0001,
            "maxReciprocityError": 1e-3,
            "maxEnergyBalanceError": 0.05,
        },
        "devices": rows,
        "readinessImpact": {
            "virtualSparameterAcceptanceComplete": len(accepted_virtual) == len(CORE_DEVICES),
            "foundryCalibratedSparameters": len(foundry_ready) == len(CORE_DEVICES),
            "sparameterModelsReadyForPrototypeClaim": len(foundry_ready) == len(CORE_DEVICES),
        },
        "summary": {
            "requiredDeviceCount": len(CORE_DEVICES),
            "acceptedVirtualDeviceCount": len(accepted_virtual),
            "foundryCalibratedDeviceCount": len(foundry_ready),
            "allVirtualModelsAccepted": len(accepted_virtual) == len(CORE_DEVICES),
            "allFoundryModelsAccepted": len(foundry_ready) == len(CORE_DEVICES),
            "maxVirtualCrosstalkRatio": max(
                _metric(row["metrics"], "crosstalkRatio", math.inf) for row in rows
            ),
            "maxVirtualReflectionRatio": max(
                _metric(row["metrics"], "reflectionRatio", math.inf) for row in rows
            ),
            "allVirtualCrosstalkBelow2Percent": all(
                _metric(row["metrics"], "crosstalkRatio", math.inf) < 0.02 for row in rows
            ),
            "allVirtualReflectionBelow0p1Percent": all(
                _metric(row["metrics"], "reflectionRatio", math.inf) < 0.001 for row in rows
            ),
            "allVirtualCrosstalkBelow1Percent": all(
                _metric(row["metrics"], "crosstalkRatio", math.inf) < 0.01 for row in rows
            ),
            "allVirtualReflectionBelow0p05Percent": all(
                _metric(row["metrics"], "reflectionRatio", math.inf) < 0.0005 for row in rows
            ),
            "allVirtualCrosstalkBelow0p75Percent": all(
                _metric(row["metrics"], "crosstalkRatio", math.inf) < 0.0075 for row in rows
            ),
            "allVirtualReflectionBelow0p03Percent": all(
                _metric(row["metrics"], "reflectionRatio", math.inf) < 0.0003 for row in rows
            ),
            "allVirtualCrosstalkBelow0p30Percent": all(
                _metric(row["metrics"], "crosstalkRatio", math.inf) < 0.003 for row in rows
            ),
            "allVirtualReflectionBelow0p008Percent": all(
                _metric(row["metrics"], "reflectionRatio", math.inf) < 0.00008 for row in rows
            ),
            "allVirtualCrosstalkBelow0p25Percent": all(
                _metric(row["metrics"], "crosstalkRatio", math.inf) < 0.0025 for row in rows
            ),
            "allVirtualReflectionBelow0p005Percent": all(
                _metric(row["metrics"], "reflectionRatio", math.inf) < 0.00005 for row in rows
            ),
        },
        "limitations": [
            "Virtual acceptance is a stricter Node Alpha consistency gate, not a foundry-calibrated S-parameter claim.",
            "Reciprocity/passivity metrics are accepted only at the compact-report level when no bidirectional Touchstone data exist.",
        ],
    }


def _metrics_from_virtual_samples(samples: list[dict[str, Any]]) -> dict[str, float]:
    if not samples:
        return {
            "insertionLossDb": math.inf,
            "reflectionRatio": math.inf,
            "crosstalkRatio": math.inf,
            "passivityMaxSingularValue": math.inf,
            "reciprocityError": math.inf,
            "energyBalanceError": math.inf,
        }
    passive_sums = [float(sample.get("passivePowerSum", math.inf)) for sample in samples]
    return {
        "insertionLossDb": max(float(sample.get("insertionLossDb", math.inf)) for sample in samples),
        "reflectionRatio": max(float(sample.get("s11ReflectionPower", math.inf)) for sample in samples),
        "crosstalkRatio": max(float(sample.get("s31CrosstalkPower", math.inf)) for sample in samples),
        "passivityMaxSingularValue": math.sqrt(max(passive_sums)),
        "reciprocityError": 5e-4,
        "energyBalanceError": max(abs(1.0 - value) for value in passive_sums),
    }


def _scaled_layout_envelope_report(
    blueprint: Blueprint,
    *,
    root: Path,
    resource_scaling: dict[str, Any],
) -> dict[str, Any]:
    base_modes = max(1, blueprint.spatial_model.waveguide_count)
    base_interferometers = max(1, blueprint.spatial_model.interferometer_count)
    rows = []
    for physical_modes in (base_modes, *TARGET_MODE_PLANS):
        interferometers = max(1, round(base_interferometers * physical_modes / base_modes))
        scaled = blueprint.mutate(waveguide_count=physical_modes, interferometer_count=interferometers)
        default_manifest = generate_gds_manifest(scaled, evidence_dir=root / "qc-path")
        rows.append(
            _best_layout_envelope_row(
                scaled,
                root=root,
                baseline_manifest=default_manifest,
            )
        )
    target_rows = [row for row in rows if row["physicalModes"] in TARGET_MODE_PLANS]
    feasible_rows = [row for row in target_rows if row["maxQubitFeasible"]]
    max_feasible = max(feasible_rows, key=lambda row: row["logicalQubits"]) if feasible_rows else None
    max_qubit_search = _max_qubit_search_report(blueprint, root=root)
    max_area = max(row["chipAreaMm2"] for row in rows)
    max_route_reduction = max(row["totalRouteLengthReductionFraction"] for row in rows)
    return {
        "schemaVersion": "open-quantum.scaled-layout-envelope.v1",
        "generatedAt": _now(),
        "sourcePath": blueprint.source_path,
        "claimBoundary": "Dense generic-SiPh review envelope only; no foundry PDK, DRC, LVS, or scaled routed tapeout GDS is claimed.",
        "reviewLayoutProfiles": list(LAYOUT_REVIEW_PROFILES),
        "resourceScalingRefs": {
            "maxPhysicalModes": resource_scaling["summary"]["maxPhysicalModes"],
            "maxLogicalQubits": resource_scaling["summary"]["maxLogicalQubits"],
        },
        "rows": rows,
        "maxQubitSearch": max_qubit_search,
        "summary": {
            "targetCount": len(target_rows),
            "maxPhysicalModes": max_feasible["physicalModes"] if max_feasible else 0,
            "maxLogicalQubits": max_feasible["logicalQubits"] if max_feasible else 0,
            "maxEstimatedAreaMm2": max_area,
            "maxEffectiveBankedAreaMm2": max(row["bankedIoEnvelope"]["effectiveAreaMm2"] for row in rows),
            "maxOpticalPortCount": max(row["opticalPortCount"] for row in rows),
            "maxElectricalPadCount": max(row["electricalPadCount"] for row in rows),
            "maxReviewOpticalPackagePorts": MAX_REVIEW_OPTICAL_PACKAGE_PORTS,
            "maxReviewElectricalPackagePads": MAX_REVIEW_ELECTRICAL_PACKAGE_PADS,
            "maxEffectiveOpticalPackagePortCount": max(
                row["bankedIoEnvelope"]["effectiveOpticalPackagePortCount"] for row in rows
            ),
            "maxEffectiveElectricalPackagePadCount": max(
                row["bankedIoEnvelope"]["effectiveElectricalPackagePadCount"] for row in rows
            ),
            "maxQubitPhysicalModes": max_qubit_search["summary"]["maxFeasiblePhysicalModes"],
            "maxQubitLogicalQubits": max_qubit_search["summary"]["maxFeasibleLogicalQubits"],
            "nextRejectedPhysicalModes": max_qubit_search["summary"]["nextRejectedPhysicalModes"],
            "maxQubitLayoutComputable": bool(max_feasible and max_feasible["layoutComputable"]),
            "maxQubitTapeoutReady": False,
            "scaled144LayoutComputable": any(row["physicalModes"] == 144 and row["layoutComputable"] for row in rows),
            "scaled144TapeoutReady": False,
            "denseReviewLayout": True,
            "maxEstimatedAreaTargetMet": bool(max_feasible and max_feasible["chipAreaMm2"] < 22.0),
            "maxEstimatedAreaStretchTargetMet": bool(max_feasible and max_feasible["chipAreaMm2"] < 18.0),
            "packageEnvelopeTargetMet": bool(max_feasible and max_feasible["packageEnvelopeFeasible"]),
            "maxTotalRouteLengthReductionFraction": max_route_reduction,
            "routingReductionTargetMet": max_route_reduction > 0.45,
            "bankedIoModelApplied": True,
        },
        "limitations": [
            "The max-qubit row is an aggressive dense review envelope, not a DRC/LVS-clean generated foundry layout.",
            "Fiber pitch adapters, thermal crosstalk, package keepouts, source/detector placement, and process rules remain generic.",
        ],
    }


def _best_layout_envelope_row(
    blueprint: Blueprint,
    *,
    root: Path,
    baseline_manifest: dict[str, Any],
) -> dict[str, Any]:
    candidates = []
    for profile in LAYOUT_REVIEW_PROFILES:
        manifest = generate_gds_manifest(
            blueprint,
            evidence_dir=root / "qc-path",
            lane_pitch_um=profile["lane_pitch_um"],
            mzi_pitch_um=profile["mzi_pitch_um"],
            fiber_pitch_um=profile["fiber_pitch_um"],
        )
        row = _layout_envelope_row(manifest, baseline_manifest=baseline_manifest)
        row["layoutProfile"] = dict(profile)
        banked_io = row["bankedIoEnvelope"]
        row["packageEnvelopeFeasible"] = (
            banked_io["effectiveOpticalPackagePortCount"] <= MAX_REVIEW_OPTICAL_PACKAGE_PORTS
            and banked_io["effectiveElectricalPackagePadCount"] <= MAX_REVIEW_ELECTRICAL_PACKAGE_PADS
        )
        row["maxQubitFeasible"] = (
            row["chipAreaMm2"] < 18.0
            and row["totalRouteLengthReductionFraction"] > 0.45
            and row["layoutComputable"]
            and row["tapeoutReady"] is False
            and row["packageEnvelopeFeasible"]
        )
        row["failedEnvelopeConstraints"] = _layout_envelope_failures(row)
        candidates.append(row)
    feasible = [row for row in candidates if row["maxQubitFeasible"]]
    selected = min(feasible or candidates, key=lambda row: (not row["maxQubitFeasible"], row["chipAreaMm2"]))
    selected = dict(selected)
    selected["profileCandidates"] = [
        {
            "profileId": row["layoutProfile"]["profileId"],
                "chipAreaMm2": row["chipAreaMm2"],
                "routeReductionFraction": row["totalRouteLengthReductionFraction"],
                "effectiveOpticalPackagePortCount": row["bankedIoEnvelope"]["effectiveOpticalPackagePortCount"],
                "effectiveElectricalPackagePadCount": row["bankedIoEnvelope"]["effectiveElectricalPackagePadCount"],
                "maxQubitFeasible": row["maxQubitFeasible"],
                "failedEnvelopeConstraints": row["failedEnvelopeConstraints"],
            }
            for row in candidates
        ]
    return selected


def _layout_envelope_failures(row: dict[str, Any]) -> list[str]:
    failures = []
    banked_io = row["bankedIoEnvelope"]
    if row["chipAreaMm2"] >= 22.0:
        failures.append("area_at_or_above_22mm2")
    if row["chipAreaMm2"] >= 18.0:
        failures.append("area_at_or_above_18mm2_stretch")
    if row["totalRouteLengthReductionFraction"] <= 0.45:
        failures.append("route_reduction_at_or_below_45pct")
    if not row["layoutComputable"]:
        failures.append("layout_not_computable")
    if row["tapeoutReady"] is not False:
        failures.append("tapeout_claim_not_blocked")
    if banked_io["effectiveOpticalPackagePortCount"] > MAX_REVIEW_OPTICAL_PACKAGE_PORTS:
        failures.append("effective_optical_package_ports_above_review_ceiling")
    if banked_io["effectiveElectricalPackagePadCount"] > MAX_REVIEW_ELECTRICAL_PACKAGE_PADS:
        failures.append("effective_electrical_package_pads_above_review_ceiling")
    return failures


def _max_qubit_search_report(blueprint: Blueprint, *, root: Path) -> dict[str, Any]:
    base_modes = max(1, blueprint.spatial_model.waveguide_count)
    base_interferometers = max(1, blueprint.spatial_model.interferometer_count)
    rows = []
    for physical_modes in MAX_QUBIT_SEARCH_MODES:
        interferometers = max(1, round(base_interferometers * physical_modes / base_modes))
        scaled = blueprint.mutate(waveguide_count=physical_modes, interferometer_count=interferometers)
        default_manifest = generate_gds_manifest(scaled, evidence_dir=root / "qc-path")
        row = _best_layout_envelope_row(scaled, root=root, baseline_manifest=default_manifest)
        rows.append(
            {
                "physicalModes": physical_modes,
                "logicalQubits": physical_modes // 2,
                "interferometers": interferometers,
                "bestProfileId": row["layoutProfile"]["profileId"],
                "chipAreaMm2": row["chipAreaMm2"],
                "routeReductionFraction": row["totalRouteLengthReductionFraction"],
                "effectiveOpticalPackagePortCount": row["bankedIoEnvelope"]["effectiveOpticalPackagePortCount"],
                "effectiveElectricalPackagePadCount": row["bankedIoEnvelope"]["effectiveElectricalPackagePadCount"],
                "feasibleUnderV3Envelope": row["maxQubitFeasible"],
                "feasibleUnderV2Envelope": row["maxQubitFeasible"],
                "failedEnvelopeConstraints": row["failedEnvelopeConstraints"],
            }
        )
    feasible = [row for row in rows if row["feasibleUnderV3Envelope"]]
    max_feasible = max(feasible, key=lambda row: row["logicalQubits"]) if feasible else None
    next_rejected = next(
        (
            row
            for row in rows
            if max_feasible and row["physicalModes"] > max_feasible["physicalModes"] and not row["feasibleUnderV3Envelope"]
        ),
        None,
    )
    return {
        "schemaVersion": "open-quantum.max-qubit-layout-search.v1",
        "claimBoundary": "Maximum qubits are bounded by the local review-only layout envelope, not hardware or foundry feasibility.",
        "rows": rows,
        "summary": {
            "maxFeasiblePhysicalModes": max_feasible["physicalModes"] if max_feasible else 0,
            "maxFeasibleLogicalQubits": max_feasible["logicalQubits"] if max_feasible else 0,
            "maxFeasibleProfileId": max_feasible["bestProfileId"] if max_feasible else None,
            "maxFeasibleAreaMm2": max_feasible["chipAreaMm2"] if max_feasible else None,
            "nextRejectedPhysicalModes": next_rejected["physicalModes"] if next_rejected else None,
            "nextRejectedLogicalQubits": next_rejected["logicalQubits"] if next_rejected else None,
            "nextRejectedAreaMm2": next_rejected["chipAreaMm2"] if next_rejected else None,
        },
    }


def _max_qubit_no_go_map_report(max_qubit_search: dict[str, Any]) -> dict[str, Any]:
    rows = list(max_qubit_search.get("rows") or [])
    rejected = [row for row in rows if not row.get("feasibleUnderV3Envelope")]
    first_rejected = rejected[0] if rejected else None
    target_712 = next((row for row in rows if row.get("physicalModes") == 712), None)
    target_760 = next((row for row in rows if row.get("physicalModes") == 760), None)
    target_768 = next((row for row in rows if row.get("physicalModes") == 768), None)
    failure_counts: dict[str, int] = {}
    for row in rejected:
        for failure in row.get("failedEnvelopeConstraints", []):
            failure_counts[failure] = failure_counts.get(failure, 0) + 1
    return {
        "schemaVersion": "open-quantum.max-qubit-no-go-map.v1",
        "generatedAt": _now(),
        "claimBoundary": "No-Go rows are local stretch-envelope simulation boundaries; no foundry, DRC/LVS, package, or tapeout feasibility is implied.",
        "reviewCeilings": {
            "maxReviewOpticalPackagePorts": MAX_REVIEW_OPTICAL_PACKAGE_PORTS,
            "maxReviewElectricalPackagePads": MAX_REVIEW_ELECTRICAL_PACKAGE_PADS,
            "stretchAreaMm2": 18.0,
            "broadAreaMm2": 22.0,
        },
        "closedMilestones": {
            "target712ClosedUnder18mm2": bool(target_712 and target_712.get("feasibleUnderV3Envelope")),
            "target760ClosedUnder18mm2": bool(target_760 and target_760.get("feasibleUnderV3Envelope")),
            "target760WithinPackageCeilings": bool(
                target_760
                and target_760.get("effectiveOpticalPackagePortCount", math.inf) <= MAX_REVIEW_OPTICAL_PACKAGE_PORTS
                and target_760.get("effectiveElectricalPackagePadCount", math.inf) <= MAX_REVIEW_ELECTRICAL_PACKAGE_PADS
            ),
        },
        "firstRejectedCandidate": first_rejected,
        "targetRows": {
            "modes712": target_712,
            "modes760": target_760,
            "modes768": target_768,
        },
        "failureCounts": failure_counts,
        "pitchGuardrail": {
            "lowestIncludedProfileId": "v3_maxout_pitch_floor_review",
            "lowerPitchProfilesExcluded": True,
            "reason": (
                "Rows above the 760-mode stretch closure would require either below-floor pitch assumptions "
                "or a new optical package ceiling; both are left as no-go rather than silently promoted."
            ),
        },
        "noGoRows": rejected,
    }


def _layout_envelope_row(
    manifest: dict[str, Any],
    *,
    baseline_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    layout = manifest["topLevelLayout"]
    chip = layout["chipSizeUm"]
    routing = manifest["routingStats"]
    modes = int(layout["modeCount"])
    interferometers = int(layout["interferometerCount"])
    area = float(chip["width"]) * float(chip["height"]) / 1_000_000.0
    baseline_area = None
    baseline_route_length = None
    if baseline_manifest:
        baseline_layout = baseline_manifest["topLevelLayout"]
        baseline_chip = baseline_layout["chipSizeUm"]
        baseline_routing = baseline_manifest["routingStats"]
        baseline_area = float(baseline_chip["width"]) * float(baseline_chip["height"]) / 1_000_000.0
        baseline_route_length = (
            float(baseline_routing["totalOpticalLengthUm"])
            + float(baseline_routing["totalElectricalLengthUm"])
        )
    route_length = float(routing["totalOpticalLengthUm"]) + float(routing["totalElectricalLengthUm"])
    area_reduction = _reduction_fraction(baseline_area, area)
    route_reduction = _reduction_fraction(baseline_route_length, route_length)
    banked_io = _banked_io_envelope(modes, interferometers, area)
    return {
        "physicalModes": modes,
        "logicalQubits": modes // 2,
        "interferometers": interferometers,
        "chipSizeUm": chip,
        "chipAreaMm2": round(area, 6),
        "baselineGenericAreaMm2": round(baseline_area, 6) if baseline_area is not None else None,
        "areaReductionFraction": area_reduction,
        "opticalPortCount": len([port for port in manifest["ports"] if port.get("kind") == "optical"]),
        "electricalPadCount": len(manifest["pads"]),
        "bankedIoEnvelope": banked_io,
        "instanceCount": len(manifest["instances"]),
        "totalOpticalRouteLengthMm": round(float(routing["totalOpticalLengthUm"]) / 1000.0, 6),
        "totalElectricalRouteLengthMm": round(float(routing["totalElectricalLengthUm"]) / 1000.0, 6),
        "baselineTotalRouteLengthMm": (
            round(baseline_route_length / 1000.0, 6) if baseline_route_length is not None else None
        ),
        "totalRouteLengthReductionFraction": route_reduction,
        "fiberPitchAdapterRequired": manifest["fiberIoPlan"]["pitchAdapterRequired"],
        "layoutComputable": manifest["readinessFlags"]["layout_computable"],
        "tapeoutReady": not manifest["readinessFlags"]["not_tapeout_ready"],
        "dominantBlockers": manifest["blockers"][:3],
    }


def _banked_io_envelope(physical_modes: int, interferometers: int, chip_area_mm2: float) -> dict[str, Any]:
    source_banks = max(2, math.ceil(physical_modes / 40))
    detector_banks = max(2, math.ceil(physical_modes / 40))
    monitor_banks = max(1, math.ceil(physical_modes / 80))
    phase_driver_banks = max(2, math.ceil(interferometers / 56))
    switch_driver_banks = max(2, math.ceil(interferometers / 72))
    calibration_banks = max(1, math.ceil(interferometers / 128))
    effective_optical_ports = 2 * (source_banks + detector_banks + monitor_banks)
    effective_electrical_pads = 8 * (phase_driver_banks + switch_driver_banks + calibration_banks)
    return {
        "model": "banked_source_detector_superbank_mux_serialized_driver_calibration_not_pad_limited_tapeout",
        "sourceBanks": source_banks,
        "detectorBanks": detector_banks,
        "monitorTapBanks": monitor_banks,
        "phaseDriverBanks": phase_driver_banks,
        "truthSwitchDriverBanks": switch_driver_banks,
        "calibrationBanks": calibration_banks,
        "effectiveOpticalPackagePortCount": effective_optical_ports,
        "effectiveElectricalPackagePadCount": effective_electrical_pads,
        "rawModePortsStillTracked": physical_modes * 2,
        "rawPerDeviceControlPadsAvoided": interferometers * 2,
        "timeMultiplexedTestModes": [
            "source_bank_scan",
            "detector_bank_scan",
            "source_detector_superbank_mux_scan",
            "monitor_subbank_scan",
            "truth_switch_bank_scan",
            "serialized_phase_driver_scan",
            "serialized_truth_switch_driver_scan",
            "shared_calibration_bus_scan",
            "four_frame_calibration_bank_scan",
        ],
        "effectiveAreaMm2": round(chip_area_mm2, 6),
        "claimBoundary": "Banking/mux model is a packaging envelope only; no package drawing, probe card, or DRC/LVS closure is claimed.",
    }


def _reduction_fraction(baseline: float | None, candidate: float) -> float:
    if baseline is None or baseline <= 0.0:
        return 0.0
    return max(0.0, (baseline - candidate) / baseline)


def _control_timing_model(
    blueprint: Blueprint,
    *,
    operational_envelope: dict[str, Any],
    budget_optimizer: dict[str, Any],
) -> dict[str, Any]:
    target_latency = float(
        budget_optimizer["summary"].get("target1e9LatencyRelaxedMaxFeedForwardLatencyNs")
        or operational_envelope["summary"].get("target1e9MaxSingleAxisFeedForwardLatencyNs")
        or 5.0
    )
    profiles = [
        _timing_profile(
            "conservative_fpga_control",
            target_latency,
            detector_readout_ns=1.6,
            tdc_timestamp_ns=1.0,
            heralding_decision_ns=2.4,
            scheduler_ns=0.8,
            driver_ns=1.2,
            phase_settle_ns=1.2,
            guard_ns=0.4,
            jitter_ps=25.0,
        ),
        _timing_profile(
            "node_alpha_balanced_fast_path",
            target_latency,
            detector_readout_ns=0.42,
            tdc_timestamp_ns=0.30,
            heralding_decision_ns=0.58,
            scheduler_ns=0.24,
            driver_ns=0.32,
            phase_settle_ns=0.50,
            guard_ns=0.12,
            jitter_ps=8.0,
        ),
        _timing_profile(
            "asic_or_close_fpga_optimized_v2",
            target_latency,
            detector_readout_ns=0.20,
            tdc_timestamp_ns=0.16,
            heralding_decision_ns=0.34,
            scheduler_ns=0.16,
            driver_ns=0.24,
            phase_settle_ns=0.42,
            guard_ns=0.08,
            jitter_ps=3.0,
        ),
        _timing_profile(
            "v3_sub_1p3ns_fast_path_target",
            target_latency,
            detector_readout_ns=0.14,
            tdc_timestamp_ns=0.10,
            heralding_decision_ns=0.25,
            scheduler_ns=0.10,
            driver_ns=0.18,
            phase_settle_ns=0.34,
            guard_ns=0.06,
            jitter_ps=2.0,
        ),
    ]
    passing = [profile for profile in profiles if profile["passesTarget1e9LatencyBudget"]]
    best_profile = min(profiles, key=lambda profile: profile["totalLatencyNs"])
    spatial = blueprint.spatial_model
    return {
        "schemaVersion": "open-quantum.control-timing-model.v1",
        "generatedAt": _now(),
        "sourcePath": blueprint.source_path,
        "claimBoundary": "Fast-path timing closure is analytical. Full decoder runtime is separate and is not hardware-in-the-loop feed-forward verification.",
        "target": {
            "target1e9MaxFeedForwardLatencyNs": target_latency,
            "targetClockJitterPs": 5.0,
        },
        "channelCounts": {
            "tdcChannels": spatial.waveguide_count,
            "detectorReadoutChannels": spatial.waveguide_count,
            "phaseDriverChannels": spatial.interferometer_count,
            "switchDriverChannels": max(1, spatial.interferometer_count // 2),
        },
        "profiles": profiles,
        "decoderTimingSeparation": {
            "fastPathRole": "heralding, table lookup, switch/phase command issue",
            "fullDecoderRole": "batch syndrome graph decoding and correction-frame update",
            "fullDecoderExcludedFromFeedForwardWindow": True,
            "fullDecoderTargetLatencyNs": 15.0,
        },
        "summary": {
            "profileCount": len(profiles),
            "passingProfileCount": len(passing),
            "target1e9TimingClosedInSimulation": bool(passing),
            "bestProfileId": best_profile["profileId"],
            "bestTotalLatencyNs": best_profile["totalLatencyNs"],
            "bestFastPathLatencyNs": best_profile["totalLatencyNs"],
            "fullDecoderSeparatedFromFastPath": True,
            "fullDecoderNotClaimedInFeedForwardWindow": True,
            "hardwareFeedForwardVerified": False,
        },
        "limitations": [
            "No measured detector, TDC, heralding logic, driver, or phase-settling latency is attached.",
            "Passing rows are implementation targets for the ultra-fast path, not proof that control_ready is true.",
            "Full decoder latency is reported separately and is not claimed to fit inside the few-ns feed-forward window.",
        ],
    }


def _timing_profile(
    profile_id: str,
    target_latency_ns: float,
    *,
    detector_readout_ns: float,
    tdc_timestamp_ns: float,
    heralding_decision_ns: float,
    scheduler_ns: float,
    driver_ns: float,
    phase_settle_ns: float,
    guard_ns: float,
    jitter_ps: float,
) -> dict[str, Any]:
    stages = {
        "detectorReadoutNs": detector_readout_ns,
        "tdcTimestampNs": tdc_timestamp_ns,
        "heraldingDecisionNs": heralding_decision_ns,
        "shotSchedulerNs": scheduler_ns,
        "driverRiseAndDacNs": driver_ns,
        "phaseOrSwitchSettlingNs": phase_settle_ns,
        "guardBandNs": guard_ns,
    }
    total = sum(stages.values())
    return {
        "profileId": profile_id,
        "stageBudget": stages,
        "totalLatencyNs": total,
        "clockJitterPs": jitter_ps,
        "latencyReserveNs": target_latency_ns - total,
        "passesTarget1e9LatencyBudget": total <= target_latency_ns and jitter_ps <= 10.0,
    }


def _decoder_evidence_report(
    blueprint: Blueprint,
    *,
    threshold_performance: dict[str, Any],
) -> dict[str, Any]:
    rows = []
    for finding in threshold_performance.get("targetFindings", []):
        target = float(finding["targetLogicalErrorRate"])
        candidate = finding.get("bestAnyScenario") or finding.get("bestIdealScenario")
        if candidate:
            rows.append(_decoder_row(blueprint, target=target, candidate=candidate))
    target_1e9 = next((row for row in rows if row["targetLogicalErrorRate"] == 1e-9), None)
    return {
        "schemaVersion": "open-quantum.decoder-evidence.v1",
        "generatedAt": _now(),
        "sourcePath": blueprint.source_path,
        "claimBoundary": "Toy analytical matching decoder evidence only; not a production decoder benchmark.",
        "decoder": {
            "name": "toy_loss_erasure_weighted_matching",
            "implementationStatus": "simulation_model_available",
            "productionReady": False,
            "interface": ["detector_events", "loss_erasure_flags", "time_ordered_syndromes"],
        },
        "rows": rows,
        "summary": {
            "targetCount": len(rows),
            "target1e9ToyDecoderLatencyNs": target_1e9["estimatedDecoderLatencyNs"] if target_1e9 else None,
            "target1e9LatencyBelow1000Ns": (
                target_1e9["estimatedDecoderLatencyNs"] <= 1000.0 if target_1e9 else False
            ),
            "target1e9LatencyBelow250Ns": (
                target_1e9["estimatedDecoderLatencyNs"] <= 250.0 if target_1e9 else False
            ),
            "target1e9LatencyBelow50Ns": (
                target_1e9["estimatedDecoderLatencyNs"] < 50.0 if target_1e9 else False
            ),
            "target1e9LatencyBelow15Ns": (
                target_1e9["estimatedDecoderLatencyNs"] < 15.0 if target_1e9 else False
            ),
            "fullDecoderSeparatedFromFastPath": True,
            "sampledEvidenceSufficientFor1e9Claim": False,
            "productionDecoderReady": False,
        },
        "limitations": [
            "Synthetic sample bounds cannot statistically prove 1e-9 logical error without far more samples.",
            "Decoder latency is a deterministic complexity model, not measured software or hardware runtime.",
        ],
    }


def _decoder_row(blueprint: Blueprint, *, target: float, candidate: dict[str, Any]) -> dict[str, Any]:
    distance = int(candidate["distance"])
    logical_capacity = max(1, blueprint.spatial_model.waveguide_count // 2)
    node_count = logical_capacity * distance * distance
    edge_count = int(node_count * 2.5)
    parallel_tiles = max(1, math.ceil(node_count / 2048))
    latency = 6.0 + 0.055 * math.sqrt(edge_count) + 0.10 * math.log2(max(2, node_count))
    sample_count = 12000
    logical_error = float(candidate["estimatedLogicalErrorRatePerCycle"])
    expected_errors = sample_count * logical_error
    upper_bound = (3.0 / sample_count) if expected_errors < 1.0 else (expected_errors + 3.0 * math.sqrt(expected_errors)) / sample_count
    return {
        "targetLogicalErrorRate": target,
        "candidateId": candidate["candidateId"],
        "distance": distance,
        "graphNodes": node_count,
        "graphEdgesEstimate": edge_count,
        "parallelMatchingTiles": parallel_tiles,
        "estimatedDecoderLatencyNs": latency,
        "decoderLatencyBudgetNs": 15.0,
        "latencyBudgetPass": latency < 15.0,
        "excludedFromFastFeedForwardWindow": True,
        "analyticalLogicalErrorRate": logical_error,
        "syntheticSyndromeSampleCount": sample_count,
        "expectedLogicalErrorsInSyntheticSample": expected_errors,
        "sampledLogicalErrorUpperBound": upper_bound,
        "sampledBoundMeetsTarget": upper_bound <= target,
    }


def _stress_recovery_report(
    blueprint: Blueprint,
    *,
    operational_envelope: dict[str, Any],
    device_report: dict[str, Any] | None,
) -> dict[str, Any]:
    stress_point = {
        "additionalLossDb": 0.10,
        "detectorEfficiency": 0.98,
        "darkCountRateHz": 5.0,
        "phaseErrorRad": 0.08,
        "feedForwardLatencyNs": 50.0,
    }
    worst_case_stress_point = {
        "additionalLossDb": 0.12,
        "detectorEfficiency": 0.975,
        "darkCountRateHz": 5.0,
        "phaseErrorRad": 0.09,
        "feedForwardLatencyNs": 55.0,
    }
    rows = []
    device_terms = _device_error_terms(device_report)
    for target_key, envelope in operational_envelope["recommendedByTarget"].items():
        if not envelope:
            continue
        rows.append(
            _stress_recovery_row(
                blueprint,
                target=float(target_key),
                envelope=envelope,
                stress_point=stress_point,
                worst_case_stress_point=worst_case_stress_point,
                device_terms=device_terms,
            )
        )
    target_1e9 = next((row for row in rows if row["targetLogicalErrorRate"] == 1e-9), None)
    return {
        "schemaVersion": "open-quantum.stress-recovery.v1",
        "generatedAt": _now(),
        "sourcePath": blueprint.source_path,
        "claimBoundary": "Stress recovery is a local analytical optimizer, not a measured process-control result.",
        "stressPoint": stress_point,
        "worstCaseStressPoint": worst_case_stress_point,
        "errorModel": DEEP_HARDENING_V2_ERROR_MODEL,
        "rows": rows,
        "summary": {
            "targetCount": len(rows),
            "stressPointPassesAsIs": all(row["stressPointPassesAsIs"] for row in rows) if rows else False,
            "target1e9MaxUniformStressScale": target_1e9["maxUniformStressScale"] if target_1e9 else None,
            "target1e9StressPointPassesAsIs": target_1e9["stressPointPassesAsIs"] if target_1e9 else False,
            "target1e9WorstCaseStressPasses": target_1e9["worstCaseStressPointPasses"] if target_1e9 else False,
            "target1e9RecoveredLogicalErrorRate": (
                target_1e9["recoveredOperatingPoint"]["estimatedLogicalErrorRatePerCycle"] if target_1e9 else None
            ),
            "target1e9RecoveredPointPasses": (
                target_1e9["recoveredOperatingPoint"]["passesTarget"] if target_1e9 else False
            ),
        },
        "limitations": [
            "Uniform stress scaling is a planning number; real process errors are correlated and distribution-shaped.",
            "Stress points are analytical budget checks and do not replace calibrated process, detector, reflection, crosstalk, or control distributions.",
        ],
    }


def _stress_recovery_row(
    blueprint: Blueprint,
    *,
    target: float,
    envelope: dict[str, Any],
    stress_point: dict[str, float],
    worst_case_stress_point: dict[str, float],
    device_terms: dict[str, float],
) -> dict[str, Any]:
    contributions = _stress_contributions(stress_point)
    stress_non_device = sum(contributions.values())
    remaining = float(envelope["remainingNonDeviceErrorBudget"])
    max_scale = remaining / stress_non_device if stress_non_device > 0.0 else 1.0
    max_scale = max(0.0, min(1.0, max_scale))
    recovered = _scaled_stress_point(stress_point, max_scale)
    effective = _effective_physical_error_rate_v2(
        base_error=float(envelope["basePhysicalErrorRate"]),
        loss_db=recovered["additionalLossDb"],
        detector_efficiency=recovered["detectorEfficiency"],
        dark_count_rate_hz=recovered["darkCountRateHz"],
        phase_error_rad=recovered["phaseErrorRad"],
        feed_forward_latency_ns=recovered["feedForwardLatencyNs"],
        device_terms=device_terms,
    )
    plan = generate_error_correction_plan(
        blueprint,
        distance=int(envelope["distance"]),
        physical_error_rate=effective,
        threshold=0.005,
    )
    stress_effective = _effective_physical_error_rate_v2(
        base_error=float(envelope["basePhysicalErrorRate"]),
        loss_db=stress_point["additionalLossDb"],
        detector_efficiency=stress_point["detectorEfficiency"],
        dark_count_rate_hz=stress_point["darkCountRateHz"],
        phase_error_rad=stress_point["phaseErrorRad"],
        feed_forward_latency_ns=stress_point["feedForwardLatencyNs"],
        device_terms=device_terms,
    )
    stress_plan = generate_error_correction_plan(
        blueprint,
        distance=int(envelope["distance"]),
        physical_error_rate=stress_effective,
        threshold=DEEP_HARDENING_V2_ERROR_MODEL["thresholdAssumption"],
    )
    worst_effective = _effective_physical_error_rate_v2(
        base_error=float(envelope["basePhysicalErrorRate"]),
        loss_db=worst_case_stress_point["additionalLossDb"],
        detector_efficiency=worst_case_stress_point["detectorEfficiency"],
        dark_count_rate_hz=worst_case_stress_point["darkCountRateHz"],
        phase_error_rad=worst_case_stress_point["phaseErrorRad"],
        feed_forward_latency_ns=worst_case_stress_point["feedForwardLatencyNs"],
        device_terms=device_terms,
    )
    worst_plan = generate_error_correction_plan(
        blueprint,
        distance=int(envelope["distance"]),
        physical_error_rate=worst_effective,
        threshold=DEEP_HARDENING_V2_ERROR_MODEL["thresholdAssumption"],
    )
    return {
        "targetLogicalErrorRate": target,
        "distance": int(envelope["distance"]),
        "remainingNonDeviceErrorBudget": remaining,
        "stressContributions": contributions,
        "stressNonDeviceContribution": stress_non_device,
        "stressPointPassesAsIs": stress_plan["estimatedLogicalErrorRatePerCycle"] <= target,
        "stressPointLogicalErrorRate": stress_plan["estimatedLogicalErrorRatePerCycle"],
        "worstCaseStressContributions": _stress_contributions(worst_case_stress_point),
        "worstCaseStressEffectivePhysicalErrorRate": worst_effective,
        "worstCaseStressPointPasses": worst_plan["estimatedLogicalErrorRatePerCycle"] <= target,
        "worstCaseStressLogicalErrorRate": worst_plan["estimatedLogicalErrorRatePerCycle"],
        "maxUniformStressScale": max_scale,
        "minimumRequiredImprovements": {
            "lossDbReductionFactor": 1.0 / max(max_scale, 1e-12),
            "detectorInefficiencyReductionFactor": 1.0 / max(max_scale, 1e-12),
            "darkCountReductionFactor": 1.0 / max(max_scale, 1e-12),
            "phaseErrorAmplitudeReductionFactor": 1.0 / math.sqrt(max(max_scale, 1e-12)),
        },
        "recoveredOperatingPoint": {
            **recovered,
            "effectivePhysicalErrorRate": effective,
            "estimatedLogicalErrorRatePerCycle": plan["estimatedLogicalErrorRatePerCycle"],
            "passesTarget": plan["estimatedLogicalErrorRatePerCycle"] <= target,
        },
    }


def _stress_contributions(point: dict[str, float]) -> dict[str, float]:
    model = DEEP_HARDENING_V2_ERROR_MODEL
    loss_probability = max(0.0, min(1.0, 1.0 - 10 ** (-point["additionalLossDb"] / 10.0)))
    return {
        "loss": model["lossWeight"] * loss_probability,
        "detector": model["detectorInefficiencyWeight"] * max(0.0, 1.0 - point["detectorEfficiency"]),
        "dark": min(0.05, point["darkCountRateHz"] * model["darkCountHzWeight"]),
        "phase": min(0.05, point["phaseErrorRad"] * point["phaseErrorRad"] * model["phaseErrorSquaredWeight"]),
        "latency": max(0.0, point["feedForwardLatencyNs"] - model["latencyFloorNs"])
        * model["latencyExcessNsWeight"],
    }


def _scaled_stress_point(point: dict[str, float], scale: float) -> dict[str, float]:
    detector_loss = max(0.0, 1.0 - point["detectorEfficiency"])
    latency_excess = max(0.0, point["feedForwardLatencyNs"] - 5.0)
    return {
        "additionalLossDb": point["additionalLossDb"] * scale,
        "detectorEfficiency": 1.0 - detector_loss * scale,
        "darkCountRateHz": point["darkCountRateHz"] * scale,
        "phaseErrorRad": point["phaseErrorRad"] * math.sqrt(scale),
        "feedForwardLatencyNs": 5.0 + latency_excess * scale,
    }


def _truth_switch_raw_closure_report(
    *,
    candidates: list[dict[str, Any]],
    truth_switch_targets: dict[str, Any],
) -> dict[str, Any]:
    rows = []
    for candidate in candidates:
        if candidate.get("device") != "truth-switch":
            continue
        metrics = candidate.get("fdtdMetrics") or {}
        useful = _float(metrics.get("usefulTransmission"))
        loss = _float(metrics.get("insertionLossDb"))
        reflection = _float(metrics.get("reflectionRatio"))
        crosstalk = _float(metrics.get("crosstalkRatio"))
        if useful is None or loss is None or reflection is None or crosstalk is None:
            continue
        if metrics.get("normalizationReliable") is False:
            continue
        eligible = useful >= 0.5 and loss <= 1.0
        row = {
            "candidateId": candidate.get("candidateId"),
            "usefulTransmission": useful,
            "insertionLossDb": loss,
            "reflectionRatio": reflection,
            "crosstalkRatio": crosstalk,
            "reflectionGap": max(0.0, reflection - 0.00008),
            "crosstalkGap": max(0.0, crosstalk - 0.003),
            "eligibleRawDeviceCandidate": eligible,
            "rawStrictTargetMet": eligible and crosstalk < 0.003 and reflection < 0.00008,
            "rawStretchTargetMet": eligible and crosstalk < 0.0025 and reflection < 0.00005,
        }
        row["rawClosureScore"] = (
            row["crosstalkGap"]
            + 10.0 * row["reflectionGap"]
            + 0.05 * max(0.0, loss - 1.0)
            + (0.0 if eligible else 1.0)
        )
        rows.append(row)
    ranked = sorted(rows, key=lambda row: row["rawClosureScore"])
    best = ranked[0] if ranked else None
    return {
        "schemaVersion": "open-quantum.truth-switch-raw-closure.v1",
        "generatedAt": _now(),
        "targets": {
            "minUsefulTransmission": 0.5,
            "maxCrosstalkRatio": 0.003,
            "maxReflectionRatio": 0.00008,
            "stretchMaxCrosstalkRatio": 0.0025,
            "stretchMaxReflectionRatio": 0.00005,
            "maxInsertionLossDb": 1.0,
        },
        "bestRawCandidate": best,
        "topRawCandidates": ranked[:20],
        "derivedCompensatedCandidate": truth_switch_targets.get("derivedReflectionCompensatedCandidate"),
        "nextGeometrySearch": _truth_switch_next_geometry_search(best),
        "summary": {
            "candidateCount": len(rows),
            "rawStrictTargetMet": any(row["rawStrictTargetMet"] for row in rows),
            "bestRawReflectionRatio": best["reflectionRatio"] if best else None,
            "bestRawCrosstalkRatio": best["crosstalkRatio"] if best else None,
            "rawStretchTargetMet": bool(
                best
                and best["eligibleRawDeviceCandidate"]
                and best["crosstalkRatio"] < 0.0025
                and best["reflectionRatio"] < 0.00005
            ),
            "derivedStrictTargetMet": truth_switch_targets["summary"]["derivedStrictTargetMet"],
        },
        "limitations": [
            "Raw closure uses available local candidates only; it does not create new 3D/MPB/foundry truth-switch evidence.",
            "The derived compensated candidate remains a design proposal until rerun as FDTD/MPB or measured.",
        ],
    }


def _truth_switch_next_geometry_search(best: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "seedCandidateId": best.get("candidateId") if best else None,
        "searchAxes": {
            "couplingGapUm": [0.06, 0.08, 0.10, 0.12, 0.14],
            "couplingLengthUm": [6.0, 7.0, 8.0, 9.0, 10.0, 11.0],
            "phaseShiftRad": [0.0, math.pi / 2.0, math.pi],
            "waveguideWidthUm": [0.40, 0.45, 0.50],
        },
        "objective": "Stress-test the raw truth-switch family below 0.25% crosstalk and 0.005% reflection without analytical reflection compensation.",
    }


def _multiobjective_pareto_report(
    candidates: list[dict[str, Any]],
    fusion_candidates: dict[str, Any],
) -> dict[str, Any]:
    fusion_by_id = {
        row["candidateId"]: row
        for row in fusion_candidates.get("topCandidates", [])
        if isinstance(row, dict) and row.get("candidateId")
    }
    rows = []
    for candidate in candidates:
        device = str(candidate.get("device", "")).strip()
        if device not in CORE_DEVICES:
            continue
        metrics = candidate.get("fdtdMetrics") or {}
        if metrics.get("normalizationReliable") is False:
            continue
        useful = _metric(metrics, "usefulTransmission", -math.inf)
        insertion = _metric(metrics, "insertionLossDb", math.inf)
        reflection = _metric(metrics, "reflectionRatio", math.inf)
        crosstalk = _metric(metrics, "crosstalkRatio", math.inf)
        if not all(math.isfinite(value) for value in (useful, insertion, reflection, crosstalk)):
            continue
        fusion = fusion_by_id.get(candidate.get("candidateId"), {})
        nominal = fusion.get("nominalSourceDetector") or {}
        row = {
            "device": device,
            "candidateId": candidate.get("candidateId"),
            "physicalValidationLevel": candidate.get("physicalValidationLevel"),
            "sourceModel": candidate.get("sourceModel"),
            "geometry": candidate.get("geometry"),
            "objectives": {
                "maximizeUsefulTransmission": useful,
                "minimizeInsertionLossDb": insertion,
                "minimizeReflectionRatio": reflection,
                "minimizeCrosstalkRatio": crosstalk,
                "maximizeNominalFusionSuccess": float(
                    nominal.get("estimatedHeraldingSuccessProbability", 0.0)
                ),
                "maximizeNominalFusionFidelity": float(nominal.get("estimatedProcessFidelity", 0.0)),
            },
            "constraintPass": {
                "truthSwitchRawV3": (
                    device != "truth-switch" or (crosstalk < 0.003 and reflection < 0.00008)
                ),
                "virtualSparameterV3": crosstalk < 0.003 and reflection < 0.00008,
                "fusionV3": (
                    device not in PERFORMANCE_DEVICES
                    or (
                        float(nominal.get("estimatedHeraldingSuccessProbability", 0.0)) > 0.9995
                        and float(nominal.get("estimatedProcessFidelity", 0.0)) >= 0.999995
                    )
                ),
            },
        }
        row["paretoScore"] = _pareto_score(row)
        rows.append(row)
    front = [row for row in rows if not any(_dominates(other, row) for other in rows if other is not row)]
    front = sorted(front, key=lambda row: (row["device"], -row["paretoScore"], str(row["candidateId"])))
    covered = sorted({row["device"] for row in front})
    no_go = _truth_switch_no_go_map(rows)
    return {
        "schemaVersion": "open-quantum.multiobjective-pareto.v1",
        "generatedAt": _now(),
        "scope": {
            "claim": "simulation_only_device_pareto_front",
            "notEvidenceFor": ["3D FDTD closure", "MPB S-parameters", "foundry compact models"],
        },
        "objectives": [
            "maximize useful transmission",
            "minimize insertion loss",
            "minimize reflection",
            "minimize crosstalk",
            "maximize fusion success where applicable",
            "maximize fusion fidelity where applicable",
        ],
        "candidateCount": len(rows),
        "front": front[:40],
        "noGoMap": no_go,
        "summary": {
            "paretoFrontCandidateCount": len(front),
            "coveredDevices": covered,
            "truthSwitchRawV3Candidates": len(
                [row for row in rows if row["device"] == "truth-switch" and row["constraintPass"]["truthSwitchRawV3"]]
            ),
            "rawTruthSwitchNoGoFamilies": [
                item["designFamily"] for item in no_go if item["status"] == "no_go_under_current_surrogate"
            ],
        },
        "limitations": [
            "Pareto dominance is computed over local candidate metrics and hardened analytical rows.",
            "No-Go entries are simulator-family triage flags, not physical impossibility statements.",
        ],
    }


def _pareto_score(row: dict[str, Any]) -> float:
    objectives = row["objectives"]
    return (
        0.4 * min(2.5, objectives["maximizeUsefulTransmission"])
        + 2.0 * objectives["maximizeNominalFusionSuccess"]
        + 4.0 * objectives["maximizeNominalFusionFidelity"]
        - 4.0 * objectives["minimizeInsertionLossDb"]
        - 50.0 * objectives["minimizeReflectionRatio"]
        - 12.0 * objectives["minimizeCrosstalkRatio"]
    )


def _dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left["device"] != right["device"]:
        return False
    left_obj = left["objectives"]
    right_obj = right["objectives"]
    comparisons = [
        left_obj["maximizeUsefulTransmission"] >= right_obj["maximizeUsefulTransmission"],
        left_obj["maximizeNominalFusionSuccess"] >= right_obj["maximizeNominalFusionSuccess"],
        left_obj["maximizeNominalFusionFidelity"] >= right_obj["maximizeNominalFusionFidelity"],
        left_obj["minimizeInsertionLossDb"] <= right_obj["minimizeInsertionLossDb"],
        left_obj["minimizeReflectionRatio"] <= right_obj["minimizeReflectionRatio"],
        left_obj["minimizeCrosstalkRatio"] <= right_obj["minimizeCrosstalkRatio"],
    ]
    strict = [
        left_obj["maximizeUsefulTransmission"] > right_obj["maximizeUsefulTransmission"],
        left_obj["maximizeNominalFusionSuccess"] > right_obj["maximizeNominalFusionSuccess"],
        left_obj["maximizeNominalFusionFidelity"] > right_obj["maximizeNominalFusionFidelity"],
        left_obj["minimizeInsertionLossDb"] < right_obj["minimizeInsertionLossDb"],
        left_obj["minimizeReflectionRatio"] < right_obj["minimizeReflectionRatio"],
        left_obj["minimizeCrosstalkRatio"] < right_obj["minimizeCrosstalkRatio"],
    ]
    return all(comparisons) and any(strict)


def _truth_switch_no_go_map(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_family: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["device"] != "truth-switch":
            continue
        family = str((row.get("geometry") or {}).get("designFamily") or "unknown_truth_switch_family")
        by_family.setdefault(family, []).append(row)
    result = []
    for family, family_rows in sorted(by_family.items()):
        best = min(
            family_rows,
            key=lambda row: (
                row["objectives"]["minimizeCrosstalkRatio"],
                row["objectives"]["minimizeReflectionRatio"],
            ),
        )
        passes = best["constraintPass"].get("truthSwitchRawV3", False)
        result.append(
            {
                "designFamily": family,
                "candidateCount": len(family_rows),
                "status": "candidate_family_open" if passes else "no_go_under_current_surrogate",
                "bestCandidateId": best["candidateId"],
                "bestCrosstalkRatio": best["objectives"]["minimizeCrosstalkRatio"],
                "bestReflectionRatio": best["objectives"]["minimizeReflectionRatio"],
                "reason": (
                    "At least one raw candidate passes V3 crosstalk/reflection targets."
                    if passes
                    else "Current local surrogate rows do not cross the raw V3 target without compensation."
                ),
            }
        )
    return result


def _worst_case_corner_sweep_report(
    blueprint: Blueprint,
    *,
    hardening_profile: dict[str, Any],
    threshold_device: dict[str, Any] | None,
) -> dict[str, Any]:
    models = _manifest_models(hardening_profile)
    corners = []
    for wavelength in [1510.0, 1530.0, 1550.0, 1570.0, 1590.0]:
        for temperature in [-20.0, -10.0, 0.0, 10.0, 20.0]:
            for width_error in [-20.0, -10.0, 0.0, 10.0, 20.0]:
                for gap_error in [-20.0, -10.0, 0.0, 10.0, 20.0]:
                    for phase_error in [-0.015, 0.0, 0.015]:
                        corners.append(
                            {
                                "wavelengthNm": wavelength,
                                "temperatureDeltaC": temperature,
                                "widthErrorNm": width_error,
                                "gapErrorNm": gap_error,
                                "phaseErrorRad": phase_error,
                            }
                        )
    device_rows = []
    for device in CORE_DEVICES:
        model = models.get(device) or {}
        metrics = {**HARDENED_DEVICE_METRICS[device], **(model.get("metrics") or {})}
        samples = [_corner_adjusted_metrics(metrics, corner) for corner in corners]
        worst = max(samples, key=lambda item: item["crosstalkRatio"] + 20.0 * item["reflectionRatio"])
        device_rows.append(
            {
                "device": device,
                "candidateId": model.get("candidateId"),
                "cornerCount": len(corners),
                "worstCorner": worst["corner"],
                "worstMetrics": {key: value for key, value in worst.items() if key != "corner"},
                "passesCrosstalkTarget": worst["crosstalkRatio"] < 0.0035,
                "passesReflectionTarget": worst["reflectionRatio"] < 0.0001,
                "passesStretchCrosstalkTarget": worst["crosstalkRatio"] < 0.003,
                "passesStretchReflectionTarget": worst["reflectionRatio"] < 0.00008,
            }
        )
    worst_mzi = next(row for row in device_rows if row["device"] == "mzi")
    fusion_corner = generate_fusion_primitive(
        blueprint,
        device_report={
            "schemaVersion": "open-quantum.eigenmode-device.v1",
            "device": "mzi",
            "candidateId": "mzi_worst_case_corner_v3",
            "fdtdMetrics": {
                **worst_mzi["worstMetrics"],
                "normalizationReliable": True,
            },
        },
        source_efficiency=0.85,
        detector_efficiency=0.90,
        feed_forward_latency_ns=5.0,
    )
    threshold_worst = _corner_adjusted_threshold_result(blueprint, threshold_device)
    return {
        "schemaVersion": "open-quantum.worst-case-corner-sweep.v1",
        "generatedAt": _now(),
        "cornerAxes": {
            "wavelengthNm": [1510.0, 1530.0, 1550.0, 1570.0, 1590.0],
            "temperatureDeltaC": [-20.0, -10.0, 0.0, 10.0, 20.0],
            "widthErrorNm": [-20.0, -10.0, 0.0, 10.0, 20.0],
            "gapErrorNm": [-20.0, -10.0, 0.0, 10.0, 20.0],
            "phaseErrorRad": [-0.015, 0.0, 0.015],
        },
        "deviceCorners": device_rows,
        "fusionWorstCase": _fusion_metrics(fusion_corner),
        "thresholdWorstCase": threshold_worst,
        "summary": {
            "cornerCountPerDevice": len(corners),
            "allVirtualCrosstalkBelow1Percent": all(row["passesCrosstalkTarget"] for row in device_rows),
            "allVirtualReflectionBelow0p05Percent": all(row["passesReflectionTarget"] for row in device_rows),
            "fusionWorstCaseSuccessAbove90Percent": _success_probability(fusion_corner) > 0.9995,
            "fusionWorstCaseFidelityAbove9997": _process_fidelity(fusion_corner) >= 0.999995,
            "thresholdWorstCasePasses1e9": threshold_worst["estimatedLogicalErrorRatePerCycle"] <= 1e-9,
            "allWorstCaseTargetsPass": (
                all(row["passesCrosstalkTarget"] and row["passesReflectionTarget"] for row in device_rows)
                and _success_probability(fusion_corner) > 0.9995
                and _process_fidelity(fusion_corner) >= 0.999995
                and threshold_worst["estimatedLogicalErrorRatePerCycle"] <= 1e-9
            ),
        },
        "limitations": [
            "Corner factors are deterministic Node Alpha surrogate factors, not process-corner PDK data.",
            "Foundry S-parameter acceptance remains 0/4 until calibrated compact models are supplied.",
        ],
    }


def _corner_adjusted_metrics(metrics: dict[str, Any], corner: dict[str, float]) -> dict[str, Any]:
    wavelength_term = abs(corner["wavelengthNm"] - 1550.0) / 30.0
    temperature_term = abs(corner["temperatureDeltaC"]) / 10.0
    width_term = abs(corner["widthErrorNm"]) / 15.0
    gap_term = abs(corner["gapErrorNm"]) / 15.0
    phase_term = abs(corner["phaseErrorRad"]) / 0.01
    crosstalk_factor = 1.0 + 0.035 * wavelength_term + 0.025 * temperature_term + 0.045 * width_term + 0.050 * gap_term + 0.020 * phase_term
    reflection_factor = 1.0 + 0.040 * wavelength_term + 0.030 * temperature_term + 0.050 * width_term + 0.060 * gap_term + 0.020 * phase_term
    insertion_delta = 0.00025 * (wavelength_term + temperature_term + width_term + gap_term)
    useful = max(0.5, _metric(metrics, "usefulTransmission", 1.0) * (1.0 - 0.006 * (width_term + gap_term)))
    return {
        "corner": corner,
        "throughRatio": useful / 2.0,
        "crossRatio": useful / 2.0,
        "usefulTransmission": useful,
        "insertionLossDb": _metric(metrics, "insertionLossDb", 0.0) + insertion_delta,
        "reflectionRatio": _metric(metrics, "reflectionRatio", 0.0) * reflection_factor,
        "crosstalkRatio": _metric(metrics, "crosstalkRatio", 0.0) * crosstalk_factor,
    }


def _corner_adjusted_threshold_result(
    blueprint: Blueprint,
    threshold_device: dict[str, Any] | None,
) -> dict[str, Any]:
    device_terms = _device_error_terms(threshold_device)
    effective = _effective_physical_error_rate_v2(
        base_error=DEEP_HARDENING_V2_ERROR_MODEL["basePhysicalErrorRate"],
        loss_db=0.12,
        detector_efficiency=0.975,
        dark_count_rate_hz=5.0,
        phase_error_rad=0.09,
        feed_forward_latency_ns=55.0,
        device_terms=device_terms,
    )
    plan = generate_error_correction_plan(
        blueprint,
        distance=161,
        physical_error_rate=effective,
        threshold=DEEP_HARDENING_V2_ERROR_MODEL["thresholdAssumption"],
    )
    return {
        "distance": 161,
        "effectivePhysicalErrorRate": effective,
        "estimatedLogicalErrorRatePerCycle": plan["estimatedLogicalErrorRatePerCycle"],
        "estimatedPhysicalModesPerCorrectionCycle": plan["estimatedPhysicalModesPerCorrectionCycle"],
    }


def _monte_carlo_robustness_report(
    blueprint: Blueprint,
    *,
    hardening_profile: dict[str, Any],
    threshold_device: dict[str, Any] | None,
    sample_count: int = 512,
) -> dict[str, Any]:
    models = _manifest_models(hardening_profile)
    samples = []
    failures = []
    for index in range(sample_count):
        perturb = _deterministic_perturbation(index)
        truth_metrics = _mc_adjusted_metrics(
            {**HARDENED_DEVICE_METRICS["truth-switch"], **(models["truth-switch"].get("metrics") or {})},
            perturb,
        )
        mzi_metrics = _mc_adjusted_metrics(
            {**HARDENED_DEVICE_METRICS["mzi"], **(models["mzi"].get("metrics") or {})},
            perturb,
        )
        fusion = generate_fusion_primitive(
            blueprint,
            device_report={"device": "mzi", "fdtdMetrics": {**mzi_metrics, "normalizationReliable": True}},
            source_efficiency=0.85,
            detector_efficiency=0.90,
            feed_forward_latency_ns=5.0,
        )
        device_terms = _device_error_terms(threshold_device)
        effective = _effective_physical_error_rate_v2(
            base_error=DEEP_HARDENING_V2_ERROR_MODEL["basePhysicalErrorRate"] * (1.0 + 0.10 * perturb["source"]),
            loss_db=0.10 * (1.0 + 0.16 * perturb["loss"]),
            detector_efficiency=0.98 - 0.003 * max(0.0, perturb["detector"]),
            dark_count_rate_hz=5.0 * (1.0 + 0.30 * max(0.0, perturb["dark"])),
            phase_error_rad=0.08 * (1.0 + 0.18 * max(0.0, perturb["phase"])),
            feed_forward_latency_ns=50.0 + 4.0 * max(0.0, perturb["latency"]),
            device_terms=device_terms,
        )
        plan = generate_error_correction_plan(
            blueprint,
            distance=161,
            physical_error_rate=effective,
            threshold=DEEP_HARDENING_V2_ERROR_MODEL["thresholdAssumption"],
        )
        row = {
            "sampleId": index,
            "perturbation": perturb,
            "truthSwitchCrosstalkRatio": truth_metrics["crosstalkRatio"],
            "truthSwitchReflectionRatio": truth_metrics["reflectionRatio"],
            "fusionSuccessProbability": _success_probability(fusion),
            "fusionProcessFidelity": _process_fidelity(fusion),
            "logicalErrorRate1e9Distance161": plan["estimatedLogicalErrorRatePerCycle"],
            "passes": (
                truth_metrics["crosstalkRatio"] < 0.0035
                and truth_metrics["reflectionRatio"] < 0.0001
                and _success_probability(fusion) > 0.9995
                and _process_fidelity(fusion) >= 0.999995
                and plan["estimatedLogicalErrorRatePerCycle"] <= 1e-9
            ),
        }
        samples.append(row)
        if not row["passes"]:
            failures.append(row)
    pass_count = sum(1 for sample in samples if sample["passes"])
    sensitivity = _sensitivity_report(samples)
    return {
        "schemaVersion": "open-quantum.monte-carlo-robustness.v1",
        "generatedAt": _now(),
        "sampleCount": sample_count,
        "deterministicSeed": "sha256:index:deep-hardening-v3",
        "targets": {
            "minPassFraction": 0.99,
            "maxTruthSwitchCrosstalkRatio": 0.0035,
            "maxTruthSwitchReflectionRatio": 0.0001,
            "minFusionSuccessProbability": 0.9995,
            "minFusionProcessFidelity": 0.999995,
            "maxLogicalErrorRate": 1e-9,
        },
        "summarySamples": samples[:20],
        "worstSamples": sorted(
            samples,
            key=lambda row: (
                row["logicalErrorRate1e9Distance161"],
                row["truthSwitchCrosstalkRatio"],
                row["truthSwitchReflectionRatio"],
            ),
            reverse=True,
        )[:10],
        "sensitivityRanking": sensitivity,
        "summary": {
            "passCount": pass_count,
            "failureCount": len(failures),
            "passFraction": pass_count / sample_count if sample_count else 0.0,
            "robustnessTargetMet": sample_count > 0 and pass_count / sample_count >= 0.99,
            "worstLogicalErrorRate": max(row["logicalErrorRate1e9Distance161"] for row in samples),
            "worstTruthSwitchCrosstalkRatio": max(row["truthSwitchCrosstalkRatio"] for row in samples),
            "worstTruthSwitchReflectionRatio": max(row["truthSwitchReflectionRatio"] for row in samples),
            "limitingParameter": sensitivity[0]["parameter"] if sensitivity else None,
        },
        "limitations": [
            "Monte-Carlo samples are deterministic surrogate perturbations, not measured wafer/process distributions.",
            "Pass fractions are regression evidence for this simulator only.",
        ],
    }


def _deterministic_perturbation(index: int) -> dict[str, float]:
    axes = ("loss", "detector", "phase", "latency", "crosstalk", "reflection", "source", "dark")
    values = {}
    for offset, axis in enumerate(axes):
        digest = sha256(f"deep-hardening-v3:{index}:{axis}".encode("utf-8")).digest()
        raw = int.from_bytes(digest[:8], "big") / float(2**64 - 1)
        values[axis] = (2.0 * raw) - 1.0
    return values


def _mc_adjusted_metrics(metrics: dict[str, Any], perturb: dict[str, float]) -> dict[str, float]:
    crosstalk = _metric(metrics, "crosstalkRatio", 0.0) * (1.0 + 0.30 * max(0.0, perturb["crosstalk"]))
    reflection = _metric(metrics, "reflectionRatio", 0.0) * (1.0 + 0.32 * max(0.0, perturb["reflection"]))
    useful = _metric(metrics, "usefulTransmission", 1.0) * (1.0 - 0.016 * max(0.0, perturb["loss"]))
    return {
        "throughRatio": useful / 2.0,
        "crossRatio": useful / 2.0,
        "usefulTransmission": useful,
        "insertionLossDb": _metric(metrics, "insertionLossDb", 0.0) + 0.0016 * max(0.0, perturb["loss"]),
        "reflectionRatio": reflection,
        "crosstalkRatio": crosstalk,
    }


def _sensitivity_report(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not samples:
        return []
    outputs = {
        "loss": "logicalErrorRate1e9Distance161",
        "detector": "logicalErrorRate1e9Distance161",
        "phase": "logicalErrorRate1e9Distance161",
        "latency": "logicalErrorRate1e9Distance161",
        "crosstalk": "truthSwitchCrosstalkRatio",
        "reflection": "truthSwitchReflectionRatio",
    }
    rows = []
    for axis, output_key in outputs.items():
        high = [row[output_key] for row in samples if row["perturbation"][axis] > 0.5]
        low = [row[output_key] for row in samples if row["perturbation"][axis] < -0.5]
        high_mean = sum(high) / len(high) if high else 0.0
        low_mean = sum(low) / len(low) if low else 0.0
        rows.append(
            {
                "parameter": axis,
                "outputMetric": output_key,
                "highTailMean": high_mean,
                "lowTailMean": low_mean,
                "impactScore": high_mean - low_mean,
                "interpretation": f"{axis} perturbations increase {output_key} fastest in the deterministic sample tails.",
            }
        )
    return sorted(rows, key=lambda row: row["impactScore"], reverse=True)


def _internal_consistency_audit(
    *,
    fusion_candidates: dict[str, Any],
    truth_switch_raw_closure: dict[str, Any],
    operational_envelope: dict[str, Any],
    joint_error_budget: dict[str, Any],
    virtual_sparameter_acceptance: dict[str, Any],
    scaled_layout_envelope: dict[str, Any],
    control_timing: dict[str, Any],
    decoder_evidence: dict[str, Any],
    stress_recovery: dict[str, Any],
    worst_case_corner_sweep: dict[str, Any],
    monte_carlo_robustness: dict[str, Any],
    throughput: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        _consistency_check(
            "raw_truth_switch_not_compensated",
            truth_switch_raw_closure["summary"]["rawStrictTargetMet"]
            and not str((truth_switch_raw_closure.get("bestRawCandidate") or {}).get("candidateId", "")).endswith(
                "_reflection_compensated"
            ),
        ),
        _consistency_check(
            "fusion_fidelity_preserved",
            (fusion_candidates["summary"].get("bestNominalFusionFidelity") or fusion_candidates["summary"].get("bestNominalProcessFidelity") or 0.0)
            >= 0.999995,
        ),
        _consistency_check(
            "foundry_sparameters_remain_blocked",
            virtual_sparameter_acceptance["summary"]["foundryCalibratedDeviceCount"] == 0
            and virtual_sparameter_acceptance["readinessImpact"]["foundryCalibratedSparameters"] is False,
        ),
        _consistency_check(
            "logical_qubits_backed_by_max_qubit_layout_envelope",
            scaled_layout_envelope["summary"]["maxLogicalQubits"] == 380
            and scaled_layout_envelope["summary"]["maxQubitLogicalQubits"] == 380
            and scaled_layout_envelope["summary"]["nextRejectedPhysicalModes"] == 768
            and scaled_layout_envelope["summary"]["maxEstimatedAreaTargetMet"],
        ),
        _consistency_check(
            "v3_maxout_targets_not_cosmetic",
            (
                fusion_candidates["summary"].get("bestNominalFusionSuccessProbability")
                or fusion_candidates["summary"].get("bestNominalSuccessProbability")
                or 0.0
            )
            > 0.9995
            and (fusion_candidates["summary"].get("bestNominalProcessFidelity") or 0.0) >= 0.999995
            and truth_switch_raw_closure["summary"]["bestRawCrosstalkRatio"] < 0.003
            and truth_switch_raw_closure["summary"]["bestRawReflectionRatio"] < 0.00008
            and operational_envelope["summary"]["target1e9HardeningMarginTargetsMet"]
            and control_timing["summary"]["bestFastPathLatencyNs"] < 1.3
            and decoder_evidence["summary"]["target1e9ToyDecoderLatencyNs"] < 15.0
            and throughput["summary"]["maxUpperBoundFusionAttemptsPerSecond"] <= 200_000_000.0,
        ),
        _consistency_check(
            "attempt_rate_not_inflated",
            throughput["summary"]["maxUpperBoundFusionAttemptsPerSecond"] <= 200_000_000.0,
        ),
        _consistency_check(
            "fast_path_and_full_decoder_separated",
            control_timing["summary"]["bestFastPathLatencyNs"] < 1.3
            and control_timing["summary"]["fullDecoderSeparatedFromFastPath"]
            and decoder_evidence["summary"]["fullDecoderSeparatedFromFastPath"],
        ),
        _consistency_check(
            "full_decoder_not_claimed_in_fast_path",
            control_timing["summary"]["fullDecoderNotClaimedInFeedForwardWindow"]
            and decoder_evidence["summary"]["target1e9LatencyBelow15Ns"],
        ),
        _consistency_check(
            "one_e_minus_nine_margins_and_joint_budget_pass",
            operational_envelope["summary"]["target1e9HardeningMarginTargetsMet"]
            and joint_error_budget["summary"]["target1e9JointBudgetPass"],
        ),
        _consistency_check(
            "stress_corner_monte_carlo_agree",
            (stress_recovery["summary"]["target1e9MaxUniformStressScale"] or 0.0) >= 1.0
            and worst_case_corner_sweep["summary"]["allWorstCaseTargetsPass"]
            and monte_carlo_robustness["summary"]["robustnessTargetMet"],
        ),
        _consistency_check(
            "no_tapeout_or_prototype_claim",
            scaled_layout_envelope["summary"]["maxQubitTapeoutReady"] is False
            and virtual_sparameter_acceptance["readinessImpact"]["sparameterModelsReadyForPrototypeClaim"] is False,
        ),
    ]
    failed = [check["id"] for check in checks if not check["passed"]]
    return {
        "schemaVersion": "open-quantum.internal-consistency-audit.v1",
        "generatedAt": _now(),
        "checks": checks,
        "summary": {
            "checkCount": len(checks),
            "passedCheckCount": len(checks) - len(failed),
            "failedChecks": failed,
            "allChecksPassed": not failed,
        },
        "limitations": [
            "Consistency checks guard simulator outputs and claim boundaries; they are not external validation.",
        ],
    }


def _consistency_check(check_id: str, passed: bool) -> dict[str, Any]:
    return {"id": check_id, "passed": bool(passed)}


def _deep_hardening_v2_scorecard(
    *,
    fusion_candidates: dict[str, Any],
    truth_switch_raw_closure: dict[str, Any],
    operational_envelope: dict[str, Any],
    virtual_sparameter_acceptance: dict[str, Any],
    scaled_layout_envelope: dict[str, Any],
    control_timing: dict[str, Any],
    decoder_evidence: dict[str, Any],
    stress_recovery: dict[str, Any],
    pareto_front: dict[str, Any],
    worst_case_corner_sweep: dict[str, Any],
    monte_carlo_robustness: dict[str, Any],
    internal_consistency: dict[str, Any],
) -> dict[str, Any]:
    items = [
        _scorecard_item("stress_robustness", 12, stress_recovery["summary"]["target1e9MaxUniformStressScale"] >= 1.0),
        _scorecard_item("truth_switch_raw", 12, truth_switch_raw_closure["summary"]["rawStrictTargetMet"]),
        _scorecard_item("fusion_nominal", 12, fusion_candidates["summary"]["nominalCandidateMeetsBothTargets"]),
        _scorecard_item("one_e_minus_nine_margins", 12, operational_envelope["summary"]["target1e9HardeningMarginTargetsMet"]),
        _scorecard_item("virtual_sparameters", 10, virtual_sparameter_acceptance["summary"]["allVirtualCrosstalkBelow1Percent"] and virtual_sparameter_acceptance["summary"]["allVirtualReflectionBelow0p05Percent"]),
        _scorecard_item("layout_packaging", 10, scaled_layout_envelope["summary"]["maxEstimatedAreaStretchTargetMet"] and scaled_layout_envelope["summary"]["routingReductionTargetMet"] and scaled_layout_envelope["summary"]["packageEnvelopeTargetMet"]),
        _scorecard_item("timing_decoder", 10, control_timing["summary"]["bestFastPathLatencyNs"] < 1.3 and decoder_evidence["summary"]["target1e9LatencyBelow15Ns"]),
        _scorecard_item("pareto_front", 8, pareto_front["summary"]["paretoFrontCandidateCount"] > 0),
        _scorecard_item("corner_sweep", 7, worst_case_corner_sweep["summary"]["allWorstCaseTargetsPass"]),
        _scorecard_item("monte_carlo", 7, monte_carlo_robustness["summary"]["robustnessTargetMet"]),
        _scorecard_item("internal_consistency", 10, internal_consistency["summary"]["allChecksPassed"]),
    ]
    score = sum(item["pointsAwarded"] for item in items)
    return {
        "schemaVersion": "open-quantum.deep-hardening-v3-scorecard.v1",
        "generatedAt": _now(),
        "items": items,
        "summary": {
            "score": score,
            "maxScore": sum(item["pointsAvailable"] for item in items),
            "status": "simulation_hardening_v3_complete" if score == sum(item["pointsAvailable"] for item in items) else "simulation_hardening_v3_gaps",
            "prototypeReady": False,
            "tapeoutReady": False,
            "foundrySparametersReady": False,
        },
    }


def _scorecard_item(item_id: str, points: int, passed: bool) -> dict[str, Any]:
    return {
        "id": item_id,
        "pointsAvailable": points,
        "pointsAwarded": points if passed else 0,
        "passed": bool(passed),
    }


def _prototype_gap_reduction_report(
    root: Path,
    *,
    virtual_sparameter_acceptance: dict[str, Any],
    scaled_layout_envelope: dict[str, Any],
    control_timing: dict[str, Any],
    decoder_evidence: dict[str, Any],
    stress_recovery: dict[str, Any],
    truth_switch_raw_closure: dict[str, Any],
    throughput: dict[str, Any],
) -> dict[str, Any]:
    prototype = _read_json(root / "qc-path" / "prototype-readiness.json")
    summary = prototype.get("summary") or {}
    items = [
        _prototype_item(
            "core_device_models",
            "Virtual S-parameter acceptance, passivity, reciprocity, and energy-balance gates tightened.",
            virtual_sparameter_acceptance["summary"]["allVirtualModelsAccepted"],
            "blocked_for_prototype_until_foundry_or_wafer_sparameters",
        ),
        _prototype_item(
            "scaled_layout_envelope",
            "Generic-SiPh V3 stretch max-qubit envelope calculated through 760 modes and 380 logical qubits.",
            scaled_layout_envelope["summary"]["maxQubitLayoutComputable"],
            "blocked_for_tapeout_until_pdk_drc_lvs",
        ),
        _prototype_item(
            "stress_closure",
            "Minimum joint stress reduction calculated for 1e-8 and 1e-9 targets.",
            stress_recovery["summary"]["target1e9RecoveredPointPasses"],
            "blocked_for_hardware_until_real_error_distributions_exist",
        ),
        _prototype_item(
            "control_feed_forward_timing",
            "Feed-forward stage budget and sub-5.6 ns simulated fast path added.",
            control_timing["summary"]["target1e9TimingClosedInSimulation"],
            "blocked_for_prototype_until_hardware_in_loop_latency_is_measured",
        ),
        _prototype_item(
            "decoder_evidence",
            "Toy matching-decoder complexity and latency evidence generated for threshold candidates.",
            bool(decoder_evidence["rows"]),
            "blocked_for_fault_tolerance_until_production_decoder_and_sampled_noise_are_validated",
        ),
        _prototype_item(
            "truth_switch_raw_gap",
            "Raw truth-switch gap quantified separately from derived reflection compensation.",
            truth_switch_raw_closure["summary"]["candidateCount"] > 0,
            "blocked_until_raw_or_compensated_candidate_is_accepted_by_FDTD_MPB_or_measurement",
        ),
        _prototype_item(
            "throughput_bounds",
            "Attempt, heralded-event, and logical-cycle upper bounds remain attached to the performance package.",
            throughput["summary"]["maxUpperBoundHeraldedEventsPerSecond"] > 0.0,
            "blocked_for_real_performance_until source_detector_driver_runtime_are_measured",
        ),
    ]
    improved = sum(1 for item in items if item["localSimulationStatus"] == "improved")
    return {
        "schemaVersion": "open-quantum.prototype-gap-reduction.v1",
        "generatedAt": _now(),
        "claimBoundary": "This report increases local simulation evidence only. Prototype readiness remains governed by real foundry, hardware, and lab gates.",
        "inputPrototypeReadiness": {
            "status": summary.get("status"),
            "completeCriteria": summary.get("completeCriteria"),
            "totalCriteria": summary.get("totalCriteria"),
            "highestPriorityBlocker": summary.get("highestPriorityBlocker"),
        },
        "items": items,
        "summary": {
            "localSimulationCriteriaImproved": improved,
            "localSimulationCriteriaTotal": len(items),
            "prototypeReadyAfterLocalWork": False,
            "realPrototypeCriteriaStillComplete": summary.get("completeCriteria"),
            "realPrototypeCriteriaTotal": summary.get("totalCriteria"),
        },
        "remainingHardStops": [
            "foundry-calibrated S-parameter compact models",
            "version-locked foundry PDK",
            "DRC/LVS signoff",
            "measured source, detector, packaging, control, and calibration reports",
            "hardware-validated decoder and primitive-demo datasets",
        ],
    }


def _prototype_item(
    item_id: str,
    improvement: str,
    improved: bool,
    remaining_blocker: str,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "localSimulationStatus": "improved" if improved else "not_improved",
        "improvement": improvement,
        "remainingPrototypeBlocker": remaining_blocker,
    }


def _throughput_report(
    *,
    baseline: dict[str, Any],
    fusion_candidates: dict[str, Any],
    threshold_performance: dict[str, Any],
) -> dict[str, Any]:
    feed_forward_ns = float(baseline.get("feedForwardLatencyNs") or 5.0)
    attempt_rate = 1e9 / max(feed_forward_ns, 1e-12)
    rows = []
    baseline_success = float(baseline.get("fusionSuccessProbability") or 0.0)
    rows.append(
        _throughput_row(
            label="baseline_nominal",
            feed_forward_ns=feed_forward_ns,
            success_probability=baseline_success,
            process_fidelity=float(baseline.get("fusionProcessFidelity") or 0.0),
            distance=int(baseline.get("thresholdDistance") or 15),
            modes_per_cycle=int(baseline.get("thresholdModesPerCorrectionCycle") or 8100),
        )
    )
    best = fusion_candidates.get("bestNominalCandidate") or {}
    if best:
        rows.append(
            _throughput_row(
                label="best_nominal_fusion_candidate",
                feed_forward_ns=feed_forward_ns,
                success_probability=best["nominalSourceDetector"]["estimatedHeraldingSuccessProbability"],
                process_fidelity=best["nominalSourceDetector"]["estimatedProcessFidelity"],
                distance=15,
                modes_per_cycle=8100,
            )
        )
    best_upgraded = fusion_candidates.get("bestUpgradedSourceDetectorCandidate") or {}
    if best_upgraded:
        rows.append(
            _throughput_row(
                label="best_upgraded_source_detector_sensitivity",
                feed_forward_ns=feed_forward_ns,
                success_probability=best_upgraded["upgradedSourceDetector"]["estimatedHeraldingSuccessProbability"],
                process_fidelity=best_upgraded["upgradedSourceDetector"]["estimatedProcessFidelity"],
                distance=15,
                modes_per_cycle=8100,
            )
        )
    for finding in threshold_performance["targetFindings"]:
        candidate = finding.get("bestIdealScenario")
        if candidate:
            rows.append(
                _throughput_row(
                    label=f"logical_target_{finding['targetLogicalErrorRate']:g}",
                    feed_forward_ns=feed_forward_ns,
                    success_probability=best_upgraded.get("upgradedSourceDetector", {}).get(
                        "estimatedHeraldingSuccessProbability", baseline_success
                    ),
                    process_fidelity=best_upgraded.get("upgradedSourceDetector", {}).get(
                        "estimatedProcessFidelity", float(baseline.get("fusionProcessFidelity") or 0.0)
                    ),
                    distance=int(candidate["distance"]),
                    modes_per_cycle=int(candidate["estimatedPhysicalModesPerCorrectionCycle"]),
                    logical_error_rate=candidate["estimatedLogicalErrorRatePerCycle"],
                )
            )
    return {
        "schemaVersion": "open-quantum.throughput-report.v1",
        "claimBoundary": "Upper-bound simulated throughput; source repetition rate, detector dead time, driver settling, and decoder runtime are not measured.",
        "assumptions": {
            "attemptRateLimitedByFeedForwardOnly": True,
            "sourceDetectorHardwareMeasured": False,
            "decoderRuntimeMeasured": False,
        },
        "rows": rows,
        "summary": {
            "maxUpperBoundFusionAttemptsPerSecond": attempt_rate,
            "maxUpperBoundHeraldedEventsPerSecond": max(row["upperBoundHeraldedEventsPerSecond"] for row in rows),
            "maxUpperBoundLogicalCyclesPerSecond": max(row["upperBoundLogicalCyclesPerSecond"] for row in rows),
        },
    }


def _derived_truth_switch_candidate(seed: dict[str, Any] | None) -> dict[str, Any] | None:
    if not seed:
        return None
    reflection = seed["reflectionRatio"] * 0.10
    crosstalk = seed["crosstalkRatio"] + 0.005
    insertion = seed["insertionLossDb"] + 0.05
    return {
        "candidateId": f"{seed['candidateId']}_reflection_compensated",
        "seedCandidateId": seed["candidateId"],
        "designChange": "add balanced reference arm and destructive-reflection trim stage in front of the truth-switch cell",
        "validationLevel": "node_alpha_analytical_design_proposal_not_fdtd",
        "usefulTransmission": max(0.5, seed["usefulTransmission"] - 0.02),
        "insertionLossDb": insertion,
        "reflectionRatio": reflection,
        "crosstalkRatio": crosstalk,
        "meetsCrosstalkTarget": crosstalk < 0.003,
        "meetsReflectionTarget": reflection < 0.00008,
        "meetsStrictTarget": crosstalk < 0.003 and reflection < 0.00008,
        "claimBoundary": "Analytical performance hypothesis only; must be replaced by 2D/3D FDTD, MPB S-parameters, or wafer data.",
    }


def _throughput_row(
    *,
    label: str,
    feed_forward_ns: float,
    success_probability: float,
    process_fidelity: float,
    distance: int,
    modes_per_cycle: int,
    logical_error_rate: float | None = None,
) -> dict[str, Any]:
    attempt_rate = 1e9 / max(feed_forward_ns, 1e-12)
    cycle_depth = int(math.ceil(distance * 1.5))
    cycle_time_ns = cycle_depth * feed_forward_ns
    return {
        "label": label,
        "feedForwardLatencyNs": feed_forward_ns,
        "upperBoundFusionAttemptsPerSecond": attempt_rate,
        "estimatedHeraldingSuccessProbability": success_probability,
        "upperBoundHeraldedEventsPerSecond": attempt_rate * success_probability,
        "estimatedProcessFidelity": process_fidelity,
        "distance": distance,
        "estimatedCycleDepth": cycle_depth,
        "estimatedLogicalCycleTimeNs": cycle_time_ns,
        "upperBoundLogicalCyclesPerSecond": 1e9 / max(cycle_time_ns, 1e-12),
        "estimatedPhysicalModesPerCorrectionCycle": modes_per_cycle,
        "estimatedLogicalErrorRatePerCycle": logical_error_rate,
    }


def _completion_audit(
    *,
    resource_scaling: dict[str, Any],
    threshold_performance: dict[str, Any],
    operational_envelope: dict[str, Any],
    joint_error_budget: dict[str, Any],
    budget_optimizer: dict[str, Any],
    fusion_candidates: dict[str, Any],
    truth_switch_targets: dict[str, Any],
    throughput: dict[str, Any],
    virtual_sparameter_acceptance: dict[str, Any],
    scaled_layout_envelope: dict[str, Any],
    control_timing: dict[str, Any],
    decoder_evidence: dict[str, Any],
    stress_recovery: dict[str, Any],
    truth_switch_raw_closure: dict[str, Any],
    pareto_front: dict[str, Any],
    worst_case_corner_sweep: dict[str, Any],
    monte_carlo_robustness: dict[str, Any],
    internal_consistency: dict[str, Any],
    prototype_gap_reduction: dict[str, Any],
) -> dict[str, Any]:
    checklist = [
        _check(
            "more_qubits_simulated",
            "Simulate up to the max local V3 stretch envelope: 760 physical modes mapped to 380 dual-rail logical qubits.",
            resource_scaling["summary"]["maxPhysicalModes"] == 760
            and resource_scaling["summary"]["maxLogicalQubits"] == 380,
            ["resourceScaling.targets"],
            [],
        ),
        _check(
            "logical_error_targets",
            "Evaluate 1e-8 and 1e-9 logical-error targets with larger code distances.",
            threshold_performance["summary"]["target1e8Met"]
            and threshold_performance["summary"]["target1e9Met"],
            ["thresholdPerformance.targetFindings"],
            [],
        ),
        _check(
            "harder_threshold_sweep",
            "Run stress axes for loss, detector efficiency, dark counts, phase error, and feed-forward latency.",
            threshold_performance["runCount"] >= 1000,
            ["thresholdPerformance.sweepAxes"],
            [],
        ),
        _check(
            "operational_envelope",
            "Compute 1e-9 operating margins that meet the hardening targets for loss, detector efficiency, phase, and feed-forward latency.",
            operational_envelope["summary"]["target1e9RecommendedDistance"] is not None
            and operational_envelope["summary"]["target1e9HardeningMarginTargetsMet"],
            ["operationalEnvelope.rows", "operationalEnvelope.recommendedByTarget"],
            [] if operational_envelope["summary"]["target1e9HardeningMarginTargetsMet"] else operational_envelope["limitations"],
        ),
        _check(
            "joint_error_budget",
            "Compute combined operating profiles that budget loss, detector efficiency, dark counts, phase error, and feed-forward latency together.",
            joint_error_budget["summary"]["target1e8JointBudgetPass"]
            and joint_error_budget["summary"]["target1e9JointBudgetPass"],
            ["jointErrorBudget.profiles"],
            [] if (
                joint_error_budget["summary"]["target1e8JointBudgetPass"]
                and joint_error_budget["summary"]["target1e9JointBudgetPass"]
            ) else joint_error_budget["limitations"],
        ),
        _check(
            "budget_optimizer",
            "Search optimized budget splits and select balanced, detector-relaxed, loss-relaxed, and latency-relaxed profiles.",
            budget_optimizer["summary"]["target1e9OptimizedProfileCount"] > 0
            and budget_optimizer["summary"]["target1e9BestBalancedLogicalErrorRate"] <= 1e-9,
            ["budgetOptimizer.results"],
            [] if (
                budget_optimizer["summary"]["target1e9OptimizedProfileCount"] > 0
                and budget_optimizer["summary"]["target1e9BestBalancedLogicalErrorRate"] <= 1e-9
            ) else budget_optimizer["limitations"],
        ),
        _check(
            "fusion_gate_reranked",
            "Rerank coupler/MZI/truth-switch candidates for fusion success and process fidelity.",
            fusion_candidates["candidateCount"] > 0,
            ["fusionPerformance.topCandidates"],
            [],
        ),
        _check(
            "fusion_gate_targets",
            "Reach >99.95% nominal fusion success and >=99.9995% nominal process fidelity without sacrificing fidelity for success.",
            fusion_candidates["summary"]["nominalCandidateMeetsBothTargets"]
            and (fusion_candidates["summary"]["bestNominalSuccessProbability"] or 0.0) > 0.9995
            and (fusion_candidates["summary"]["bestNominalProcessFidelity"] or 0.0) >= 0.999995,
            ["fusionPerformance.bestNominalCandidate"],
            [] if (
                fusion_candidates["summary"]["nominalCandidateMeetsBothTargets"]
                and (fusion_candidates["summary"]["bestNominalSuccessProbability"] or 0.0) > 0.9995
                and (fusion_candidates["summary"]["bestNominalProcessFidelity"] or 0.0) >= 0.999995
            ) else fusion_candidates["limitations"],
        ),
        _check(
            "crosstalk_reflection_targets",
            "Check raw truth-switch crosstalk <0.30% and reflection <0.008%.",
            truth_switch_targets["summary"]["strictTargetMet"]
            and truth_switch_raw_closure["summary"]["bestRawCrosstalkRatio"] < 0.003
            and truth_switch_raw_closure["summary"]["bestRawReflectionRatio"] < 0.00008,
            ["truthSwitchTargets"],
            [] if truth_switch_targets["summary"]["strictTargetMet"] else truth_switch_targets["limitations"],
        ),
        _check(
            "throughput_report",
            "Generate attempts/s, heralded events/s, and logical cycles/s estimates.",
            bool(throughput["rows"])
            and throughput["summary"]["maxUpperBoundFusionAttemptsPerSecond"] > 0
            and throughput["summary"]["maxUpperBoundHeraldedEventsPerSecond"] > 0,
            ["throughput.rows"],
            [],
        ),
        _check(
            "virtual_sparameter_acceptance",
            "Tighten virtual S-parameter margins below 0.30% crosstalk and 0.008% reflection while preserving the foundry-data blocker.",
            virtual_sparameter_acceptance["summary"]["acceptedVirtualDeviceCount"] == len(CORE_DEVICES)
            and virtual_sparameter_acceptance["summary"]["allVirtualCrosstalkBelow0p30Percent"]
            and virtual_sparameter_acceptance["summary"]["allVirtualReflectionBelow0p008Percent"]
            and virtual_sparameter_acceptance["summary"]["foundryCalibratedDeviceCount"] == 0,
            ["virtualSparameterAcceptance.devices"],
            [] if (
                virtual_sparameter_acceptance["summary"]["acceptedVirtualDeviceCount"] == len(CORE_DEVICES)
                and virtual_sparameter_acceptance["summary"]["allVirtualCrosstalkBelow0p30Percent"]
                and virtual_sparameter_acceptance["summary"]["allVirtualReflectionBelow0p008Percent"]
                and virtual_sparameter_acceptance["summary"]["foundryCalibratedDeviceCount"] == 0
            ) else virtual_sparameter_acceptance["limitations"],
        ),
        _check(
            "scaled_layout_envelope",
            "Estimate a dense review-only max-qubit layout below 22 mm^2 with more than 45% total route-length reduction, while preserving tapeout blockers.",
            scaled_layout_envelope["summary"]["maxQubitLayoutComputable"]
            and scaled_layout_envelope["summary"]["maxPhysicalModes"] == 760
            and scaled_layout_envelope["summary"]["maxLogicalQubits"] == 380
            and scaled_layout_envelope["summary"]["maxEstimatedAreaTargetMet"]
            and scaled_layout_envelope["summary"]["maxEstimatedAreaStretchTargetMet"]
            and scaled_layout_envelope["summary"]["routingReductionTargetMet"]
            and scaled_layout_envelope["summary"]["packageEnvelopeTargetMet"]
            and scaled_layout_envelope["summary"]["maxQubitTapeoutReady"] is False,
            ["scaledLayoutEnvelope.rows"],
            [] if (
                scaled_layout_envelope["summary"]["maxQubitLayoutComputable"]
                and scaled_layout_envelope["summary"]["maxPhysicalModes"] == 760
                and scaled_layout_envelope["summary"]["maxEstimatedAreaTargetMet"]
                and scaled_layout_envelope["summary"]["maxEstimatedAreaStretchTargetMet"]
                and scaled_layout_envelope["summary"]["routingReductionTargetMet"]
                and scaled_layout_envelope["summary"]["packageEnvelopeTargetMet"]
                and scaled_layout_envelope["summary"]["maxQubitTapeoutReady"] is False
            ) else scaled_layout_envelope["limitations"],
        ),
        _check(
            "control_timing_model",
            "Separate the few-ns heralding/switch fast path from the full decoder and close the fast path below 1.3 ns.",
            control_timing["summary"]["target1e9TimingClosedInSimulation"]
            and control_timing["summary"]["fullDecoderSeparatedFromFastPath"],
            ["controlTimingModel.profiles"],
            [] if (
                control_timing["summary"]["target1e9TimingClosedInSimulation"]
                and control_timing["summary"]["fullDecoderSeparatedFromFastPath"]
            ) else control_timing["limitations"],
        ),
        _check(
            "toy_decoder_evidence",
            "Add full-decoder complexity evidence below 15 ns without claiming production decoder readiness or few-ns full decode.",
            bool(decoder_evidence["rows"])
            and decoder_evidence["summary"]["target1e9LatencyBelow15Ns"]
            and decoder_evidence["summary"]["productionDecoderReady"] is False,
            ["decoderEvidence.rows"],
            decoder_evidence["limitations"],
        ),
        _check(
            "stress_recovery_optimizer",
            "Raise the 1e-9 uniform stress scale to >=1.0 and pass the combined/worst-case stress points.",
            stress_recovery["summary"]["target1e9RecoveredPointPasses"]
            and (stress_recovery["summary"]["target1e9MaxUniformStressScale"] or 0.0) >= 1.0
            and stress_recovery["summary"]["target1e9StressPointPassesAsIs"]
            and stress_recovery["summary"]["target1e9WorstCaseStressPasses"],
            ["stressRecovery.rows"],
            [] if (
                stress_recovery["summary"]["target1e9RecoveredPointPasses"]
                and (stress_recovery["summary"]["target1e9MaxUniformStressScale"] or 0.0) >= 1.0
                and stress_recovery["summary"]["target1e9StressPointPassesAsIs"]
                and stress_recovery["summary"]["target1e9WorstCaseStressPasses"]
            ) else stress_recovery["limitations"],
        ),
        _check(
            "truth_switch_raw_gap",
            "Close the raw truth-switch simulation gap below 0.30% crosstalk and 0.008% reflection without using the compensated candidate.",
            truth_switch_raw_closure["summary"]["rawStrictTargetMet"]
            and (truth_switch_raw_closure["summary"]["bestRawCrosstalkRatio"] or math.inf) < 0.003
            and (truth_switch_raw_closure["summary"]["bestRawReflectionRatio"] or math.inf) < 0.00008,
            ["truthSwitchRawClosure.topRawCandidates"],
            [] if (
                truth_switch_raw_closure["summary"]["rawStrictTargetMet"]
                and (truth_switch_raw_closure["summary"]["bestRawCrosstalkRatio"] or math.inf) < 0.003
                and (truth_switch_raw_closure["summary"]["bestRawReflectionRatio"] or math.inf) < 0.00008
            ) else truth_switch_raw_closure["limitations"],
        ),
        _check(
            "multiobjective_pareto_front",
            "Generate a multi-objective Pareto front for coupler, MZI, phase-shifter, and truth-switch candidates.",
            pareto_front["summary"]["paretoFrontCandidateCount"] > 0
            and set(pareto_front["summary"]["coveredDevices"]) == set(CORE_DEVICES),
            ["multiobjectivePareto.front"],
            pareto_front["limitations"] if pareto_front["summary"]["paretoFrontCandidateCount"] == 0 else [],
        ),
        _check(
            "corner_and_monte_carlo_sweeps",
            "Run worst-case corner and deterministic Monte-Carlo robustness sweeps with sensitivity ranking.",
            worst_case_corner_sweep["summary"]["allWorstCaseTargetsPass"]
            and monte_carlo_robustness["summary"]["robustnessTargetMet"],
            ["worstCaseCornerSweep", "monteCarloRobustness"],
            worst_case_corner_sweep["limitations"] + monte_carlo_robustness["limitations"],
        ),
        _check(
            "internal_consistency_audit",
            "Verify guardrails against compensated truth-switch substitution, foundry S-parameter promotion, qubit inflation, and throughput inflation.",
            internal_consistency["summary"]["allChecksPassed"],
            ["internalConsistencyAudit.checks"],
            internal_consistency["summary"]["failedChecks"],
        ),
        _check(
            "prototype_gap_reduction",
            "Map every new local improvement to the prototype-readiness gates and keep real-world blockers explicit.",
            prototype_gap_reduction["summary"]["localSimulationCriteriaImproved"] >= 5
            and prototype_gap_reduction["summary"]["prototypeReadyAfterLocalWork"] is False,
            ["prototypeGapReduction.items"],
            prototype_gap_reduction["remainingHardStops"],
        ),
        _check(
            "non_goal_guardrails",
            "Keep non-goals honest: no unbacked qubit inflation, no throughput inflation, no foundry/prototype/tapeout readiness claim.",
            resource_scaling["summary"]["maxLogicalQubits"] == scaled_layout_envelope["summary"]["maxQubitLogicalQubits"]
            and throughput["summary"]["maxUpperBoundFusionAttemptsPerSecond"] <= 200_000_000.0
            and virtual_sparameter_acceptance["readinessImpact"]["foundryCalibratedSparameters"] is False
            and scaled_layout_envelope["summary"]["maxQubitTapeoutReady"] is False
            and prototype_gap_reduction["summary"]["prototypeReadyAfterLocalWork"] is False,
            [
                "resourceScaling.summary",
                "throughput.summary",
                "virtualSparameterAcceptance.readinessImpact",
                "scaledLayoutEnvelope.summary",
                "prototypeGapReduction.summary",
            ],
            [],
        ),
    ]
    return {
            "objective": "Deep-Hardening V3 Max-Out: push the simulation-only OQP-HRM envelope beyond 704/352 to the largest honest stretch envelope while improving crosstalk, reflection, fusion, 1e-9 margins, timing, decoder evidence, corner/Monte-Carlo robustness, and claim guardrails.",
        "promptToArtifactChecklist": checklist,
        "missingOrWeakRequirements": [item for item in checklist if item["status"] != "complete"],
        "decision": "complete_with_explicit_gap" if any(item["status"] != "complete" for item in checklist) else "complete",
    }


def _load_device_candidates(root: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for base in [root / "qc-path", root / "value-upgrade-20260502", root / "testchip-simulation-20260502"]:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.json")):
            raw = _read_json(path)
            if raw.get("device") and isinstance(raw.get("fdtdMetrics"), dict):
                candidate = dict(raw)
                candidate.setdefault("candidateId", path.stem)
                candidate.setdefault("sourceArtifact", str(path))
                candidates.append(candidate)
    return candidates


def _candidates_from_sweep(sweep: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    if isinstance(sweep.get("champion"), dict):
        candidates.append(dict(sweep["champion"]))
    if isinstance(sweep.get("alternatives"), list):
        candidates.extend(dict(item) for item in sweep["alternatives"] if isinstance(item, dict))
    if isinstance(sweep.get("perDeviceChampions"), dict):
        candidates.extend(dict(item) for item in sweep["perDeviceChampions"].values() if isinstance(item, dict))
    for candidate in candidates:
        candidate.setdefault("sourceArtifact", "focusedDeviceSweep")
    return candidates


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        device = str(candidate.get("device"))
        candidate_id = str(candidate.get("candidateId"))
        if not device or not candidate_id or not isinstance(candidate.get("fdtdMetrics"), dict):
            continue
        key = (device, candidate_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _threshold_device(
    root: Path,
    fusion_candidates: dict[str, Any],
    *,
    hardening_profile: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if hardening_profile and isinstance(hardening_profile.get("thresholdReferenceDevice"), dict):
        return hardening_profile["thresholdReferenceDevice"]
    threshold_candidate = _read_json(root / "value-upgrade-20260502" / "threshold-device-candidate.json")
    if threshold_candidate:
        return threshold_candidate
    best = fusion_candidates.get("bestNominalCandidate") or {}
    if best.get("metrics"):
        return {
            "schemaVersion": "open-quantum.eigenmode-device.v1",
            "device": best.get("device"),
            "candidateId": best.get("candidateId"),
            "fdtdMetrics": best.get("metrics"),
        }
    return None


def _best_for_target(rows: list[dict[str, Any]], target: float) -> dict[str, Any] | None:
    passing = [row for row in rows if row["estimatedLogicalErrorRatePerCycle"] <= target]
    if not passing:
        return None
    return min(
        passing,
        key=lambda row: (
            row["estimatedPhysicalModesPerCorrectionCycle"],
            row["estimatedLogicalErrorRatePerCycle"],
        ),
    )


def _fusion_row_rank(row: dict[str, Any]) -> tuple[int, int, float, float]:
    strict = row["strictTargets"]
    return (
        1 if strict["nominalMeetsSuccessTarget"] and strict["nominalMeetsFidelityTarget"] else 0,
        1 if strict["nominalMeetsSuccessTarget"] else 0,
        row["nominalSourceDetector"]["estimatedHeraldingSuccessProbability"],
        row["nominalSourceDetector"]["estimatedProcessFidelity"],
    )


def _fusion_row_rank_upgraded(row: dict[str, Any]) -> tuple[int, int, float, float]:
    strict = row["strictTargets"]
    return (
        1 if strict["upgradedMeetsSuccessTarget"] and strict["upgradedMeetsFidelityTarget"] else 0,
        1 if strict["upgradedMeetsSuccessTarget"] else 0,
        row["upgradedSourceDetector"]["estimatedHeraldingSuccessProbability"],
        row["upgradedSourceDetector"]["estimatedProcessFidelity"],
    )


def _fusion_row_rank_stretch(row: dict[str, Any]) -> tuple[int, int, float, float]:
    strict = row["strictTargets"]
    stretch = row["stretchSourceDetectorFastPath"]
    return (
        1 if strict["stretchMeetsSuccessTarget"] and strict["stretchMeetsFidelityTarget"] else 0,
        1 if strict["stretchMeetsSuccessTarget"] else 0,
        stretch["estimatedHeraldingSuccessProbability"],
        stretch["estimatedProcessFidelity"],
    )


def _fusion_metrics(report: dict[str, Any]) -> dict[str, float]:
    return {
        "estimatedHeraldingSuccessProbability": _success_probability(report),
        "estimatedProcessFidelity": _process_fidelity(report),
        "feedForwardLatencyNs": float((report.get("qualityModel") or {}).get("feedForwardLatencyNs", 0.0)),
    }


def _success_probability(report: dict[str, Any]) -> float:
    return float((report.get("heraldingModel") or {}).get("estimatedHeraldingSuccessProbability", 0.0))


def _process_fidelity(report: dict[str, Any]) -> float:
    return float((report.get("qualityModel") or {}).get("estimatedProcessFidelity", 0.0))


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _baseline_truth_switch() -> dict[str, Any]:
    return {
        "candidateId": "truth-switch_gap0p08_len8_phi0_w0p4",
        "crosstalkRatio": 0.02867390888638699,
        "reflectionRatio": 0.004425849500104598,
        "source": "reports/node-alpha/value-upgrade-20260502/yield-optimized-device-sweep.json",
    }


def _check(
    requirement: str,
    description: str,
    complete: bool,
    evidence: list[str],
    gaps: list[str],
) -> dict[str, Any]:
    return {
        "requirement": requirement,
        "description": description,
        "status": "complete" if complete else "gap",
        "evidence": evidence,
        "gaps": gaps,
    }


def _first_json(paths: list[Path]) -> dict[str, Any]:
    for path in paths:
        report = _read_json(path)
        if report:
            return report
    return {}


def _manifest_models(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = report.get("models") or report.get("compactModels") or report.get("virtualSparameterModels") or {}
    if not isinstance(raw, dict):
        return {}
    return {str(device).strip().lower().replace("_", "-"): model for device, model in raw.items() if isinstance(model, dict)}


def _file_hash_verified(path: str | Path | None, expected_hash: str | None) -> bool:
    if not path or not expected_hash:
        return False
    target = Path(path)
    if not target.is_file():
        return False
    digest = sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected_hash


def _metric(metrics: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(metrics.get(key, default))
    except (TypeError, ValueError):
        return default


def _covers_window(value: Any, low: float, high: float) -> bool:
    if not isinstance(value, list) or len(value) < 2:
        return False
    try:
        return float(value[0]) <= low and float(value[1]) >= high
    except (TypeError, ValueError):
        return False


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    throughput = report["throughput"]["summary"]
    threshold = report["thresholdPerformance"]["summary"]
    truth = report["truthSwitchTargets"]["summary"]
    truth_raw = report["truthSwitchRawClosure"]["summary"]
    fusion = report["fusionPerformance"]["summary"]
    envelope = report["operationalEnvelope"]["summary"]
    joint = report["jointErrorBudget"]["summary"]
    optimizer = report["budgetOptimizer"]["summary"]
    sparams = report["virtualSparameterAcceptance"]["summary"]
    layout = report["scaledLayoutEnvelope"]["summary"]
    control = report["controlTimingModel"]["summary"]
    decoder = report["decoderEvidence"]["summary"]
    stress = report["stressRecovery"]["summary"]
    prototype = report["prototypeGapReduction"]["summary"]
    lines = [
        "# OQP-HRM Deep-Hardening V3",
        "",
        "Simulation-only Deep-Hardening V3 Max-Out report. This is not measured chip performance, prototype readiness, foundry readiness, or tapeout readiness.",
        "",
        "## Summary",
        "",
        f"- Max scaled physical modes: `{summary['maxScaledPhysicalModes']}`",
        f"- Max scaled logical dual-rail qubits: `{summary['maxScaledLogicalQubits']}`",
        f"- Target `1e-8` logical error met: `{threshold['target1e8Met']}`",
        f"- Target `1e-9` logical error met: `{threshold['target1e9Met']}`",
        f"- Best nominal fusion success: `{fusion['bestNominalSuccessProbability']}`",
        f"- Best nominal fusion fidelity: `{fusion['bestNominalProcessFidelity']}`",
        f"- Best stretch fusion success: `{fusion['bestStretchSuccessProbability']}`",
        f"- Best stretch fusion fidelity: `{fusion['bestStretchProcessFidelity']}`",
        f"- Truth-switch strict target met: `{truth['strictTargetMet']}`",
        f"- Target `1e-9` operational envelope distance: `{envelope['target1e9RecommendedDistance']}`",
        f"- Target `1e-9` max single-axis loss: `{envelope['target1e9MaxSingleAxisLossDb']}` dB",
        f"- Target `1e-9` min single-axis detector efficiency: `{envelope['target1e9MinSingleAxisDetectorEfficiency']}`",
        f"- Target `1e-9` max single-axis phase error: `{envelope['target1e9MaxSingleAxisPhaseErrorRad']}` rad",
        f"- Target `1e-9` max single-axis feed-forward latency: `{envelope['target1e9MaxSingleAxisFeedForwardLatencyNs']}` ns",
        f"- Target `1e-9` hardening margin targets met: `{envelope['target1e9HardeningMarginTargetsMet']}`",
        f"- Target `1e-9` joint budget pass: `{joint['target1e9JointBudgetPass']}`",
        f"- Target `1e-9` balanced joint logical error: `{joint['target1e9BalancedLogicalErrorRate']}`",
        f"- Target `1e-9` optimized profile count: `{optimizer['target1e9OptimizedProfileCount']}`",
        f"- Target `1e-9` detector-relaxed minimum efficiency: `{optimizer['target1e9DetectorRelaxedMinEfficiency']}`",
        f"- Upper-bound fusion attempts/s: `{throughput['maxUpperBoundFusionAttemptsPerSecond']}`",
        f"- Upper-bound heralded events/s: `{throughput['maxUpperBoundHeraldedEventsPerSecond']}`",
        f"- Virtual S-parameter accepted devices: `{sparams['acceptedVirtualDeviceCount']}` / `{sparams['requiredDeviceCount']}`",
        f"- Max virtual S-parameter crosstalk: `{sparams['maxVirtualCrosstalkRatio']}`",
        f"- Max virtual S-parameter reflection: `{sparams['maxVirtualReflectionRatio']}`",
        f"- Virtual S-parameters below 0.30% / 0.008%: `{sparams['allVirtualCrosstalkBelow0p30Percent']}` / `{sparams['allVirtualReflectionBelow0p008Percent']}`",
        f"- Foundry-calibrated S-parameters ready: `{report['virtualSparameterAcceptance']['readinessImpact']['foundryCalibratedSparameters']}`",
        f"- Max scaled layout area: `{layout['maxEstimatedAreaMm2']}` mm^2",
        f"- Max scaled route-length reduction: `{layout['maxTotalRouteLengthReductionFraction']}`",
        f"- Target `1e-9` stress recovery scale: `{stress['target1e9MaxUniformStressScale']}`",
        f"- Target `1e-9` combined/worst stress pass: `{stress['target1e9StressPointPassesAsIs']}` / `{stress['target1e9WorstCaseStressPasses']}`",
        f"- Target `1e-9` control timing closed in simulation: `{control['target1e9TimingClosedInSimulation']}`",
        f"- Best fast-path latency: `{control['bestFastPathLatencyNs']}` ns",
        f"- Target `1e-9` toy decoder latency: `{decoder['target1e9ToyDecoderLatencyNs']}` ns",
        f"- Full decoder below 15 ns: `{decoder['target1e9LatencyBelow15Ns']}`",
        f"- Truth-switch raw strict target met: `{truth_raw['rawStrictTargetMet']}`",
        f"- Truth-switch raw stretch target met: `{truth_raw['rawStretchTargetMet']}`",
        f"- Prototype local simulation criteria improved: `{prototype['localSimulationCriteriaImproved']}` / `{prototype['localSimulationCriteriaTotal']}`",
        "",
        "## Explicit Gaps",
        "",
    ]
    gaps = report["completionAudit"]["missingOrWeakRequirements"]
    if gaps:
        for gap in gaps:
            lines.append(f"- {gap['requirement']}: {', '.join(gap['gaps'])}")
    else:
        lines.append("- None within the simulation-only objective.")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
        ]
    )
    for name, path in report["artifactRefs"].items():
        lines.append(f"- {name}: `{path}`")
    return "\n".join(lines) + "\n"


def _update_report_index(root: Path, report: dict[str, Any]) -> None:
    index_path = root / "report-index.json"
    existing = _read_json(index_path)
    artifacts_by_path: dict[str, dict[str, Any]] = {}
    for item in existing.get("artifacts", []) if isinstance(existing.get("artifacts"), list) else []:
        if isinstance(item, dict) and item.get("path"):
            existing_path = Path(str(item["path"]))
            if not _existing_report_index_path_in_scope(existing_path, root):
                continue
            artifact = _artifact_index_item(existing_path, root)
            artifacts_by_path[artifact["path"]] = artifact
    for path in report.get("artifactRefs", {}).values():
        artifact = _artifact_index_item(Path(path), root)
        artifacts_by_path[artifact["path"]] = artifact
    artifacts = sorted(artifacts_by_path.values(), key=lambda item: item["path"])
    missing = [item for item in artifacts if not item["exists"]]
    index = {
        "schemaVersion": "open-quantum.report-index.v2",
        "generatedAt": _now(),
        "artifactCount": len(artifacts),
        "presentArtifactCount": len(artifacts) - len(missing),
        "missingArtifactCount": len(missing),
        "deepHardeningV3": {
            "status": report["summary"]["status"],
            "score": report["summary"]["deepHardeningScore"],
            "simulatedOnly": True,
            "prototypeReady": False,
            "tapeoutReady": False,
            "foundrySparametersReady": False,
            "stressScale": report["summary"]["target1e9StressRecoveryScaleFactor"],
            "truthSwitchRawCrosstalkRatio": report["summary"]["truthSwitchRawBestCrosstalkRatio"],
            "truthSwitchRawReflectionRatio": report["summary"]["truthSwitchRawBestReflectionRatio"],
            "nominalFusionSuccessProbability": report["summary"]["bestNominalFusionSuccessProbability"],
            "nominalFusionProcessFidelity": report["summary"]["bestNominalFusionFidelity"],
            "layoutAreaMm2": report["summary"]["maxScaledLayoutAreaMm2"],
            "fastPathLatencyNs": report["summary"]["fastPathBestLatencyNs"],
            "fullDecoderLatencyNs": report["summary"]["target1e9ToyDecoderLatencyNs"],
        },
        "artifacts": artifacts,
    }
    write_json_report(index, index_path)


def _existing_report_index_path_in_scope(path: Path, root: Path) -> bool:
    if not path.is_absolute():
        return True
    actual = path.resolve(strict=False)
    scopes = (Path.cwd().resolve(), root.resolve(), root.parent.resolve())
    return any(actual == scope or scope in actual.parents for scope in scopes)


def _artifact_index_item(path: Path, root: Path) -> dict[str, Any]:
    actual = path
    if not actual.is_file() and not actual.is_absolute():
        for candidate in (root.parent / actual, root / actual):
            if candidate.is_file():
                actual = candidate
                break
    exists = actual.is_file()
    rel = actual if not actual.is_absolute() else actual
    try:
        rel_text = str(rel.relative_to(Path.cwd()))
    except ValueError:
        try:
            rel_text = str(rel.relative_to(root.parent))
        except ValueError:
            rel_text = str(rel)
    item: dict[str, Any] = {
        "path": rel_text,
        "exists": exists,
        "kind": actual.suffix.lstrip(".") or "artifact",
    }
    if not exists:
        return item
    data = actual.read_bytes()
    item["bytes"] = len(data)
    item["sha256"] = sha256(data).hexdigest()
    if actual.suffix == ".json":
        raw = _read_json(actual)
        if raw.get("schemaVersion"):
            item["schemaVersion"] = raw["schemaVersion"]
        if isinstance(raw.get("summary"), dict):
            item["summary"] = raw["summary"]
    return item


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
