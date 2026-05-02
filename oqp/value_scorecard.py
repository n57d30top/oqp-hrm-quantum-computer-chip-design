"""No-budget value scorecard for the OQP-HRM partner package."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .blueprint import Blueprint
from .report import write_json_report


def generate_value_scorecard(
    blueprint: Blueprint,
    *,
    artifact_root: str | Path = "reports/node-alpha",
    out_dir: str | Path | None = None,
    docs_dir: str | Path = "docs",
) -> dict[str, Any]:
    """Write a conservative diligence-oriented value scorecard.

    This is not a legal valuation, investment recommendation, or patent
    opinion. It exists to make the current engineering package easier to review
    by partners, reviewers, grant programs, and potential collaborators.
    """

    root = Path(artifact_root)
    output = Path(out_dir) if out_dir else root / "no-budget-package"
    docs = Path(docs_dir)
    output.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)

    evidence = _evidence_snapshot(root)
    scores = _scores(evidence, docs)
    valuation = _valuation_ranges(evidence, scores)
    risk_register = _risk_register(evidence)
    value_ladder = _value_ladder(valuation)
    claim_matrix = _claim_readiness_matrix(evidence)
    partner_asks = _partner_ask_matrix()
    assumptions = _assumption_register(evidence)
    reviewer_questions = _reviewer_question_bank()
    partner_pipeline = _partner_pipeline()
    milestones = _milestones()
    report = {
        "schemaVersion": "open-quantum.value-scorecard.v1",
        "generatedAt": _now(),
        "sourcePath": blueprint.source_path,
        "purpose": "Increase partner diligence value without claiming build or prototype readiness.",
        "claimBoundary": {
            "assetClass": "simulation_and_partner_diligence_package",
            "notAClaimOf": [
                "fabrication-ready quantum computer",
                "foundry-clean tapeout",
                "hardware-demonstrated primitive",
                "hardware-calibrated fault tolerance",
                "patentability or freedom-to-operate",
            ],
        },
        "evidenceSnapshot": evidence,
        "scores": scores,
        "scoreBreakdown": scores["breakdown"],
        "claimReadinessMatrix": claim_matrix,
        "diligenceRiskRegister": risk_register,
        "partnerAskMatrix": partner_asks,
        "assumptionRegister": assumptions,
        "reviewerQuestionBank": reviewer_questions,
        "partnerPipeline": partner_pipeline,
        "valuationRanges": valuation,
        "valuationConfidence": _valuation_confidence(evidence),
        "valueLadder": value_ladder,
        "valueLeversCompleted": [
            "machine-readable value scorecard",
            "transparent score breakdown by evidence item",
            "diligence risk register with explicit external blockers",
            "claim-readiness matrix separating simulation, partner, and hardware claims",
            "assumption register and reviewer question bank",
            "partner pipeline with stage gates and success metrics",
            "yield-improvement delta integrated into value scoring",
            "partner outreach brief",
            "grant concept note",
            "data-room index",
            "explicit milestone-to-value ladder",
        ],
        "nextNoCashActions": [
            "send partner outreach brief to academic quantum-photonics groups",
            "ask for independent device-metric review before any fabrication claim",
            "turn the grant concept note into a non-dilutive funding application",
            "collect written reviewer feedback and attach it as diligence evidence",
        ],
        "milestones": milestones,
        "artifactRefs": {
            "scorecardJson": str(output / "value-scorecard.json"),
            "scorecardMarkdown": str(output / "value-scorecard.md"),
            "partnerOutreach": str(docs / "partner-outreach.md"),
            "grantConceptNote": str(docs / "grant-concept-note.md"),
            "dataRoomIndex": str(docs / "data-room-index.md"),
            "reviewerPack": str(docs / "reviewer-pack.md"),
            "partnerPipeline": str(docs / "partner-pipeline.md"),
        },
        "summary": {
            "status": "value_scorecard_generated",
            "currentCommercialReadiness": scores["commercialReadinessScore"],
            "partnerDiligenceReadiness": scores["partnerDiligenceReadinessScore"],
            "technicalEvidenceScore": scores["technicalEvidenceScore"],
            "scorecardCompleteness": scores["scorecardCompleteness"],
            "reviewerQuestionCount": len(reviewer_questions),
            "activeCriticalRiskCount": sum(
                1 for risk in risk_register if risk["active"] and risk["severity"] == "critical"
            ),
            "partnerPipelineStageCount": len(partner_pipeline),
            "deterministicYieldPassing": evidence["testchip"]["allDevicesYieldPassing"],
            "yieldImprovementMultiplier": evidence["yieldImprovement"]["relativeSystemYieldMultiplier"],
            "performanceHardeningComplete": evidence["performance"]["completionAuditDecision"] == "complete",
            "performanceHardeningSimulationOnly": evidence["performance"]["present"]
            and evidence["performance"]["completionAuditDecision"] == "complete"
            and evidence["performance"]["virtualSparameterReadyForFoundryClaim"] is False,
            "immediateSaleRange": valuation["immediateSaleWithoutHardware"],
            "partnerPackageRange": valuation["partnerReviewPackage"],
            "grantLeverageRange": valuation["grantLeverageTarget"],
            "prototypeReady": evidence["prototype"]["status"] == "prototype_ready",
            "tapeoutReady": evidence["gds"]["tapeoutReady"] is True,
            "foundrySparametersReady": evidence["sparameters"]["foundryCalibrated"] is True,
        },
    }

    write_json_report(report, output / "value-scorecard.json")
    (output / "value-scorecard.md").write_text(_scorecard_markdown(report), encoding="utf-8")
    (docs / "partner-outreach.md").write_text(_partner_outreach_markdown(report), encoding="utf-8")
    (docs / "grant-concept-note.md").write_text(_grant_concept_markdown(report), encoding="utf-8")
    (docs / "data-room-index.md").write_text(_data_room_markdown(report), encoding="utf-8")
    (docs / "reviewer-pack.md").write_text(_reviewer_pack_markdown(report), encoding="utf-8")
    (docs / "partner-pipeline.md").write_text(_partner_pipeline_markdown(report), encoding="utf-8")
    return report


def _evidence_snapshot(root: Path) -> dict[str, Any]:
    value = _read_json(root / "value-upgrade-20260502" / "value-upgrade-report.json")
    robust = _read_json(root / "value-upgrade-20260502" / "high-resolution-robustness-report.json")
    yield_sweep = _read_json(root / "value-upgrade-20260502" / "testchip" / "yield-sweep.json")
    yield_improvement = _read_json(root / "value-upgrade-20260502" / "yield-improvement-report.json")
    fault = _read_json(root / "qc-path" / "fault-tolerance-audit.json")
    sparameters = _read_json(root / "qc-path" / "sparameter-audit.json")
    gds = _read_json(root / "gds-path" / "gds-audit.json")
    prototype = _read_json(root / "qc-path" / "prototype-readiness.json")
    performance = _first_json(
        [
            root / "deep-hardening-v3-20260502" / "deep-hardening-v3-report.json",
            root / "deep-hardening-v3-20260502" / "performance-upgrade-report.json",
            root / "deep-hardening-v2-20260502" / "deep-hardening-v2-report.json",
            root / "deep-hardening-v2-20260502" / "performance-upgrade-report.json",
            root / "performance-upgrade-20260502" / "deep-hardening-v3-report.json",
            root / "performance-upgrade-20260502" / "deep-hardening-v2-report.json",
            root / "performance-upgrade-20260502" / "performance-upgrade-report.json",
        ]
    )
    report_index = _read_json(root / "report-index.json")
    no_budget = _read_json(root / "no-budget-package" / "no-budget-readiness.json")
    return {
        "valuePackage": {
            "status": value.get("summary", {}).get("status"),
            "thresholdStatus": value.get("summary", {}).get("thresholdStatus"),
            "thresholdChampionLogicalErrorRate": value.get("summary", {}).get("thresholdChampionLogicalErrorRate"),
            "syntheticSyndromeEventCount": value.get("summary", {}).get("syntheticSyndromeEventCount"),
        },
        "highResolution": {
            "status": robust.get("summary", {}).get("status"),
            "acceptedDevices": robust.get("summary", {}).get("acceptedDevices", []),
            "blockedDevices": robust.get("summary", {}).get("blockedDevices", []),
            "allRequiredDevicesAccepted": robust.get("summary", {}).get("allRequiredDevicesAccepted") is True,
        },
        "testchip": {
            "allDevicesYieldPassing": yield_sweep.get("summary", {}).get("allDevicesYieldPassing") is True,
            "systemYieldEstimate": yield_sweep.get("summary", {}).get("systemYieldEstimate"),
            "acceptedDeviceCount": yield_sweep.get("summary", {}).get("acceptedDeviceCount"),
            "requiredDeviceCount": yield_sweep.get("summary", {}).get("requiredDeviceCount"),
        },
        "yieldImprovement": {
            "present": bool(yield_improvement),
            "baselineSystemYieldEstimate": yield_improvement.get("baselineBeforeOptimization", {}).get(
                "systemYieldEstimate"
            ),
            "currentSystemYieldEstimate": yield_improvement.get("currentAfterOptimization", {}).get(
                "systemYieldEstimate"
            ),
            "relativeSystemYieldMultiplier": yield_improvement.get("improvement", {}).get(
                "relativeSystemYieldMultiplier"
            ),
            "absoluteSystemYieldGain": yield_improvement.get("improvement", {}).get("absoluteSystemYieldGain"),
            "acceptedDeviceCountGain": yield_improvement.get("improvement", {}).get("acceptedDeviceCountGain"),
            "claimBoundary": yield_improvement.get("claimBoundary"),
        },
        "faultTolerance": {
            "ready": fault.get("readinessFlags", {}).get("fault_tolerance_ready") is True,
            "hardwareCalibratedNoiseAvailable": fault.get("readinessFlags", {}).get(
                "hardware_calibrated_noise_available"
            )
            is True,
            "belowThresholdEvidence": fault.get("readinessFlags", {}).get("below_threshold_evidence") is True,
            "decoderImplemented": fault.get("readinessFlags", {}).get("decoder_implemented") is True,
        },
        "sparameters": {
            "modelsPresent": sparameters.get("readinessFlags", {}).get("all_core_sparameters_present") is True,
            "hashesVerified": sparameters.get("readinessFlags", {}).get("all_hashes_verified") is True,
            "foundryCalibrated": sparameters.get("readinessFlags", {}).get("foundry_calibrated_sparameters") is True,
            "modelsReady": sparameters.get("readinessFlags", {}).get("sparameter_models_ready") is True,
        },
        "gds": {
            "generated": gds.get("auditFlags", {}).get("gds_generated") is True,
            "layoutComputable": gds.get("auditFlags", {}).get("layout_computable") is True,
            "tapeoutReady": not bool(gds.get("auditFlags", {}).get("not_tapeout_ready", True)),
            "foundryPdkMissing": gds.get("auditFlags", {}).get("foundry_pdk_missing") is True,
            "drcNotRun": gds.get("auditFlags", {}).get("drc_not_run") is True,
            "lvsNotRun": gds.get("auditFlags", {}).get("lvs_not_run") is True,
        },
        "prototype": {
            "status": prototype.get("summary", {}).get("status"),
            "completeCriteria": prototype.get("summary", {}).get("completeCriteria"),
            "totalCriteria": prototype.get("summary", {}).get("totalCriteria"),
            "highestPriorityBlocker": prototype.get("summary", {}).get("highestPriorityBlocker"),
        },
        "performance": {
            "present": bool(performance),
            "maxScaledPhysicalModes": performance.get("summary", {}).get("maxScaledPhysicalModes"),
            "maxScaledLogicalQubits": performance.get("summary", {}).get("maxScaledLogicalQubits"),
            "target1e9LogicalErrorMet": performance.get("summary", {}).get("target1e9LogicalErrorMet") is True,
            "completionAuditDecision": performance.get("completionAudit", {}).get("decision"),
            "bestNominalFusionFidelity": performance.get("summary", {}).get("bestNominalFusionFidelity"),
            "fusionTargetMetInNominalScenario": performance.get("summary", {}).get(
                "fusionTargetMetInNominalScenario"
            )
            is True,
            "target1e9HardeningMarginTargetsMet": performance.get("summary", {}).get(
                "target1e9HardeningMarginTargetsMet"
            )
            is True,
            "target1e9MaxSingleAxisLossDb": performance.get("summary", {}).get(
                "target1e9MaxSingleAxisLossDb"
            ),
            "target1e9MinSingleAxisDetectorEfficiency": performance.get("summary", {}).get(
                "target1e9MinSingleAxisDetectorEfficiency"
            ),
            "target1e9ControlTimingPass": performance.get("summary", {}).get("target1e9ControlTimingPass") is True,
            "target1e9StressRecoveryScaleFactor": performance.get("summary", {}).get(
                "target1e9StressRecoveryScaleFactor"
            ),
            "target1e9ToyDecoderLatencyNs": performance.get("summary", {}).get("target1e9ToyDecoderLatencyNs"),
            "target1e9ToyDecoderLatencyBelow250Ns": performance.get("summary", {}).get(
                "target1e9ToyDecoderLatencyBelow250Ns"
            )
            is True,
            "target1e9ToyDecoderLatencyBelow15Ns": (
                performance.get("summary", {}).get("target1e9ToyDecoderLatencyNs") is not None
                and performance.get("summary", {}).get("target1e9ToyDecoderLatencyNs") < 15.0
            ),
            "truthSwitchRawStrictTargetMet": performance.get("summary", {}).get(
                "truthSwitchRawStrictTargetMet"
            )
            is True,
            "truthSwitchRawBestCrosstalkRatio": performance.get("summary", {}).get(
                "truthSwitchRawBestCrosstalkRatio"
            ),
            "truthSwitchRawBestReflectionRatio": performance.get("summary", {}).get(
                "truthSwitchRawBestReflectionRatio"
            ),
            "virtualSparameterAcceptedDeviceCount": performance.get("summary", {}).get(
                "virtualSparameterAcceptedDeviceCount"
            ),
            "allVirtualSparameterCrosstalkBelow2Percent": performance.get("summary", {}).get(
                "allVirtualSparameterCrosstalkBelow2Percent"
            )
            is True,
            "allVirtualSparameterReflectionBelow0p1Percent": performance.get("summary", {}).get(
                "allVirtualSparameterReflectionBelow0p1Percent"
            )
            is True,
            "allVirtualSparameterCrosstalkBelow1Percent": performance.get("summary", {}).get(
                "allVirtualSparameterCrosstalkBelow1Percent"
            )
            is True,
            "allVirtualSparameterReflectionBelow0p05Percent": performance.get("summary", {}).get(
                "allVirtualSparameterReflectionBelow0p05Percent"
            )
            is True,
            "allVirtualSparameterCrosstalkBelow0p30Percent": performance.get("summary", {}).get(
                "allVirtualSparameterCrosstalkBelow0p30Percent"
            )
            is True,
            "allVirtualSparameterReflectionBelow0p008Percent": performance.get("summary", {}).get(
                "allVirtualSparameterReflectionBelow0p008Percent"
            )
            is True,
            "virtualSparameterReadyForFoundryClaim": performance.get("summary", {}).get(
                "virtualSparameterReadyForFoundryClaim"
            )
            is True,
            "maxScaledLayoutAreaMm2": performance.get("summary", {}).get("maxScaledLayoutAreaMm2"),
            "scaledLayoutAreaTargetMet": performance.get("summary", {}).get("scaledLayoutAreaTargetMet") is True,
            "maxScaledLayoutRouteReductionFraction": performance.get("summary", {}).get(
                "maxScaledLayoutRouteReductionFraction"
            ),
            "prototypeLocalSimulationCriteriaImproved": performance.get("summary", {}).get(
                "prototypeLocalSimulationCriteriaImproved"
            ),
        },
        "reportIndex": {
            "presentArtifactCount": report_index.get("presentArtifactCount"),
            "artifactCount": report_index.get("artifactCount"),
            "missingArtifactCount": report_index.get("missingArtifactCount"),
        },
        "noBudgetReadiness": {
            "present": bool(no_budget),
            "constraint": no_budget.get("constraint"),
        },
    }


def _scores(evidence: dict[str, Any], docs: Path) -> dict[str, Any]:
    docs_present = [
        docs / "no-budget-partner-package.md",
        docs / "30-minute-reproduction.md",
        docs / "preprint-outline.md",
        docs / "open-validation-issues.md",
    ]
    breakdown = {
        "technicalEvidence": [
            _score_item("high_resolution_core_devices", 30, evidence["highResolution"]["allRequiredDevicesAccepted"]),
            _score_item("below_threshold_analytical_path", 10, evidence["valuePackage"]["thresholdStatus"] == "below_threshold_candidate_found"),
            _score_item("decoder_and_threshold_audit", 8, evidence["faultTolerance"]["belowThresholdEvidence"] and evidence["faultTolerance"]["decoderImplemented"]),
            _score_item("generic_gds_generated", 8, evidence["gds"]["generated"] and evidence["gds"]["layoutComputable"]),
            _score_item("virtual_sparameter_hashes", 6, evidence["sparameters"]["modelsPresent"] and evidence["sparameters"]["hashesVerified"]),
            _score_item("deterministic_yield_stress_pass", 6, evidence["testchip"]["allDevicesYieldPassing"]),
            _score_item(
                "extended_performance_package",
                4,
                evidence["performance"]["present"]
                and evidence["performance"]["maxScaledPhysicalModes"] == 760
                and evidence["performance"]["target1e9LogicalErrorMet"],
            ),
            _score_item(
                "stress_control_decoder_models",
                4,
                evidence["performance"]["target1e9ControlTimingPass"]
                and evidence["performance"]["target1e9StressRecoveryScaleFactor"] is not None
                and evidence["performance"]["target1e9ToyDecoderLatencyNs"] is not None,
            ),
            _score_item(
                "hardening_goal_package",
                8,
                evidence["performance"]["completionAuditDecision"] == "complete"
                and evidence["performance"]["truthSwitchRawStrictTargetMet"]
                and evidence["performance"]["target1e9HardeningMarginTargetsMet"]
                and evidence["performance"]["fusionTargetMetInNominalScenario"]
                and evidence["performance"]["target1e9ToyDecoderLatencyBelow15Ns"]
                and evidence["performance"]["scaledLayoutAreaTargetMet"],
                note="Simulation-only hardening package hit the local Truth-Switch, margin, fusion, layout, stress, and decoder targets.",
            ),
            _score_item(
                "virtual_sparameter_acceptance_package",
                2,
                evidence["performance"]["virtualSparameterAcceptedDeviceCount"] == 4
                and evidence["performance"]["allVirtualSparameterCrosstalkBelow0p30Percent"]
                and evidence["performance"]["allVirtualSparameterReflectionBelow0p008Percent"]
                and not evidence["performance"]["virtualSparameterReadyForFoundryClaim"],
                note="Simulation-only S-parameter acceptance improved without converting it into a foundry claim.",
            ),
            _score_item("complete_report_index", 4, evidence["reportIndex"]["missingArtifactCount"] == 0),
        ],
        "commercialReadiness": [
            _score_item("simulated_core_device_closure", 8, evidence["highResolution"]["allRequiredDevicesAccepted"]),
            _score_item("gds_available", 5, evidence["gds"]["generated"]),
            _score_item("compact_model_placeholders_present", 3, evidence["sparameters"]["modelsPresent"]),
            _score_item("deterministic_yield_estimate_present", 4, evidence["testchip"]["systemYieldEstimate"] is not None),
            _score_item("deterministic_yield_stress_pass", 5, evidence["testchip"]["allDevicesYieldPassing"]),
            _score_item("foundry_calibrated_sparameters", 15, evidence["sparameters"]["foundryCalibrated"]),
            _score_item("tapeout_ready_gds", 20, evidence["gds"]["tapeoutReady"]),
            _score_item("hardware_calibrated_noise", 20, evidence["faultTolerance"]["hardwareCalibratedNoiseAvailable"]),
            _score_item("prototype_ready", 20, evidence["prototype"]["status"] == "prototype_ready"),
        ],
        "partnerDiligence": [
            _score_item("complete_report_index", 20, evidence["reportIndex"]["missingArtifactCount"] == 0),
            _score_item("core_partner_docs_present", 20, all(path.is_file() for path in docs_present)),
            _score_item("high_resolution_device_evidence", 20, evidence["highResolution"]["allRequiredDevicesAccepted"]),
            _score_item("no_budget_readiness_report", 10, evidence["noBudgetReadiness"]["present"]),
            _score_item("generic_gds_available", 10, evidence["gds"]["generated"]),
            _score_item("sparameter_models_present", 10, evidence["sparameters"]["modelsPresent"]),
            _score_item("claim_boundary_preserved", 10, evidence["prototype"]["status"] == "not_prototype_ready"),
        ],
    }
    technical = min(100, _score_total(breakdown["technicalEvidence"]))
    commercial = min(100, _score_total(breakdown["commercialReadiness"]))
    partner = min(100, _score_total(breakdown["partnerDiligence"]))
    completeness = _scorecard_completeness(evidence, docs_present)

    return {
        "technicalEvidenceScore": technical,
        "commercialReadinessScore": commercial,
        "partnerDiligenceReadinessScore": partner,
        "scorecardCompleteness": completeness,
        "breakdown": breakdown,
        "scoreInterpretation": {
            "technicalEvidenceScore": "simulation evidence and reproducibility, not hardware proof",
            "commercialReadinessScore": "cash-sale readiness; capped by missing hardware/foundry/legal evidence",
            "partnerDiligenceReadinessScore": "how ready the package is for unpaid external review",
            "scorecardCompleteness": "how complete the diligence packet is as a review artifact",
        },
    }


def _score_item(identifier: str, points: int, condition: bool, *, note: str | None = None) -> dict[str, Any]:
    return {
        "id": identifier,
        "points": points if condition else 0,
        "maxPoints": points,
        "passed": bool(condition),
        "note": note,
    }


def _score_total(items: list[dict[str, Any]]) -> int:
    return sum(int(item["points"]) for item in items)


def _scorecard_completeness(evidence: dict[str, Any], docs_present: list[Path]) -> int:
    checks = [
        evidence["reportIndex"]["missingArtifactCount"] == 0,
        evidence["yieldImprovement"]["present"],
        evidence["noBudgetReadiness"]["present"],
        all(path.is_file() for path in docs_present),
        evidence["prototype"]["status"] == "not_prototype_ready",
    ]
    return int(round(100 * sum(1 for check in checks if check) / len(checks)))


def _valuation_ranges(evidence: dict[str, Any], scores: dict[str, Any]) -> dict[str, Any]:
    partner_ready = scores["partnerDiligenceReadinessScore"] >= 70
    high_res_closed = evidence["highResolution"]["allRequiredDevicesAccepted"]
    return {
        "immediateSaleWithoutHardware": {
            "currency": "USD_or_EUR_order_of_magnitude",
            "low": 0,
            "mid": 5000 if high_res_closed else 1000,
            "high": 10000 if high_res_closed else 5000,
            "rationale": "No patent, no chip, no foundry signoff, and no hardware data keep cash-sale value low.",
        },
        "partnerReviewPackage": {
            "currency": "USD_or_EUR_order_of_magnitude",
            "low": 10000 if partner_ready else 5000,
            "mid": 25000 if partner_ready else 10000,
            "high": 50000 if partner_ready else 25000,
            "rationale": "Value is in reviewer time saved by reproducible artifacts, not in build readiness.",
        },
        "grantLeverageTarget": {
            "currency": "USD_or_EUR_non_dilutive_target",
            "low": 50000,
            "mid": 150000,
            "high": 300000,
            "rationale": "A strong simulation package can support a proof-of-concept grant ask; award probability is separate.",
        },
        "postFoundrySparameterReview": {
            "currency": "USD_or_EUR_order_of_magnitude",
            "low": 100000,
            "mid": 250000,
            "high": 500000,
            "rationale": "Foundry-calibrated compact models and PDK review would remove the largest diligence blockers.",
        },
        "postMeasuredTestchip": {
            "currency": "USD_or_EUR_order_of_magnitude",
            "low": 500000,
            "mid": 1000000,
            "high": 2000000,
            "rationale": "Measured chip data would convert the package from simulation asset to hardware validation asset.",
        },
    }


def _valuation_confidence(evidence: dict[str, Any]) -> dict[str, Any]:
    blockers = []
    if not evidence["sparameters"]["foundryCalibrated"]:
        blockers.append("foundry-calibrated S-parameters missing")
    if not evidence["gds"]["tapeoutReady"]:
        blockers.append("foundry PDK DRC/LVS not closed")
    if not evidence["faultTolerance"]["hardwareCalibratedNoiseAvailable"]:
        blockers.append("hardware-calibrated noise model missing")
    if evidence["prototype"]["status"] != "prototype_ready":
        blockers.append("prototype evidence incomplete")
    return {
        "level": "low_for_cash_sale_high_for_partner_review",
        "cashSaleConfidence": "low",
        "partnerReviewConfidence": "high" if evidence["reportIndex"]["missingArtifactCount"] == 0 else "medium",
        "primaryUncertaintyDrivers": blockers,
    }


def _claim_readiness_matrix(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _claim("simulation_package_reproducible", True, "supported", ["value package", "report index", "unit tests"]),
        _claim(
            "core_devices_accepted_in_2d_node_alpha",
            evidence["highResolution"]["allRequiredDevicesAccepted"],
            "supported_simulation_only",
            ["high-resolution robustness report"],
        ),
        _claim(
            "deterministic_testchip_yield_stress_passed",
            evidence["testchip"]["allDevicesYieldPassing"],
            "supported_simulation_only",
            ["yield sweep", "yield improvement report"],
        ),
        _claim(
            "foundry_sparameter_ready",
            evidence["sparameters"]["foundryCalibrated"],
            "blocked_external_evidence",
            ["foundry or wafer calibrated compact models"],
        ),
        _claim(
            "tapeout_ready",
            evidence["gds"]["tapeoutReady"],
            "blocked_external_evidence",
            ["foundry PDK", "DRC report", "LVS report"],
        ),
        _claim(
            "hardware_fault_tolerance_ready",
            evidence["faultTolerance"]["ready"],
            "blocked_external_evidence",
            ["hardware-calibrated noise dataset", "validated decoder evidence"],
        ),
        _claim(
            "prototype_ready",
            evidence["prototype"]["status"] == "prototype_ready",
            "blocked_external_evidence",
            ["hardware, lab, foundry, calibration, primitive-demo evidence"],
        ),
    ]


def _claim(identifier: str, ready: bool, status: str, evidence_needed: list[str]) -> dict[str, Any]:
    return {
        "id": identifier,
        "ready": bool(ready),
        "status": "ready" if ready else status,
        "evidence": evidence_needed,
    }


def _risk_register(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _risk(
            "virtual_sparameter_gap",
            "critical",
            not evidence["sparameters"]["foundryCalibrated"],
            "Virtual S-parameters do not satisfy foundry compact-model diligence.",
            "Replace all four core device models with foundry/wafer-calibrated files and pass sparameter-audit.",
        ),
        _risk(
            "generic_gds_not_tapeout_ready",
            "critical",
            not evidence["gds"]["tapeoutReady"],
            "The GDS is layout-computable but not tied to a real foundry PDK or DRC/LVS deck.",
            "Attach PDK manifest plus DRC/LVS reports.",
        ),
        _risk(
            "synthetic_noise_only",
            "high",
            not evidence["faultTolerance"]["hardwareCalibratedNoiseAvailable"],
            "Fault-tolerance evidence uses synthetic or analytical noise assumptions.",
            "Attach hardware-calibrated syndrome/noise distributions.",
        ),
        _risk(
            "no_measured_testchip",
            "high",
            evidence["prototype"]["status"] != "prototype_ready",
            "No fabricated testchip or measured primitive data exists.",
            "Fabricate or partner for measurement, then ingest hardware and primitive-demo datasets.",
        ),
        _risk(
            "yield_is_deterministic_not_wafer_statistics",
            "medium",
            evidence["testchip"]["allDevicesYieldPassing"],
            "The improved yield is a deterministic tolerance-grid pass, not wafer yield.",
            "Replace tolerance grid with foundry process distributions and wafer data.",
        ),
    ]


def _risk(identifier: str, severity: str, active: bool, description: str, mitigation: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "severity": severity,
        "active": bool(active),
        "description": description,
        "mitigation": mitigation,
    }


def _partner_ask_matrix() -> list[dict[str, Any]]:
    return [
        {
            "ask": "device_metric_review",
            "costClass": "partner_time",
            "artifactToReview": "reports/node-alpha/deep-hardening-v3-20260502/device-sweep-deep-hardening-v3.json",
            "usefulOutput": "Written review of which 2D FDTD assumptions need 3D/MPB validation first.",
        },
        {
            "ask": "foundry_sparameter_plan",
            "costClass": "partner_or_grant",
            "artifactToReview": "reports/node-alpha/qc-path/sparameter-audit.json",
            "usefulOutput": "Port conventions, wavelength range, process corners, and calibration requirements.",
        },
        {
            "ask": "layout_to_pdk_gap_review",
            "costClass": "partner_or_grant",
            "artifactToReview": "reports/node-alpha/deep-hardening-v3-20260502/scaled-layout-envelope-report.json",
            "usefulOutput": "Foundry-specific layer, PCell, pad, package, DRC, and LVS gap list.",
        },
        {
            "ask": "testchip_measurement_plan",
            "costClass": "grant_needed",
            "artifactToReview": "reports/node-alpha/deep-hardening-v3-20260502/prototype-gap-reduction-report.json",
            "usefulOutput": "Minimal measurement matrix for first fabricated testchip.",
        },
    ]


def _assumption_register(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "2d_fdtd_candidate_validity",
            "status": "simulation_supported_not_hardware_proven",
            "currentEvidence": evidence["highResolution"]["status"],
            "validationNeeded": "3D/MPB S-parameter extraction for promoted candidates.",
        },
        {
            "id": "deterministic_yield_grid_relevance",
            "status": "planning_evidence_only",
            "currentEvidence": evidence["testchip"]["systemYieldEstimate"],
            "validationNeeded": "Foundry process distributions and measured wafer statistics.",
        },
        {
            "id": "virtual_sparameter_usefulness",
            "status": "hash_verified_placeholder",
            "currentEvidence": evidence["sparameters"]["modelsPresent"],
            "validationNeeded": "Foundry or wafer calibrated Touchstone/compact-model files.",
        },
        {
            "id": "synthetic_noise_representativeness",
            "status": "analytical_only",
            "currentEvidence": evidence["faultTolerance"]["belowThresholdEvidence"],
            "validationNeeded": "Hardware-calibrated noise and syndrome distributions.",
        },
        {
            "id": "generic_layout_portability",
            "status": "layout_envelope_not_foundry_clean",
            "currentEvidence": evidence["gds"]["generated"],
            "validationNeeded": "Versioned PDK mapping plus DRC/LVS reports.",
        },
    ]


def _reviewer_question_bank() -> list[dict[str, Any]]:
    return [
        {
            "id": "device_metrics",
            "reviewerType": "photonic_device_simulation",
            "question": "Which public V3 device candidate is most likely to fail under 3D/MPB S-parameter extraction?",
            "artifact": "reports/node-alpha/deep-hardening-v3-20260502/device-sweep-deep-hardening-v3.json",
        },
        {
            "id": "yield_model",
            "reviewerType": "silicon_photonics_process",
            "question": "Which V3 corner axis is least realistic for a foundry process?",
            "artifact": "reports/node-alpha/deep-hardening-v3-20260502/worst-case-corner-sweep-report.json",
        },
        {
            "id": "layout_mapping",
            "reviewerType": "foundry_pdk_layout",
            "question": "What is the first blocking issue when mapping the generic layout envelope to a real PDK?",
            "artifact": "reports/node-alpha/deep-hardening-v3-20260502/scaled-layout-envelope-report.json",
        },
        {
            "id": "compact_models",
            "reviewerType": "sparameter_compact_model",
            "question": "What port conventions and process corners are required to replace the virtual S-parameters?",
            "artifact": "reports/node-alpha/qc-path/sparameter-audit.json",
        },
        {
            "id": "fault_tolerance",
            "reviewerType": "quantum_error_correction",
            "question": "Which analytical noise assumption most strongly affects the 1e-9 envelope?",
            "artifact": "reports/node-alpha/deep-hardening-v3-20260502/operational-envelope-report.json",
        },
        {
            "id": "primitive_demo",
            "reviewerType": "quantum_photonics_lab",
            "question": "What is the minimal measured primitive-demo dataset that would materially raise diligence value?",
            "artifact": "reports/node-alpha/deep-hardening-v3-20260502/prototype-gap-reduction-report.json",
        },
    ]


def _partner_pipeline() -> list[dict[str, Any]]:
    return [
        {
            "stage": "target_list",
            "goal": "Identify 20 academic/foundry/lab reviewers with matching expertise.",
            "successMetric": "20 named contacts with one selected review ask each.",
            "cashRequired": False,
        },
        {
            "stage": "first_outreach",
            "goal": "Send concise partner brief with one narrow artifact review request.",
            "successMetric": "5 replies or 2 technical objections.",
            "cashRequired": False,
        },
        {
            "stage": "review_capture",
            "goal": "Convert replies into written assumption reviews attached to data room.",
            "successMetric": "2 signed or attributable technical reviews.",
            "cashRequired": False,
        },
        {
            "stage": "grant_conversion",
            "goal": "Use reviews to support a foundry-validation grant application.",
            "successMetric": "1 submitted grant or partner-funded PDK/S-parameter review.",
            "cashRequired": False,
        },
    ]


def _value_ladder(valuation: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "stage": "current_simulation_partner_package",
            "valueRange": valuation["partnerReviewPackage"],
            "entryGate": "current scorecard and data room complete",
        },
        {
            "stage": "grant_funded_foundry_review",
            "valueRange": valuation["grantLeverageTarget"],
            "entryGate": "accepted grant or no-cost foundry/university review",
        },
        {
            "stage": "foundry_sparameter_reviewed_package",
            "valueRange": valuation["postFoundrySparameterReview"],
            "entryGate": "foundry-calibrated S-parameters and PDK gap review attached",
        },
        {
            "stage": "measured_testchip_package",
            "valueRange": valuation["postMeasuredTestchip"],
            "entryGate": "measured testchip and hardware evidence ingested",
        },
    ]


def _milestones() -> list[dict[str, Any]]:
    return [
        {
            "id": "external_review_letters",
            "costClass": "no_cash_partner_time",
            "valueEffect": "raises trust in simulation assumptions",
            "definitionOfDone": "two independent written reviews attached to the data room",
        },
        {
            "id": "foundry_sparameter_replacement",
            "costClass": "partner_or_grant_needed",
            "valueEffect": "moves compact-model gate from virtual to foundry calibrated",
            "definitionOfDone": "four core device S-parameter files hash-verified and accepted by sparameter-audit",
        },
        {
            "id": "pdk_drc_lvs_review",
            "costClass": "partner_or_grant_needed",
            "valueEffect": "turns generic GDS into a real foundry gap list",
            "definitionOfDone": "PDK manifest plus DRC/LVS reports attached, even if blocked",
        },
        {
            "id": "measured_testchip",
            "costClass": "funding_needed",
            "valueEffect": "converts simulation evidence into hardware evidence",
            "definitionOfDone": "measured source/detector/device/testcell reports ingested and audited",
        },
    ]


def _scorecard_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    ranges = report["valuationRanges"]
    evidence = report["evidenceSnapshot"]
    lines = [
        "# OQP-HRM Value Scorecard",
        "",
        f"Generated: {report['generatedAt']}",
        "",
        "This is an engineering diligence scorecard, not a legal valuation or investment recommendation.",
        "",
        "## Scores",
        "",
        f"- Internal simulation evidence score: {summary['technicalEvidenceScore']} / 100",
        "- External hardware evidence score: blocked/not scored as validated hardware",
        f"- Partner diligence readiness: {summary['partnerDiligenceReadiness']} / 100",
        f"- Commercial readiness: {summary['currentCommercialReadiness']} / 100",
        f"- Scorecard completeness: {summary['scorecardCompleteness']} / 100",
        f"- Deterministic testchip yield passing: `{summary['deterministicYieldPassing']}`",
        f"- Yield improvement multiplier: `{summary['yieldImprovementMultiplier']}`",
        f"- Performance hardening complete: `{summary['performanceHardeningComplete']}`",
        f"- Performance hardening simulation-only: `{summary['performanceHardeningSimulationOnly']}`",
        "",
        "## Score Breakdown",
        "",
    ]
    for category, items in report["scoreBreakdown"].items():
        total = sum(item["points"] for item in items)
        maximum = sum(item["maxPoints"] for item in items)
        lines.append(f"- {category}: {total} / {maximum}")
        for item in items:
            state = "pass" if item["passed"] else "blocked"
            lines.append(f"  - {item['id']}: {item['points']} / {item['maxPoints']} ({state})")
    lines.extend(
        [
            "",
            "## Yield Evidence",
            "",
            f"- Current system-yield estimate: `{evidence['testchip']['systemYieldEstimate']}`",
            f"- Yield baseline: `{evidence['yieldImprovement']['baselineSystemYieldEstimate']}`",
            f"- Yield absolute gain: `{evidence['yieldImprovement']['absoluteSystemYieldGain']}`",
            f"- Yield accepted devices: `{evidence['testchip']['acceptedDeviceCount']} / {evidence['testchip']['requiredDeviceCount']}`",
            "",
            "## Performance Hardening",
            "",
            f"- Completion audit: `{evidence['performance']['completionAuditDecision']}`",
            f"- Best nominal fusion fidelity: `{evidence['performance']['bestNominalFusionFidelity']}`",
            f"- Truth-switch raw crosstalk: `{evidence['performance']['truthSwitchRawBestCrosstalkRatio']}`",
            f"- Truth-switch raw reflection: `{evidence['performance']['truthSwitchRawBestReflectionRatio']}`",
            f"- Stress scale at 1e-9: `{evidence['performance']['target1e9StressRecoveryScaleFactor']}`",
            f"- Max scaled layout area: `{evidence['performance']['maxScaledLayoutAreaMm2']}` mm^2",
            f"- Route-length reduction: `{evidence['performance']['maxScaledLayoutRouteReductionFraction']}`",
            "",
            "## Current Value Ranges",
            "",
        ]
    )
    for name, value in ranges.items():
        lines.append(f"- {name}: {value['low']} to {value['high']} {value['currency']}; midpoint {value['mid']}.")
    lines.extend(["", "## Risk Register", ""])
    for risk in report["diligenceRiskRegister"]:
        active = "active" if risk["active"] else "mitigated-or-not-current"
        lines.append(f"- {risk['id']} ({risk['severity']}, {active}): {risk['mitigation']}")
    lines.extend(["", "## Value Ladder", ""])
    for stage in report["valueLadder"]:
        value = stage["valueRange"]
        lines.append(f"- {stage['stage']}: {value['low']} to {value['high']} {value['currency']} after `{stage['entryGate']}`")
    lines.extend(
        [
            "",
            "## Hard Boundaries",
            "",
            "- Not prototype-ready.",
            "- Not tapeout-ready.",
            "- Virtual S-parameters do not close foundry compact-model gates.",
            "- Synthetic syndrome data do not prove hardware fault tolerance.",
        ]
    )
    return "\n".join(lines) + "\n"


def _partner_outreach_markdown(report: dict[str, Any]) -> str:
    evidence = report["evidenceSnapshot"]
    summary = report["summary"]
    return f"""# Partner Outreach Brief

## Short Email

Subject: Open photonic QC simulation package seeking independent validation

Hello,

I am maintaining OQP-HRM, an open simulation-first photonic quantum-computer
design package. It is not a build-ready chip. The current package has accepted
Node Alpha 20/60 2D candidates for the coupler, MZI, phase shifter, and truth
switch, public V3 hardening reports, and explicit evidence gates for foundry,
layout signoff, hardware, and lab validation.

The useful ask is narrow: could your group review one part of the package and
tell us which assumption would fail first in a real photonics flow?

Key artifacts:

- `reports/node-alpha/deep-hardening-v3-20260502/device-sweep-deep-hardening-v3.json`
- `reports/node-alpha/deep-hardening-v3-20260502/worst-case-corner-sweep-report.json`
- `reports/node-alpha/deep-hardening-v3-20260502/scaled-layout-envelope-report.json`
- `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.json`
- `reports/node-alpha/qc-path/sparameter-audit.json`
- `docs/30-minute-reproduction.md`

Current claim boundary: simulation package only; no prototype, no tapeout
readiness, no hardware fault-tolerance claim.

## Reviewer Ask Options

- Device-metric review.
- Generic layout envelope to PDK gap review.
- S-parameter replacement plan.
- Testchip yield stress review.
- Fault-tolerance assumption review.

## Evidence Snapshot

- High-resolution status: `{evidence['highResolution']['status']}`
- Accepted devices: `{', '.join(evidence['highResolution']['acceptedDevices'])}`
- Public Deep-Hardening V3 max modes: `{evidence['performance']['maxScaledPhysicalModes']}`
- Public Deep-Hardening V3 max logical qubits: `{evidence['performance']['maxScaledLogicalQubits']}`
- Partner diligence readiness: `{summary['partnerDiligenceReadiness']} / 100`
- Prototype status: `{evidence['prototype']['status']}`
- Highest blocker: `{evidence['prototype']['highestPriorityBlocker']}`
"""


def _grant_concept_markdown(report: dict[str, Any]) -> str:
    ranges = report["valuationRanges"]["grantLeverageTarget"]
    evidence = report["evidenceSnapshot"]
    return f"""# Grant Concept Note

## Project

OQP-HRM Foundry-Validation Path for a Heralded Photonic Quantum-Computer
Testchip

## Funding Target

Order-of-magnitude non-dilutive target: `{ranges['low']}` to `{ranges['high']}`
USD/EUR equivalent, with a midpoint around `{ranges['mid']}`.

## Problem

The repository has a reproducible simulation package, but the value is capped by
missing foundry-calibrated S-parameters, PDK signoff, and measured testchip data.
The current deterministic testchip yield stress passes with system yield
`{evidence['testchip']['systemYieldEstimate']}`, but that remains a simulated
tolerance-grid result rather than wafer statistics.

## Objective

Convert the current Node Alpha simulation package into a foundry-reviewable and
measurement-ready testchip package without claiming full quantum-computer
prototype readiness.

## Work Packages

1. Independent 3D/MPB/S-parameter review of four core device candidates.
2. Foundry PDK mapping and first DRC/LVS gap report for the generic GDS.
3. Compact-model replacement for virtual S-parameters.
4. Testchip measurement plan for source, detector, package, and feed-forward
   gates.
5. Hardware-calibrated noise model replacing synthetic syndrome assumptions.

## Success Criteria

- `sparameter-audit` accepts foundry-calibrated models for all four core devices.
- `gds-audit` is tied to a versioned foundry PDK and DRC/LVS report.
- `fault-tolerance-audit` receives hardware-calibrated noise data.
- Prototype readiness remains blocked unless evidence actually exists.

## Current De-Risked Base

- High-resolution device closure: `{evidence['highResolution']['status']}`
- Deterministic yield improvement multiplier: `{evidence['yieldImprovement']['relativeSystemYieldMultiplier']}`
- Report-index missing artifacts: `{evidence['reportIndex']['missingArtifactCount']}`
"""


def _data_room_markdown(report: dict[str, Any]) -> str:
    refs = report["artifactRefs"]
    lines = [
        "# OQP-HRM Data Room Index",
        "",
        "## Decision Documents",
        "",
        f"- Value scorecard: `{refs['scorecardJson']}`",
        f"- Partner outreach: `{refs['partnerOutreach']}`",
        f"- Grant concept: `{refs['grantConceptNote']}`",
        f"- Reviewer pack: `{refs['reviewerPack']}`",
        f"- Partner pipeline: `{refs['partnerPipeline']}`",
        "- No-budget package: `docs/no-budget-partner-package.md`",
        "- Reproduction guide: `docs/30-minute-reproduction.md`",
        "",
        "## Technical Evidence",
        "",
        "- Device sweep: `reports/node-alpha/deep-hardening-v3-20260502/device-sweep-deep-hardening-v3.json`",
        "- Truth-switch raw closure: `reports/node-alpha/deep-hardening-v3-20260502/truth-switch-raw-closure-report.json`",
        "- Fusion candidates: `reports/node-alpha/deep-hardening-v3-20260502/fusion-performance-candidates.json`",
        "- Deep-Hardening V3 Max-Out: `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.json`",
        "- Operational envelope: `reports/node-alpha/deep-hardening-v3-20260502/operational-envelope-report.json`",
        "- Joint error budget: `reports/node-alpha/deep-hardening-v3-20260502/joint-error-budget-report.json`",
        "- Budget optimizer: `reports/node-alpha/deep-hardening-v3-20260502/budget-optimizer-report.json`",
        "- Throughput report: `reports/node-alpha/deep-hardening-v3-20260502/throughput-report.json`",
        "- Virtual S-parameter acceptance: `reports/node-alpha/deep-hardening-v3-20260502/virtual-sparameter-acceptance-report.json`",
        "- Scaled layout envelope: `reports/node-alpha/deep-hardening-v3-20260502/scaled-layout-envelope-report.json`",
        "- Max-qubit envelope: `reports/node-alpha/deep-hardening-v3-20260502/max-qubit-envelope-report.json`",
        "- Max-qubit No-Go map: `reports/node-alpha/deep-hardening-v3-20260502/max-qubit-no-go-map-report.json`",
        "- Stress recovery: `reports/node-alpha/deep-hardening-v3-20260502/stress-recovery-report.json`",
        "- Control timing model: `reports/node-alpha/deep-hardening-v3-20260502/control-timing-model-report.json`",
        "- Decoder evidence: `reports/node-alpha/deep-hardening-v3-20260502/decoder-evidence-report.json`",
        "- Truth-switch raw closure: `reports/node-alpha/deep-hardening-v3-20260502/truth-switch-raw-closure-report.json`",
        "- Pareto/corner/Monte-Carlo: `reports/node-alpha/deep-hardening-v3-20260502/multiobjective-pareto-report.json`, `reports/node-alpha/deep-hardening-v3-20260502/worst-case-corner-sweep-report.json`, `reports/node-alpha/deep-hardening-v3-20260502/monte-carlo-robustness-report.json`",
        "- Prototype gap reduction: `reports/node-alpha/deep-hardening-v3-20260502/prototype-gap-reduction-report.json`",
        "- Artifact manifest: `ARTIFACTS.md`",
        "- S-parameter audit: `reports/node-alpha/qc-path/sparameter-audit.json`",
        "- Report index and hashes: `reports/node-alpha/report-index.json`",
        "",
        "## Missing External Evidence",
        "",
        "- Foundry PDK manifest.",
        "- DRC and LVS reports.",
        "- Foundry-calibrated S-parameters.",
        "- Hardware source/detector/package/control evidence.",
        "- Hardware-calibrated syndrome/noise dataset.",
        "- Measured testchip results.",
        "",
        "## Claim-Readiness Summary",
        "",
    ]
    for claim in report["claimReadinessMatrix"]:
        lines.append(f"- {claim['id']}: {claim['status']}")
    return "\n".join(lines) + "\n"


def _reviewer_pack_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# OQP-HRM Reviewer Pack",
        "",
        "This pack turns the scorecard into concrete technical review questions.",
        "It is designed to collect external diligence evidence without making hardware claims.",
        "",
        "## Assumption Register",
        "",
    ]
    for item in report["assumptionRegister"]:
        lines.append(f"- {item['id']}: {item['status']}; validation needed: {item['validationNeeded']}")
    lines.extend(["", "## Reviewer Questions", ""])
    for item in report["reviewerQuestionBank"]:
        lines.append(f"- {item['reviewerType']}: {item['question']} Artifact: `{item['artifact']}`")
    lines.extend(["", "## Required Review Output", ""])
    lines.extend(
        [
            "- One paragraph on whether the artifact is internally coherent.",
            "- One paragraph on the first assumption likely to fail in real hardware/foundry flow.",
            "- One recommended next experiment or report that can be done before paid tapeout.",
        ]
    )
    return "\n".join(lines) + "\n"


def _partner_pipeline_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# OQP-HRM Partner Pipeline",
        "",
        "Goal: convert the no-budget scorecard into external review evidence and grant leverage.",
        "",
        "## Pipeline",
        "",
    ]
    for item in report["partnerPipeline"]:
        cash = "no cash" if not item["cashRequired"] else "cash needed"
        lines.append(f"- {item['stage']} ({cash}): {item['goal']} Success metric: {item['successMetric']}")
    lines.extend(["", "## Current Assets", ""])
    summary = report["summary"]
    lines.extend(
        [
            f"- Internal simulation evidence score: `{summary['technicalEvidenceScore']} / 100`",
            "- External hardware evidence score: blocked/not scored as validated hardware",
            f"- Partner diligence readiness: `{summary['partnerDiligenceReadiness']} / 100`",
            f"- Scorecard completeness: `{summary['scorecardCompleteness']} / 100`",
            f"- Deterministic yield passing: `{summary['deterministicYieldPassing']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _first_json(paths: list[Path]) -> dict[str, Any]:
    for path in paths:
        report = _read_json(path)
        if report:
            return report
    return {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
