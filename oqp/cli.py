"""Command line interface for OQP-HRM tools."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .blueprint import load_blueprint
from .report import format_text_report, write_json_report
from .sweep import generate_grid_candidates, generate_optimizer_candidates, run_candidates


def _csv_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def _csv_floats(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def _csv_strings(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def validate_command(args: argparse.Namespace) -> int:
    from .simulator_sf import simulate_blueprint

    report = simulate_blueprint(load_blueprint(args.blueprint))
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_text_report(report))
    return 0


def sweep_command(args: argparse.Namespace) -> int:
    base = load_blueprint(args.blueprint)
    candidates = generate_grid_candidates(
        base,
        waveguides=_csv_ints(args.waveguides),
        interferometers=_csv_ints(args.interferometers),
        strides=_csv_ints(args.strides),
    )
    ranked = run_candidates(candidates, args.out)
    print(f"Completed {len(ranked)} candidates. Champion: {Path(args.out) / 'champion.json'}")
    if ranked:
        best = ranked[0]
        metrics = best["observedMetrics"]
        print(
            "Best "
            f"{best['candidateId']}: score={metrics['architectureScore']:.3f}, "
            f"yield={metrics['reconstructedAverageHeraldingYieldPercent']:.1f}%, "
            f"loss={metrics['totalMeshPathLossFromAttenuationScoreDb']:.3f} dB"
        )
    return 0


def optimize_command(args: argparse.Namespace) -> int:
    base = load_blueprint(args.blueprint)
    candidates = generate_optimizer_candidates(base, args.budget)
    ranked = run_candidates(candidates, args.out)
    print(f"Completed optimizer budget {len(ranked)}. Champion: {Path(args.out) / 'champion.json'}")
    if ranked:
        best = ranked[0]
        metrics = best["observedMetrics"]
        print(
            "Best "
            f"{best['candidateId']}: score={metrics['architectureScore']:.3f}, "
            f"yield={metrics['reconstructedAverageHeraldingYieldPercent']:.1f}%, "
            f"components={best['spatialModel']['modeGraphConnectedComponents']}, "
            f"loss={metrics['totalMeshPathLossFromAttenuationScoreDb']:.3f} dB"
        )
    return 0


def rank_command(args: argparse.Namespace) -> int:
    index = json.loads((Path(args.runs) / "index.json").read_text(encoding="utf-8"))
    for position, result in enumerate(index["results"][: args.limit], start=1):
        metrics = result["observedMetrics"]
        print(
            f"{position}. {result['candidateId']} "
            f"score={metrics['architectureScore']:.3f} "
            f"yield={metrics['reconstructedAverageHeraldingYieldPercent']:.1f}% "
            f"components={result['spatialModel']['modeGraphConnectedComponents']}"
        )
    return 0


def meep_probe_command(args: argparse.Namespace) -> int:
    from .meep_probe import run_meep_probe

    report = run_meep_probe()
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("=== OQP MEEP/FDTD Probe ===")
        print(f"Backend: {report['backend']}")
        print(f"MEEP version: {report['meepVersion']}")
        print(f"Resolution: {report['resolution']}")
        print(f"Duration: {report['durationSeconds']}s")
    return 0


def meep_run_command(args: argparse.Namespace) -> int:
    from .meep_runner import run_meep_blueprint

    report = run_meep_blueprint(
        load_blueprint(args.blueprint),
        resolution=args.resolution,
        until=args.until,
        max_lanes=args.max_lanes,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        metrics = report["fdtdMetrics"]
        spatial = report["spatialModel"]
        print("=== OQP MEEP/FDTD Surrogate Report ===")
        print(f"MEEP version: {report['meepVersion']}")
        print(f"Represented lanes: {spatial['representedLanes']} / {spatial['waveguideCount']}")
        print(f"Transmission ratio: {metrics['transmissionRatio']:.4f}")
        print(f"Reflection ratio: {metrics['reflectionRatio']:.4f}")
        print("Surrogate: yes")
    return 0


def layout_plan_command(args: argparse.Namespace) -> int:
    from .layout_plan import generate_layout_plan

    report = generate_layout_plan(
        load_blueprint(args.blueprint),
        lane_pitch_um=args.lane_pitch_um,
        mzi_pitch_um=args.mzi_pitch_um,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        spatial = report["spatialModel"]
        print("=== OQP Layout Plan ===")
        print(f"Modes: {spatial['waveguideCount']}")
        print(f"MZI cells: {len(report['mziCells'])}")
        print(f"Connected components: {spatial['connectedComponents']}")
        print(f"GDS ready: {report['gdsReady']}")
    return 0


def gds_plan_command(args: argparse.Namespace) -> int:
    from .gds import generate_gds_plan

    report = generate_gds_plan(
        load_blueprint(args.blueprint),
        pdk=args.pdk,
        evidence_dir=args.evidence_dir,
        device_reports=args.device_report,
        lane_pitch_um=args.lane_pitch_um,
        mzi_pitch_um=args.mzi_pitch_um,
        fiber_pitch_um=args.fiber_pitch_um,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        layout = report["topLevelLayout"]
        print("=== OQP GDS Plan ===")
        print(f"Top cell: {report['topCell']}")
        print(f"Chip: {layout['chipSizeUm']['width']:.1f} x {layout['chipSizeUm']['height']:.1f} um")
        print(f"Cells: {len(report['cellRegistry'])}")
        print(f"Layout computable: {report['layoutComputable']}")
    return 0


def gds_generate_command(args: argparse.Namespace) -> int:
    from .gds import generate_gds_artifacts

    report = generate_gds_artifacts(
        load_blueprint(args.blueprint),
        out_dir=args.out_dir,
        gds_out=args.gds_out,
        pdk=args.pdk,
        evidence_dir=args.evidence_dir,
        device_reports=args.device_report,
        lane_pitch_um=args.lane_pitch_um,
        mzi_pitch_um=args.mzi_pitch_um,
        fiber_pitch_um=args.fiber_pitch_um,
        include_preview=not args.no_preview,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["manifestSummary"]
        print("=== OQP GDS Generated ===")
        print(f"GDS: {report['gdsFile']['path']}")
        print(f"Chip: {summary['chipSizeUm']['width']:.1f} x {summary['chipSizeUm']['height']:.1f} um")
        print(f"Instances: {summary['instanceCount']} Ports: {summary['portCount']} Pads: {summary['padCount']}")
        print(f"Tapeout ready: {not report['readinessFlags']['not_tapeout_ready']}")
    return 0


def gds_manifest_command(args: argparse.Namespace) -> int:
    from .gds import generate_gds_manifest

    report = generate_gds_manifest(
        load_blueprint(args.blueprint),
        pdk=args.pdk,
        evidence_dir=args.evidence_dir,
        device_reports=args.device_report,
        lane_pitch_um=args.lane_pitch_um,
        mzi_pitch_um=args.mzi_pitch_um,
        fiber_pitch_um=args.fiber_pitch_um,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("=== OQP GDS Manifest ===")
        print(f"Top cell: {report['topCell']}")
        print(f"Instances: {len(report['instances'])}")
        print(f"Ports: {len(report['ports'])}")
        print(f"Pads: {len(report['pads'])}")
    return 0


def gds_audit_command(args: argparse.Namespace) -> int:
    from .gds import generate_gds_audit

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8")) if args.manifest else None
    report = generate_gds_audit(
        None if manifest else load_blueprint(args.blueprint),
        manifest=manifest,
        pdk=args.pdk,
        evidence_dir=args.evidence_dir,
        device_reports=args.device_report,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        flags = report["auditFlags"]
        print("=== OQP GDS Audit ===")
        print(f"GDS generated: {flags['gds_generated']}")
        print(f"Layout computable: {flags['layout_computable']}")
        print(f"FDTD gap placeholders: {flags['fdtd_gap_backed_placeholder']}")
        print(f"Tapeout ready: {not flags['not_tapeout_ready']}")
    return 0


def gds_preview_command(args: argparse.Namespace) -> int:
    from .gds import generate_gds_manifest, write_gds_preview

    manifest = (
        json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        if args.manifest
        else generate_gds_manifest(
            load_blueprint(args.blueprint),
            pdk=args.pdk,
            evidence_dir=args.evidence_dir,
            device_reports=args.device_report,
            lane_pitch_um=args.lane_pitch_um,
            mzi_pitch_um=args.mzi_pitch_um,
            fiber_pitch_um=args.fiber_pitch_um,
        )
    )
    report = write_gds_preview(manifest, args.svg_out)
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"GDS preview SVG: {report['previewSvg']}")
    return 0


def device_acceptance_command(args: argparse.Namespace) -> int:
    from .prototype_readiness import generate_device_acceptance_audit

    report = generate_device_acceptance_audit(
        load_blueprint(args.blueprint),
        evidence_dir=args.evidence_dir,
        device_reports=args.device_report,
        min_useful_transmission=args.min_useful_transmission,
        max_insertion_loss_db=args.max_insertion_loss_db,
        max_reflection_ratio=args.max_reflection_ratio,
        max_crosstalk_ratio=args.max_crosstalk_ratio,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print("=== OQP Device Acceptance Audit ===")
        print(f"Accepted devices: {summary['acceptedDeviceCount']} / {summary['requiredDeviceCount']}")
        print(f"FDTD gap placeholders: {summary['fdtdGapBackedPlaceholderCount']}")
        print(f"Core devices accepted: {summary['allCoreDevicesAccepted']}")
    return 0


def prototype_readiness_command(args: argparse.Namespace) -> int:
    from .prototype_readiness import generate_prototype_readiness

    report = generate_prototype_readiness(
        load_blueprint(args.blueprint),
        artifact_root=args.artifact_root,
        evidence_dir=args.evidence_dir,
        sparameter_audit_path=args.sparameter_audit,
        gds_audit_path=args.gds_audit,
        pdk_audit_path=args.pdk_audit,
        signoff_audit_path=args.signoff_audit,
        hardware_audit_path=args.hardware_audit,
        primitive_demo_audit_path=args.primitive_demo_audit,
        fault_tolerance_audit_path=args.fault_tolerance_audit,
        threshold_report_path=args.threshold_report,
        control_report_path=args.control_report,
        lab_report_path=args.lab_report,
        fusion_report_path=args.fusion_report,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print("=== OQP Prototype Readiness ===")
        print(f"Status: {summary['status']}")
        print(f"Complete criteria: {summary['completeCriteria']} / {summary['totalCriteria']}")
        print(f"Top blocker: {summary['highestPriorityBlocker']}")
    return 0


def evidence_bundle_command(args: argparse.Namespace) -> int:
    from .evidence_bundle import generate_evidence_bundle

    report = generate_evidence_bundle(
        load_blueprint(args.blueprint),
        artifact_root=args.artifact_root,
        write_templates=args.write_templates,
        templates_dir=args.templates_dir,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        flags = report["readinessFlags"]
        print("=== OQP Evidence Bundle ===")
        print(f"Artifact root: {report['artifactRoot']}")
        print(f"Present artifacts: {summary['presentArtifactCount']} / {summary['requiredArtifactCount']}")
        print(f"Prototype evidence complete: {flags['prototype_evidence_complete']}")
    return 0


def design_dossier_command(args: argparse.Namespace) -> int:
    from .design_dossier import generate_design_dossier

    report = generate_design_dossier(
        load_blueprint(args.blueprint),
        artifact_root=args.artifact_root,
        encoding=args.encoding,
        primitive=args.primitive,
        shots=args.shots,
        feed_forward_latency_ns=args.feed_forward_latency_ns,
        target_logical_error_rate=args.target_logical_error_rate,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        flags = report["readinessFlags"]
        print("=== OQP Design Dossier ===")
        print(f"Status: {summary['status']}")
        print(f"Closed layers: {summary['closedLayerCount']} / {summary['totalLayerCount']}")
        print(f"Prototype ready: {flags['prototype_ready']}")
        print(f"Complete quantum computer: {all(flags[name] for name in ['prototype_ready', 'tapeout_ready', 'hardware_evidence_complete', 'fault_tolerance_ready', 'experimental_primitive_demonstrated'])}")
    return 0


def node_alpha_closure_command(args: argparse.Namespace) -> int:
    from .node_alpha import generate_node_alpha_closure

    report = generate_node_alpha_closure(
        load_blueprint(args.blueprint),
        artifact_root=args.artifact_root,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        flags = report["readinessFlags"]
        print("=== OQP Node Alpha Closure ===")
        print(f"Status: {summary['status']}")
        print(f"Complete local items: {summary['completeLocalItemCount']} / {summary['totalLocalItemCount']}")
        print(f"Node Alpha maxed: {flags['node_alpha_maxed_without_realworld_input']}")
        print(f"Complete quantum computer: {flags['complete_quantum_computer']}")
    return 0


def node_alpha_compute_report_command(args: argparse.Namespace) -> int:
    from .node_alpha_compute import generate_node_alpha_compute_report

    report = generate_node_alpha_compute_report(
        load_blueprint(args.blueprint),
        device_sweep_path=args.device_sweep,
        threshold_sweep_path=args.threshold_sweep,
        resource_sweep_path=args.resource_sweep,
        closure_path=args.closure,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print("=== OQP Node Alpha Compute Report ===")
        print(f"Device runs: {summary['deviceRunCount']}")
        print(f"Threshold runs: {summary['thresholdRunCount']}")
        print(f"Resource runs: {summary['resourceRunCount']}")
        print(f"Threshold status: {summary['thresholdStatus']}")
    return 0


def complete_simulation_command(args: argparse.Namespace) -> int:
    from .complete_simulation import run_complete_simulation

    report = run_complete_simulation(
        load_blueprint(args.blueprint),
        artifact_root=args.artifact_root,
        device_sweep_path=args.device_sweep,
        threshold_sweep_path=args.threshold_sweep,
        resource_sweep_path=args.resource_sweep,
        compute_report_path=args.compute_report,
        closure_path=args.closure,
        design_dossier_path=args.design_dossier,
        encoding=args.encoding,
        primitive=args.primitive,
        shots=args.shots,
        feed_forward_latency_ns=args.feed_forward_latency_ns,
        target_logical_error_rate=args.target_logical_error_rate,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        flags = report["readinessFlags"]
        print("=== OQP Complete Simulation ===")
        print(f"Status: {summary['status']}")
        print(f"Simulated layers: {summary['simulatedLayerCount']} / {summary['totalLayerCount']}")
        print(f"Failed gates: {summary['failedGateCount']}")
        print(f"Simulated quantum computer complete: {flags['simulatedQuantumComputerComplete']}")
        print(f"Threshold candidate found: {flags['belowThresholdCandidateFound']}")
    return 0


def testchip_simulation_command(args: argparse.Namespace) -> int:
    from .testchip_simulation import run_testchip_simulation

    report = run_testchip_simulation(
        load_blueprint(args.blueprint),
        out_dir=args.out_dir,
        device_sweep_path=args.device_sweep,
        wavelengths_nm=_csv_floats(args.wavelengths_nm),
        width_errors_nm=_csv_floats(args.width_errors_nm),
        gap_errors_nm=_csv_floats(args.gap_errors_nm),
        phase_errors_rad=_csv_floats(args.phase_errors_rad),
        temperature_deltas_c=_csv_floats(args.temperature_deltas_c),
        shots=args.shots,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        flags = report["readinessFlags"]
        print("=== OQP Testchip Simulation ===")
        print(f"Status: {summary['status']}")
        print(f"Device status: {summary['deviceStatus']}")
        print(f"Virtual S-parameter models: {summary['virtualSparameterModelCount']}")
        print(f"Yield devices accepted: {summary['yieldAcceptedDeviceCount']} / {summary['yieldRequiredDeviceCount']}")
        print(f"Fusion status: {summary['fusionStatus']}")
        print(f"Ready for fabrication: {flags['readyForFabrication']}")
        print(f"Report: {Path(args.out_dir) / 'testchip-simulation.json'}")
    return 0


def value_package_command(args: argparse.Namespace) -> int:
    from .value_package import generate_value_package

    report = generate_value_package(
        load_blueprint(args.blueprint),
        artifact_root=args.artifact_root,
        out_dir=args.out_dir,
        device_sweep_path=args.device_sweep,
        syndrome_event_count=args.syndrome_event_count,
        shots=args.shots,
        target_logical_error_rate=args.target_logical_error_rate,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print("=== OQP Value Upgrade Package ===")
        print(f"Status: {summary['status']}")
        print(f"Testchip status: {summary['testchipStatus']}")
        print(f"Virtual S-parameter models: {summary['virtualSparameterModelCount']}")
        print(f"Threshold status: {summary['thresholdStatus']}")
        print(f"Fault tolerance ready: {summary['faultToleranceReady']}")
        print(f"Prototype status: {summary['prototypeStatus']}")
        print(f"Report: {Path(args.out_dir) / 'value-upgrade-report.json'}")
    return 0


def value_scorecard_command(args: argparse.Namespace) -> int:
    from .value_scorecard import generate_value_scorecard

    report = generate_value_scorecard(
        load_blueprint(args.blueprint),
        artifact_root=args.artifact_root,
        out_dir=args.out_dir,
        docs_dir=args.docs_dir,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print("=== OQP Value Scorecard ===")
        print(f"Status: {summary['status']}")
        print(f"Technical evidence score: {summary['technicalEvidenceScore']} / 100")
        print(f"Partner diligence readiness: {summary['partnerDiligenceReadiness']} / 100")
        print(f"Commercial readiness: {summary['currentCommercialReadiness']} / 100")
        print(f"Immediate sale range: {summary['immediateSaleRange']}")
        print(f"Partner package range: {summary['partnerPackageRange']}")
        print(f"Report: {Path(args.out_dir) / 'value-scorecard.json'}")
    return 0


def performance_upgrade_command(args: argparse.Namespace) -> int:
    from .performance_upgrade import generate_performance_upgrade

    report = generate_performance_upgrade(
        load_blueprint(args.blueprint),
        artifact_root=args.artifact_root,
        out_dir=args.out_dir,
        focused_max_runs=args.focused_max_runs,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print("=== OQP Deep-Hardening V3 Max-Out ===")
        print(f"Status: {summary['status']}")
        print(f"Max scaled logical qubits: {summary['maxScaledLogicalQubits']}")
        print(f"Target 1e-8 logical error met: {summary['target1e8LogicalErrorMet']}")
        print(f"Target 1e-9 logical error met: {summary['target1e9LogicalErrorMet']}")
        print(f"Fusion target met nominal: {summary['fusionTargetMetInNominalScenario']}")
        print(f"Fusion stretch target met: {summary['fusionStretchTargetMet']}")
        print(f"Truth-switch strict target met: {summary['truthSwitchStrictTargetMet']}")
        print(f"Virtual S-parameter accepted devices: {summary['virtualSparameterAcceptedDeviceCount']}")
        stress_scale = summary["target1e9StressRecoveryScaleFactor"]
        print(f"Target 1e-9 stress recovery scale: {stress_scale:.6g}" if stress_scale is not None else "Target 1e-9 stress recovery scale: n/a")
        print(f"Target 1e-9 control timing pass: {summary['target1e9ControlTimingPass']}")
        print(f"Report: {Path(args.out_dir) / 'deep-hardening-v3-report.json'}")
    return 0


def encoding_command(args: argparse.Namespace) -> int:
    from .encoding import generate_encoding_spec

    report = generate_encoding_spec(load_blueprint(args.blueprint), encoding=args.encoding)
    if args.out:
        write_json_report(report, args.out)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else f"Encoding {report['encoding']} logical capacity: {report['logicalQubitCapacity']}")
    return 0


def compile_command(args: argparse.Namespace) -> int:
    from .compiler import compile_blueprint

    report = compile_blueprint(load_blueprint(args.blueprint), shots=args.shots, encoding=args.encoding)
    if args.out:
        write_json_report(report, args.out)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else f"Compiled {report['instructionCount']} instructions for {report['shots']} shots")
    return 0


def runtime_trace_command(args: argparse.Namespace) -> int:
    from .compiler import compile_blueprint, runtime_trace

    compiled = compile_blueprint(load_blueprint(args.blueprint), shots=args.shots, encoding=args.encoding)
    report = runtime_trace(compiled, feed_forward_latency_ns=args.feed_forward_latency_ns)
    if args.out:
        write_json_report(report, args.out)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else f"Runtime per shot: {report['totalProgramTimeNsPerShot']:.3f} ns")
    return 0


def error_budget_command(args: argparse.Namespace) -> int:
    from .error_budget import generate_error_budget

    report = generate_error_budget(
        load_blueprint(args.blueprint),
        source_efficiency=args.source_efficiency,
        detector_efficiency=args.detector_efficiency,
        dark_count_rate_hz=args.dark_count_rate_hz,
        feed_forward_latency_ns=args.feed_forward_latency_ns,
        phase_error_rad=args.phase_error_rad,
    )
    if args.out:
        write_json_report(report, args.out)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else f"End-to-end loss: {report['totalEndToEndLossDb']:.3f} dB")
    return 0


def layout_readiness_command(args: argparse.Namespace) -> int:
    from .layout_readiness import generate_layout_readiness

    report = generate_layout_readiness(load_blueprint(args.blueprint), pdk=args.pdk)
    if args.out:
        write_json_report(report, args.out)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else f"Layout ready: {report['gdsReady']} Tapeout ready: {report['tapeoutReady']}")
    return 0


def pdk_audit_command(args: argparse.Namespace) -> int:
    from .pdk import generate_pdk_audit

    report = generate_pdk_audit(
        load_blueprint(args.blueprint),
        pdk=args.pdk,
        pdk_manifest=args.pdk_manifest,
        gds_audit_path=args.gds_audit,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        flags = report["readinessFlags"]
        print("=== OQP Foundry PDK Audit ===")
        print(f"Selected PDK: {report['selectedPdk']}")
        print(f"Foundry locked: {flags['foundry_pdk_locked']}")
        print(f"PDK ready: {flags['pdk_ready']}")
        print(f"DRC/LVS runnable: {flags['drc_lvs_runnable']}")
    return 0


def sparameter_audit_command(args: argparse.Namespace) -> int:
    from .sparameters import generate_sparameter_audit

    report = generate_sparameter_audit(
        load_blueprint(args.blueprint),
        model_manifest_path=args.model_manifest,
        min_wavelength_nm=args.min_wavelength_nm,
        max_wavelength_nm=args.max_wavelength_nm,
        max_insertion_loss_db=args.max_insertion_loss_db,
        max_reflection_ratio=args.max_reflection_ratio,
        max_crosstalk_ratio=args.max_crosstalk_ratio,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        flags = report["readinessFlags"]
        print("=== OQP S-Parameter Audit ===")
        print(f"Models ready: {flags['sparameter_models_ready']}")
        print(f"Accepted models: {report['summary']['acceptedDeviceCount']} / {report['summary']['requiredDeviceCount']}")
        print(f"Hashes verified: {flags['all_hashes_verified']}")
    return 0


def signoff_audit_command(args: argparse.Namespace) -> int:
    from .signoff import generate_signoff_audit

    report = generate_signoff_audit(
        load_blueprint(args.blueprint),
        gds_audit_path=args.gds_audit,
        pdk_audit_path=args.pdk_audit,
        drc_report_path=args.drc_report,
        lvs_report_path=args.lvs_report,
        waiver_report_path=args.waiver_report,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        flags = report["readinessFlags"]
        print("=== OQP DRC/LVS Signoff Audit ===")
        print(f"DRC clean or waived: {flags['drc_clean_or_waived']}")
        print(f"LVS clean or waived: {flags['lvs_clean_or_waived']}")
        print(f"Signoff ready: {flags['signoff_ready']}")
    return 0


def meep_device_command(args: argparse.Namespace) -> int:
    from .meep_device import run_meep_device

    report = run_meep_device(
        load_blueprint(args.blueprint),
        device=args.device,
        resolution=args.resolution,
        until=args.until,
        coupling_gap_um=args.coupling_gap_um,
        coupling_length_um=args.coupling_length_um,
        phase_shift_rad=args.phase_shift_rad,
        waveguide_width_um=args.waveguide_width_um,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        metrics = report["fdtdMetrics"]
        print("=== OQP MEEP Device FDTD Report ===")
        print(f"Device: {report['device']}")
        print(f"MEEP version: {report['meepVersion']}")
        print(f"Through ratio: {metrics['throughRatio']:.4f}")
        print(f"Cross ratio: {metrics['crossRatio']:.4f}")
        print(f"Insertion loss: {metrics['insertionLossDb']:.3f} dB")
    return 0


def eigenmode_device_command(args: argparse.Namespace) -> int:
    from .eigenmode_device import run_eigenmode_device

    report = run_eigenmode_device(
        load_blueprint(args.blueprint),
        device=args.device,
        resolution=args.resolution,
        until=args.until,
        coupling_gap_um=args.coupling_gap_um,
        coupling_length_um=args.coupling_length_um,
        phase_shift_rad=args.phase_shift_rad,
        waveguide_width_um=args.waveguide_width_um,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        metrics = report["fdtdMetrics"]
        print("=== OQP Eigenmode-Normalized Device FDTD Report ===")
        print(f"Device: {report['device']}")
        print(f"Source model: {report['sourceModel']}")
        print(f"Useful transmission: {metrics['usefulTransmission']:.4f}")
        print(f"Reflection ratio: {metrics['reflectionRatio']:.4f}")
        print(f"Insertion loss: {metrics['insertionLossDb']:.3f} dB")
        print(f"Status: {report['acceptanceStatus']}")
    return 0


def primitive_spec_command(args: argparse.Namespace) -> int:
    from .primitive import generate_primitive_spec

    report = generate_primitive_spec(load_blueprint(args.blueprint), encoding=args.encoding, primitive=args.primitive)
    if args.out:
        write_json_report(report, args.out)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else f"Primitive {report['primitive']} universality: {report['universalityStatus']}")
    return 0


def fusion_primitive_command(args: argparse.Namespace) -> int:
    from .primitive import generate_fusion_primitive

    device_report = None
    if args.device_report:
        device_report = json.loads(Path(args.device_report).read_text(encoding="utf-8"))
    report = generate_fusion_primitive(
        load_blueprint(args.blueprint),
        device_report=device_report,
        encoding=args.encoding,
        feed_forward_latency_ns=args.feed_forward_latency_ns,
        source_efficiency=args.source_efficiency,
        detector_efficiency=args.detector_efficiency,
    )
    if args.out:
        write_json_report(report, args.out)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else f"Fusion primitive status: {report['status']}")
    return 0


def primitive_demo_audit_command(args: argparse.Namespace) -> int:
    from .demo import generate_primitive_demo_audit

    report = generate_primitive_demo_audit(
        load_blueprint(args.blueprint),
        measurement_report_path=args.measurement_report,
        dataset_manifest_path=args.dataset_manifest,
        hardware_audit_path=args.hardware_audit,
        fusion_report_path=args.fusion_report,
        min_shots=args.min_shots,
        min_heralded_events=args.min_heralded_events,
        min_heralding_success_probability=args.min_heralding_success_probability,
        min_process_fidelity=args.min_process_fidelity,
        max_feed_forward_latency_ns=args.max_feed_forward_latency_ns,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        flags = report["readinessFlags"]
        print("=== OQP Primitive Demo Audit ===")
        print(f"Primitive demonstrated: {flags['primitive_demonstrated']}")
        print(f"Dataset verified: {flags['dataset_verified']}")
        print(f"Hardware ready: {flags['hardware_ready']}")
    return 0


def primitive_demo_ingest_command(args: argparse.Namespace) -> int:
    from .demo import ingest_primitive_demo_dataset

    report = ingest_primitive_demo_dataset(
        load_blueprint(args.blueprint),
        dataset_path=args.dataset,
        measurement_out=args.measurement_out,
        dataset_manifest_out=args.dataset_manifest_out,
        primitive=args.primitive,
        experimental_status=args.experimental_status,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print("=== OQP Primitive Demo Ingest ===")
        print(f"Records: {summary['recordCount']} Invalid: {summary['invalidRecordCount']}")
        print(f"Heralded events: {summary['heraldedEventCount']} / {summary['shotCount']}")
        print(f"Dataset manifest: {report['artifactRefs']['datasetManifest']}")
    return 0


def resource_model_command(args: argparse.Namespace) -> int:
    from .resource_model import generate_resource_model

    report = generate_resource_model(
        load_blueprint(args.blueprint),
        encoding=args.encoding,
        logical_qubits=args.logical_qubits,
        target_logical_error_rate=args.target_logical_error_rate,
    )
    if args.out:
        write_json_report(report, args.out)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else f"Resources for {report['logicalQubits']} logical qubits")
    return 0


def resource_sweep_command(args: argparse.Namespace) -> int:
    from .resource_sweep import run_resource_sweep

    report = run_resource_sweep(
        load_blueprint(args.blueprint),
        encoding=args.encoding,
        logical_qubits=_csv_ints(args.logical_qubits),
        target_logical_error_rates=_csv_floats(args.target_logical_error_rates),
        out_dir=args.out,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print("=== OQP Resource Sweep ===")
        print(f"Runs: {report['runCount']}")
        print(f"Logical qubits: {summary['minLogicalQubits']}..{summary['maxLogicalQubits']}")
        print(f"Max sources: {summary['maxSinglePhotonSources']}")
        print(f"Report: {Path(args.out) / 'resource-sweep.json'}")
    return 0


def device_sweep_command(args: argparse.Namespace) -> int:
    from .device_sweep import run_device_sweep

    report = run_device_sweep(
        load_blueprint(args.blueprint),
        devices=_csv_strings(args.devices),
        coupling_gaps_um=_csv_floats(args.coupling_gaps_um),
        coupling_lengths_um=_csv_floats(args.coupling_lengths_um),
        phase_shifts_rad=_csv_floats(args.phase_shifts_rad),
        waveguide_widths_um=_csv_floats(args.waveguide_widths_um),
        resolution=args.resolution,
        until=args.until,
        max_runs=args.max_runs,
        out_dir=args.out,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        champion = report["champion"]
        if champion:
            print(f"Device sweep champion: {champion['candidateId']} score={champion['score']:.3f} status={report['status']}")
        else:
            print("Device sweep produced no candidates")
    return 0


def device_sweep_rerank_command(args: argparse.Namespace) -> int:
    from .device_sweep import rerank_device_sweep

    report = rerank_device_sweep(
        load_blueprint(args.blueprint),
        evidence_dir=args.evidence_dir,
        devices=_csv_strings(args.devices),
        out=args.out,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        champion = report["champion"]
        print("=== OQP Device Sweep Rerank ===")
        print(f"Candidates: {report['runCount']}")
        print(f"Champion: {champion['candidateId'] if champion else 'none'}")
        print(f"Blocking metric: {report['gapSummary']['blockingMetric']}")
        print(f"Report: {args.out}")
    return 0


def error_correction_plan_command(args: argparse.Namespace) -> int:
    from .error_correction import generate_error_correction_plan

    report = generate_error_correction_plan(
        load_blueprint(args.blueprint),
        code=args.code,
        distance=args.distance,
        physical_error_rate=args.physical_error_rate,
        threshold=args.threshold,
    )
    if args.out:
        write_json_report(report, args.out)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else f"Error correction {report['code']} below threshold: {report['belowThreshold']}")
    return 0


def threshold_sweep_command(args: argparse.Namespace) -> int:
    from .threshold import run_threshold_sweep

    device_report = None
    if args.device_report:
        device_report = json.loads(Path(args.device_report).read_text(encoding="utf-8"))
    report = run_threshold_sweep(
        load_blueprint(args.blueprint),
        code=args.code,
        device_report=device_report,
        decoder_backend=args.decoder_backend,
        distances=_csv_ints(args.distances),
        physical_error_rates=_csv_floats(args.physical_error_rates),
        loss_values_db=_csv_floats(args.loss_values_db),
        detector_efficiencies=_csv_floats(args.detector_efficiencies),
        dark_count_rates_hz=_csv_floats(args.dark_count_rates_hz),
        phase_errors_rad=_csv_floats(args.phase_errors_rad),
        feed_forward_latencies_ns=_csv_floats(args.feed_forward_latencies_ns),
        threshold=args.threshold,
        max_runs=args.max_runs,
        out_dir=args.out,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        champion = report["champion"]
        if champion:
            print(
                "Threshold sweep champion: "
                f"{champion['candidateId']} logical_error={champion['estimatedLogicalErrorRatePerCycle']:.6g} "
                f"status={report['status']}"
            )
        else:
            print("Threshold sweep produced no candidates")
    return 0


def fault_tolerance_ingest_command(args: argparse.Namespace) -> int:
    from .fault_tolerance import ingest_fault_tolerance_dataset

    report = ingest_fault_tolerance_dataset(
        load_blueprint(args.blueprint),
        dataset_path=args.dataset,
        decoder_report_out=args.decoder_report_out,
        noise_dataset_manifest_out=args.noise_dataset_manifest_out,
        decoder=args.decoder,
        implementation_status=args.implementation_status,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print("=== OQP Fault-Tolerance Ingest ===")
        print(f"Records: {summary['recordCount']} Invalid: {summary['invalidRecordCount']}")
        print(f"Logical errors: {summary['logicalErrorCount']} rate={summary['validatedLogicalErrorRate']:.6g}")
        print(f"Dataset manifest: {report['artifactRefs']['noiseDatasetManifest']}")
    return 0


def fault_tolerance_audit_command(args: argparse.Namespace) -> int:
    from .fault_tolerance import generate_fault_tolerance_audit

    report = generate_fault_tolerance_audit(
        load_blueprint(args.blueprint),
        threshold_report_path=args.threshold_report,
        decoder_report_path=args.decoder_report,
        noise_dataset_manifest_path=args.noise_dataset,
        hardware_audit_path=args.hardware_audit,
        target_logical_error_rate=args.target_logical_error_rate,
        max_decoder_latency_ns=args.max_decoder_latency_ns,
        min_sampled_syndrome_events=args.min_sampled_syndrome_events,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        flags = report["readinessFlags"]
        print("=== OQP Fault-Tolerance Audit ===")
        print(f"Below threshold: {flags['below_threshold_evidence']}")
        print(f"Decoder implemented: {flags['decoder_implemented']}")
        print(f"Fault-tolerance ready: {flags['fault_tolerance_ready']}")
    return 0


def control_readiness_command(args: argparse.Namespace) -> int:
    from .readiness import generate_control_readiness

    report = generate_control_readiness(
        load_blueprint(args.blueprint),
        feed_forward_latency_ns=args.feed_forward_latency_ns,
        detector_jitter_ps=args.detector_jitter_ps,
    )
    if args.out:
        write_json_report(report, args.out)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else f"Control ready: {report['controlReady']}")
    return 0


def lab_readiness_command(args: argparse.Namespace) -> int:
    from .readiness import generate_lab_readiness

    report = generate_lab_readiness(
        load_blueprint(args.blueprint),
        detector_type=args.detector_type,
        laser_wavelength_nm=args.laser_wavelength_nm,
    )
    if args.out:
        write_json_report(report, args.out)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else f"Lab ready: {report['labReady']}")
    return 0


def hardware_ingest_command(args: argparse.Namespace) -> int:
    from .hardware import ingest_hardware_dataset

    report = ingest_hardware_dataset(
        load_blueprint(args.blueprint),
        dataset_path=args.dataset,
        source_out=args.source_out,
        detector_out=args.detector_out,
        packaging_out=args.packaging_out,
        control_out=args.control_out,
        calibration_out=args.calibration_out,
        feed_forward_out=args.feed_forward_out,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print("=== OQP Hardware Ingest ===")
        print(f"Records: {summary['recordCount']} Invalid: {summary['invalidRecordCount']}")
        print(f"Calibration loops: {summary['completedCalibrationCount']} / 6")
        print(f"Hardware-in-loop shots: {summary['hardwareInLoopShots']}")
    return 0


def hardware_audit_command(args: argparse.Namespace) -> int:
    from .hardware import generate_hardware_audit

    report = generate_hardware_audit(
        load_blueprint(args.blueprint),
        source_report_path=args.source_report,
        detector_report_path=args.detector_report,
        packaging_report_path=args.packaging_report,
        control_report_path=args.control_report,
        calibration_report_path=args.calibration_report,
        feed_forward_report_path=args.feed_forward_report,
    )
    if args.out:
        write_json_report(report, args.out)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        flags = report["readinessFlags"]
        print("=== OQP Hardware Audit ===")
        print(f"Hardware ready: {flags['hardware_ready']}")
        print(f"Calibration ready: {flags['automatic_calibration_ready']}")
        print(f"Feed-forward verified: {flags['feed_forward_verified']}")
    return 0


def tapeout_readiness_command(args: argparse.Namespace) -> int:
    from .tapeout_readiness import generate_tapeout_readiness

    report = generate_tapeout_readiness(
        load_blueprint(args.blueprint),
        pdk=args.pdk,
        feed_forward_latency_ns=args.feed_forward_latency_ns,
        detector_type=args.detector_type,
    )
    if args.out:
        write_json_report(report, args.out)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else f"Tapeout ready: {report['tapeoutReady']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oqp", description="Open Quantum Photonics HRM tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate one OQP-HRM blueprint")
    validate.add_argument("blueprint")
    validate.add_argument("--json", action="store_true", help="print JSON report")
    validate.add_argument("--out", help="write JSON report to path")
    validate.set_defaults(func=validate_command)

    sweep = subparsers.add_parser("sweep", help="run a grid sweep from a base blueprint")
    sweep.add_argument("blueprint")
    sweep.add_argument("--out", default="runs/sweep", help="output directory")
    sweep.add_argument("--waveguides", default="36", help="comma-separated mode counts")
    sweep.add_argument("--interferometers", default="24", help="comma-separated MZI counts")
    sweep.add_argument("--strides", default="3", help="comma-separated pairing strides")
    sweep.set_defaults(func=sweep_command)

    optimize = subparsers.add_parser("optimize", help="run deterministic optimizer candidates")
    optimize.add_argument("blueprint")
    optimize.add_argument("--out", default="runs/optimize", help="output directory")
    optimize.add_argument("--budget", type=int, default=20, help="maximum candidate count")
    optimize.set_defaults(func=optimize_command)

    rank = subparsers.add_parser("rank", help="rank a completed sweep directory")
    rank.add_argument("runs")
    rank.add_argument("--limit", type=int, default=10)
    rank.set_defaults(func=rank_command)

    meep_probe = subparsers.add_parser("meep-probe", help="verify MEEP/FDTD Python runtime")
    meep_probe.add_argument("--json", action="store_true", help="print JSON report")
    meep_probe.add_argument("--out", help="write JSON report to path")
    meep_probe.set_defaults(func=meep_probe_command)

    meep_run = subparsers.add_parser("meep-run", help="run surrogate MEEP/FDTD validation")
    meep_run.add_argument("blueprint")
    meep_run.add_argument("--json", action="store_true", help="print JSON report")
    meep_run.add_argument("--out", help="write JSON report to path")
    meep_run.add_argument("--resolution", type=int, default=10)
    meep_run.add_argument("--until", type=float, default=30)
    meep_run.add_argument("--max-lanes", type=int, default=8)
    meep_run.set_defaults(func=meep_run_command)

    layout_plan = subparsers.add_parser("layout-plan", help="write abstract layout plan for future GDS")
    layout_plan.add_argument("blueprint")
    layout_plan.add_argument("--json", action="store_true", help="print JSON report")
    layout_plan.add_argument("--out", help="write JSON report to path")
    layout_plan.add_argument("--lane-pitch-um", type=float, default=4.0)
    layout_plan.add_argument("--mzi-pitch-um", type=float, default=30.0)
    layout_plan.set_defaults(func=layout_plan_command)

    def add_gds_common(command: argparse.ArgumentParser) -> None:
        command.add_argument("blueprint")
        command.add_argument("--pdk", default="generic-si-photonics")
        command.add_argument("--evidence-dir", default="reports/node-alpha/qc-path")
        command.add_argument("--device-report", action="append", help="extra FDTD/device evidence JSON report")
        command.add_argument("--lane-pitch-um", type=float, default=18.0)
        command.add_argument("--mzi-pitch-um", type=float, default=160.0)
        command.add_argument("--fiber-pitch-um", type=float, default=127.0)
        command.add_argument("--json", action="store_true", help="print JSON report")
        command.add_argument("--out", help="write JSON report to path")

    gds_plan = subparsers.add_parser("gds-plan", help="compute PDK-aware generic-SiPh GDS plan")
    add_gds_common(gds_plan)
    gds_plan.set_defaults(func=gds_plan_command)

    gds_generate = subparsers.add_parser("gds-generate", help="write generic-SiPh OQP-HRM GDS and manifests")
    add_gds_common(gds_generate)
    gds_generate.add_argument("--out-dir", default="reports/node-alpha/gds-path")
    gds_generate.add_argument("--gds-out", help="write GDS to explicit path")
    gds_generate.add_argument("--no-preview", action="store_true", help="skip SVG preview generation")
    gds_generate.set_defaults(func=gds_generate_command)

    gds_manifest = subparsers.add_parser("gds-manifest", help="compute GDS cell/instance/port/pad manifest")
    add_gds_common(gds_manifest)
    gds_manifest.set_defaults(func=gds_manifest_command)

    gds_audit = subparsers.add_parser("gds-audit", help="audit generated or computable GDS readiness")
    add_gds_common(gds_audit)
    gds_audit.add_argument("--manifest", help="audit an existing gds-manifest JSON")
    gds_audit.set_defaults(func=gds_audit_command)

    gds_preview = subparsers.add_parser("gds-preview", help="write an SVG preview from a GDS manifest")
    add_gds_common(gds_preview)
    gds_preview.add_argument("--manifest", help="preview an existing gds-manifest JSON")
    gds_preview.add_argument("--svg-out", default="reports/node-alpha/gds-path/gds-preview.svg")
    gds_preview.set_defaults(func=gds_preview_command)

    device_acceptance = subparsers.add_parser("device-acceptance", help="audit core photonic device evidence against acceptance gates")
    device_acceptance.add_argument("blueprint")
    device_acceptance.add_argument("--evidence-dir", default="reports/node-alpha/qc-path")
    device_acceptance.add_argument("--device-report", action="append", help="extra FDTD/device evidence JSON report")
    device_acceptance.add_argument("--min-useful-transmission", type=float, default=0.5)
    device_acceptance.add_argument("--max-insertion-loss-db", type=float, default=1.0)
    device_acceptance.add_argument("--max-reflection-ratio", type=float, default=0.05)
    device_acceptance.add_argument("--max-crosstalk-ratio", type=float, default=0.05)
    device_acceptance.add_argument("--json", action="store_true", help="print JSON report")
    device_acceptance.add_argument("--out", help="write JSON report to path")
    device_acceptance.set_defaults(func=device_acceptance_command)

    prototype = subparsers.add_parser("prototype-readiness", help="audit OQP-HRM quantum-computer prototype readiness")
    prototype.add_argument("blueprint")
    prototype.add_argument("--artifact-root", default="reports/node-alpha")
    prototype.add_argument("--evidence-dir", default="reports/node-alpha/qc-path")
    prototype.add_argument("--sparameter-audit", default="reports/node-alpha/qc-path/sparameter-audit.json")
    prototype.add_argument("--gds-audit", default="reports/node-alpha/gds-path/gds-audit.json")
    prototype.add_argument("--pdk-audit", default="reports/node-alpha/gds-path/pdk-audit.json")
    prototype.add_argument("--signoff-audit", default="reports/node-alpha/gds-path/signoff-audit.json")
    prototype.add_argument("--hardware-audit", default="reports/node-alpha/qc-path/hardware-audit.json")
    prototype.add_argument("--primitive-demo-audit", default="reports/node-alpha/qc-path/primitive-demo-audit.json")
    prototype.add_argument("--fault-tolerance-audit", default="reports/node-alpha/qc-path/fault-tolerance-audit.json")
    prototype.add_argument("--threshold-report", default="reports/node-alpha/qc-path/threshold-sweep.json")
    prototype.add_argument("--control-report", default="reports/node-alpha/qc-path/control-readiness.json")
    prototype.add_argument("--lab-report", default="reports/node-alpha/qc-path/lab-readiness.json")
    prototype.add_argument("--fusion-report", default="reports/node-alpha/qc-path/fusion-primitive.json")
    prototype.add_argument("--json", action="store_true", help="print JSON report")
    prototype.add_argument("--out", help="write JSON report to path")
    prototype.set_defaults(func=prototype_readiness_command)

    evidence_bundle = subparsers.add_parser("evidence-bundle", help="audit and template the full prototype evidence intake bundle")
    evidence_bundle.add_argument("blueprint")
    evidence_bundle.add_argument("--artifact-root", default="reports/node-alpha")
    evidence_bundle.add_argument("--write-templates", action="store_true", help="write placeholder intake templates")
    evidence_bundle.add_argument("--templates-dir", help="directory for intake templates")
    evidence_bundle.add_argument("--json", action="store_true", help="print JSON report")
    evidence_bundle.add_argument("--out", help="write JSON report to path")
    evidence_bundle.set_defaults(func=evidence_bundle_command)

    design_dossier = subparsers.add_parser("design-dossier", help="write the full-stack OQP-HRM quantum-computer design dossier")
    design_dossier.add_argument("blueprint")
    design_dossier.add_argument("--artifact-root", default="reports/node-alpha")
    design_dossier.add_argument("--encoding", default="dual_rail", choices=["dual_rail", "cv_gkp"])
    design_dossier.add_argument(
        "--primitive",
        default="fusion_entangling",
        choices=["fusion_entangling", "klm_csign", "gkp_gate_teleportation"],
    )
    design_dossier.add_argument("--shots", type=int, default=1000)
    design_dossier.add_argument("--feed-forward-latency-ns", type=float, default=5.0)
    design_dossier.add_argument("--target-logical-error-rate", type=float, default=1e-6)
    design_dossier.add_argument("--json", action="store_true", help="print JSON report")
    design_dossier.add_argument("--out", help="write JSON report to path")
    design_dossier.set_defaults(func=design_dossier_command)

    node_alpha = subparsers.add_parser(
        "node-alpha-closure",
        help="audit everything Node Alpha can finish without real-world evidence",
    )
    node_alpha.add_argument("blueprint")
    node_alpha.add_argument("--artifact-root", default="reports/node-alpha")
    node_alpha.add_argument("--json", action="store_true", help="print JSON report")
    node_alpha.add_argument("--out", help="write JSON report to path")
    node_alpha.set_defaults(func=node_alpha_closure_command)

    node_alpha_compute = subparsers.add_parser(
        "node-alpha-compute-report",
        help="aggregate extended Node Alpha device, threshold, and resource calculations",
    )
    node_alpha_compute.add_argument("blueprint")
    node_alpha_compute.add_argument("--device-sweep", required=True)
    node_alpha_compute.add_argument("--threshold-sweep", required=True)
    node_alpha_compute.add_argument("--resource-sweep", required=True)
    node_alpha_compute.add_argument("--closure", default="reports/node-alpha/qc-path/node-alpha-closure.json")
    node_alpha_compute.add_argument("--json", action="store_true", help="print JSON report")
    node_alpha_compute.add_argument("--out", help="write JSON report to path")
    node_alpha_compute.set_defaults(func=node_alpha_compute_report_command)

    complete_simulation = subparsers.add_parser(
        "complete-simulation",
        help="run the complete available Node Alpha simulation stack",
    )
    complete_simulation.add_argument("blueprint")
    complete_simulation.add_argument("--artifact-root", default="reports/node-alpha")
    complete_simulation.add_argument("--device-sweep")
    complete_simulation.add_argument("--threshold-sweep")
    complete_simulation.add_argument("--resource-sweep")
    complete_simulation.add_argument("--compute-report")
    complete_simulation.add_argument("--closure")
    complete_simulation.add_argument("--design-dossier")
    complete_simulation.add_argument("--encoding", default="dual_rail", choices=["dual_rail", "cv_gkp"])
    complete_simulation.add_argument(
        "--primitive",
        default="fusion_entangling",
        choices=["fusion_entangling", "klm_csign", "gkp_gate_teleportation"],
    )
    complete_simulation.add_argument("--shots", type=int, default=1000)
    complete_simulation.add_argument("--feed-forward-latency-ns", type=float, default=5.0)
    complete_simulation.add_argument("--target-logical-error-rate", type=float, default=1e-6)
    complete_simulation.add_argument("--json", action="store_true", help="print JSON report")
    complete_simulation.add_argument("--out", help="write JSON report to path")
    complete_simulation.set_defaults(func=complete_simulation_command)

    testchip_simulation = subparsers.add_parser(
        "testchip-simulate",
        help="run simulation-only testchip pipeline with virtual S-parameters and yield sweeps",
    )
    testchip_simulation.add_argument("blueprint")
    testchip_simulation.add_argument("--device-sweep", help="existing device-sweep.json to reuse")
    testchip_simulation.add_argument("--wavelengths-nm", default="1520,1550,1580")
    testchip_simulation.add_argument("--width-errors-nm", default="-10,0,10")
    testchip_simulation.add_argument("--gap-errors-nm", default="-10,0,10")
    testchip_simulation.add_argument("--phase-errors-rad", default="-0.005,0,0.005")
    testchip_simulation.add_argument("--temperature-deltas-c", default="-5,0,5")
    testchip_simulation.add_argument("--shots", type=int, default=10000)
    testchip_simulation.add_argument("--json", action="store_true", help="print JSON report")
    testchip_simulation.add_argument(
        "--out-dir",
        default="reports/node-alpha/testchip-simulation-20260502",
        help="output directory",
    )
    testchip_simulation.set_defaults(func=testchip_simulation_command)

    value_package = subparsers.add_parser(
        "value-package",
        help="generate Node Alpha value-upgrade artifacts without claiming real-world readiness",
    )
    value_package.add_argument("blueprint")
    value_package.add_argument("--artifact-root", default="reports/node-alpha")
    value_package.add_argument("--device-sweep", default="reports/node-alpha/qc-path/device-sweep.json")
    value_package.add_argument("--syndrome-event-count", type=int, default=10000)
    value_package.add_argument("--shots", type=int, default=10000)
    value_package.add_argument("--target-logical-error-rate", type=float, default=1e-6)
    value_package.add_argument("--json", action="store_true", help="print JSON report")
    value_package.add_argument(
        "--out-dir",
        default="reports/node-alpha/value-upgrade-20260502",
        help="output directory",
    )
    value_package.set_defaults(func=value_package_command)

    value_scorecard = subparsers.add_parser(
        "value-scorecard",
        help="generate conservative diligence valuation and partner/grant artifacts",
    )
    value_scorecard.add_argument("blueprint")
    value_scorecard.add_argument("--artifact-root", default="reports/node-alpha")
    value_scorecard.add_argument("--out-dir", default="reports/node-alpha/no-budget-package")
    value_scorecard.add_argument("--docs-dir", default="docs")
    value_scorecard.add_argument("--json", action="store_true", help="print JSON report")
    value_scorecard.set_defaults(func=value_scorecard_command)

    performance_upgrade = subparsers.add_parser(
        "performance-upgrade",
        help="generate simulation-only qubit, threshold, fusion, and throughput performance reports",
    )
    performance_upgrade.add_argument("blueprint")
    performance_upgrade.add_argument("--artifact-root", default="reports/node-alpha")
    performance_upgrade.add_argument("--out-dir", default="reports/node-alpha/deep-hardening-v3-20260502")
    performance_upgrade.add_argument("--focused-max-runs", type=int, default=768)
    performance_upgrade.add_argument("--json", action="store_true", help="print JSON report")
    performance_upgrade.set_defaults(func=performance_upgrade_command)

    encoding = subparsers.add_parser("encoding", help="write computational encoding spec")
    encoding.add_argument("blueprint")
    encoding.add_argument("--encoding", default="dual_rail", choices=["dual_rail", "cv_gkp"])
    encoding.add_argument("--json", action="store_true", help="print JSON report")
    encoding.add_argument("--out", help="write JSON report to path")
    encoding.set_defaults(func=encoding_command)

    compile_parser = subparsers.add_parser("compile", help="compile blueprint to OQP ISA trace")
    compile_parser.add_argument("blueprint")
    compile_parser.add_argument("--encoding", default="dual_rail", choices=["dual_rail", "cv_gkp"])
    compile_parser.add_argument("--shots", type=int, default=1000)
    compile_parser.add_argument("--json", action="store_true", help="print JSON report")
    compile_parser.add_argument("--out", help="write JSON report to path")
    compile_parser.set_defaults(func=compile_command)

    runtime = subparsers.add_parser("runtime-trace", help="write feed-forward runtime timing trace")
    runtime.add_argument("blueprint")
    runtime.add_argument("--encoding", default="dual_rail", choices=["dual_rail", "cv_gkp"])
    runtime.add_argument("--shots", type=int, default=1000)
    runtime.add_argument("--feed-forward-latency-ns", type=float, default=5.0)
    runtime.add_argument("--json", action="store_true", help="print JSON report")
    runtime.add_argument("--out", help="write JSON report to path")
    runtime.set_defaults(func=runtime_trace_command)

    error_budget = subparsers.add_parser("error-budget", help="write noise and fault-tolerance error budget")
    error_budget.add_argument("blueprint")
    error_budget.add_argument("--source-efficiency", type=float, default=0.85)
    error_budget.add_argument("--detector-efficiency", type=float, default=0.9)
    error_budget.add_argument("--dark-count-rate-hz", type=float, default=25.0)
    error_budget.add_argument("--feed-forward-latency-ns", type=float, default=5.0)
    error_budget.add_argument("--phase-error-rad", type=float, default=0.01)
    error_budget.add_argument("--json", action="store_true", help="print JSON report")
    error_budget.add_argument("--out", help="write JSON report to path")
    error_budget.set_defaults(func=error_budget_command)

    layout_readiness = subparsers.add_parser("layout-readiness", help="write PDK/GDS/tapeout readiness report")
    layout_readiness.add_argument("blueprint")
    layout_readiness.add_argument("--pdk", default="generic-si-photonics")
    layout_readiness.add_argument("--json", action="store_true", help="print JSON report")
    layout_readiness.add_argument("--out", help="write JSON report to path")
    layout_readiness.set_defaults(func=layout_readiness_command)

    pdk_audit = subparsers.add_parser("pdk-audit", help="audit foundry PDK, rule decks, compact models, and signoff inputs")
    pdk_audit.add_argument("blueprint")
    pdk_audit.add_argument("--pdk", default="generic-si-photonics")
    pdk_audit.add_argument("--pdk-manifest", help="foundry PDK manifest JSON to validate")
    pdk_audit.add_argument("--gds-audit", default="reports/node-alpha/gds-path/gds-audit.json")
    pdk_audit.add_argument("--json", action="store_true", help="print JSON report")
    pdk_audit.add_argument("--out", help="write JSON report to path")
    pdk_audit.set_defaults(func=pdk_audit_command)

    sparameter_audit = subparsers.add_parser(
        "sparameter-audit",
        help="audit foundry-calibrated S-parameter compact models for core devices",
    )
    sparameter_audit.add_argument("blueprint")
    sparameter_audit.add_argument("--model-manifest", default="reports/node-alpha/qc-path/sparameter-models.json")
    sparameter_audit.add_argument("--min-wavelength-nm", type=float, default=1520.0)
    sparameter_audit.add_argument("--max-wavelength-nm", type=float, default=1580.0)
    sparameter_audit.add_argument("--max-insertion-loss-db", type=float, default=1.0)
    sparameter_audit.add_argument("--max-reflection-ratio", type=float, default=0.05)
    sparameter_audit.add_argument("--max-crosstalk-ratio", type=float, default=0.05)
    sparameter_audit.add_argument("--json", action="store_true", help="print JSON report")
    sparameter_audit.add_argument("--out", help="write JSON report to path")
    sparameter_audit.set_defaults(func=sparameter_audit_command)

    signoff_audit = subparsers.add_parser("signoff-audit", help="audit DRC/LVS reports and waiver status for GDS signoff")
    signoff_audit.add_argument("blueprint")
    signoff_audit.add_argument("--gds-audit", default="reports/node-alpha/gds-path/gds-audit.json")
    signoff_audit.add_argument("--pdk-audit", default="reports/node-alpha/gds-path/pdk-audit.json")
    signoff_audit.add_argument("--drc-report", default="reports/node-alpha/gds-path/drc-report.json")
    signoff_audit.add_argument("--lvs-report", default="reports/node-alpha/gds-path/lvs-report.json")
    signoff_audit.add_argument("--waiver-report", default="reports/node-alpha/gds-path/signoff-waivers.json")
    signoff_audit.add_argument("--json", action="store_true", help="print JSON report")
    signoff_audit.add_argument("--out", help="write JSON report to path")
    signoff_audit.set_defaults(func=signoff_audit_command)

    tapeout = subparsers.add_parser("tapeout-readiness", help="write strict PDK/GDS/tapeout readiness report")
    tapeout.add_argument("blueprint")
    tapeout.add_argument("--pdk", default="generic-si-photonics")
    tapeout.add_argument("--feed-forward-latency-ns", type=float, default=5.0)
    tapeout.add_argument("--detector-type", default="SNSPD")
    tapeout.add_argument("--json", action="store_true", help="print JSON report")
    tapeout.add_argument("--out", help="write JSON report to path")
    tapeout.set_defaults(func=tapeout_readiness_command)

    meep_device = subparsers.add_parser("meep-device-run", help="run MEEP FDTD on a device cell")
    meep_device.add_argument("blueprint")
    meep_device.add_argument("--device", default="mzi", choices=["coupler", "mzi", "truth-switch"])
    meep_device.add_argument("--json", action="store_true", help="print JSON report")
    meep_device.add_argument("--out", help="write JSON report to path")
    meep_device.add_argument("--resolution", type=int, default=10)
    meep_device.add_argument("--until", type=float, default=30.0)
    meep_device.add_argument("--coupling-gap-um", type=float, default=0.2)
    meep_device.add_argument("--coupling-length-um", type=float, default=3.0)
    meep_device.add_argument("--phase-shift-rad", type=float, default=0.0)
    meep_device.add_argument("--waveguide-width-um", type=float, default=0.45)
    meep_device.set_defaults(func=meep_device_command)

    eigenmode_device = subparsers.add_parser("eigenmode-device-run", help="run eigenmode-normalized MEEP FDTD on a device cell")
    eigenmode_device.add_argument("blueprint")
    eigenmode_device.add_argument("--device", default="mzi", choices=["coupler", "mzi", "phase-shifter", "truth-switch"])
    eigenmode_device.add_argument("--json", action="store_true", help="print JSON report")
    eigenmode_device.add_argument("--out", help="write JSON report to path")
    eigenmode_device.add_argument("--resolution", type=int, default=10)
    eigenmode_device.add_argument("--until", type=float, default=30.0)
    eigenmode_device.add_argument("--coupling-gap-um", type=float, default=0.2)
    eigenmode_device.add_argument("--coupling-length-um", type=float, default=3.0)
    eigenmode_device.add_argument("--phase-shift-rad", type=float, default=0.0)
    eigenmode_device.add_argument("--waveguide-width-um", type=float, default=0.45)
    eigenmode_device.set_defaults(func=eigenmode_device_command)

    primitive = subparsers.add_parser("primitive-spec", help="write universal primitive/demonstrator spec")
    primitive.add_argument("blueprint")
    primitive.add_argument("--encoding", default="dual_rail", choices=["dual_rail", "cv_gkp"])
    primitive.add_argument("--primitive", default="fusion_entangling", choices=["fusion_entangling", "klm_csign", "gkp_gate_teleportation"])
    primitive.add_argument("--json", action="store_true", help="print JSON report")
    primitive.add_argument("--out", help="write JSON report to path")
    primitive.set_defaults(func=primitive_spec_command)

    fusion = subparsers.add_parser("fusion-primitive", help="write executable two-qubit heralded-fusion primitive report")
    fusion.add_argument("blueprint")
    fusion.add_argument("--encoding", default="dual_rail", choices=["dual_rail", "cv_gkp"])
    fusion.add_argument("--device-report", help="eigenmode-device-run JSON artifact to score against")
    fusion.add_argument("--source-efficiency", type=float, default=0.85)
    fusion.add_argument("--detector-efficiency", type=float, default=0.9)
    fusion.add_argument("--feed-forward-latency-ns", type=float, default=5.0)
    fusion.add_argument("--json", action="store_true", help="print JSON report")
    fusion.add_argument("--out", help="write JSON report to path")
    fusion.set_defaults(func=fusion_primitive_command)

    primitive_demo_ingest = subparsers.add_parser("primitive-demo-ingest", help="ingest primitive-demo event data into measurement and dataset manifests")
    primitive_demo_ingest.add_argument("blueprint")
    primitive_demo_ingest.add_argument("--dataset", required=True, help="JSONL or JSON event dataset")
    primitive_demo_ingest.add_argument("--primitive", default="two_qubit_heralded_fusion")
    primitive_demo_ingest.add_argument("--experimental-status", default="measured")
    primitive_demo_ingest.add_argument("--measurement-out", default="reports/node-alpha/qc-path/primitive-demo-measurement.json")
    primitive_demo_ingest.add_argument("--dataset-manifest-out", default="reports/node-alpha/qc-path/primitive-demo-dataset.json")
    primitive_demo_ingest.add_argument("--json", action="store_true", help="print JSON report")
    primitive_demo_ingest.add_argument("--out", help="write JSON report to path")
    primitive_demo_ingest.set_defaults(func=primitive_demo_ingest_command)

    primitive_demo = subparsers.add_parser("primitive-demo-audit", help="audit measured heralded primitive demonstration evidence")
    primitive_demo.add_argument("blueprint")
    primitive_demo.add_argument("--measurement-report", default="reports/node-alpha/qc-path/primitive-demo-measurement.json")
    primitive_demo.add_argument("--dataset-manifest", default="reports/node-alpha/qc-path/primitive-demo-dataset.json")
    primitive_demo.add_argument("--hardware-audit", default="reports/node-alpha/qc-path/hardware-audit.json")
    primitive_demo.add_argument("--fusion-report", default="reports/node-alpha/qc-path/fusion-primitive.json")
    primitive_demo.add_argument("--min-shots", type=int, default=1000)
    primitive_demo.add_argument("--min-heralded-events", type=int, default=10)
    primitive_demo.add_argument("--min-heralding-success-probability", type=float, default=0.01)
    primitive_demo.add_argument("--min-process-fidelity", type=float, default=0.99)
    primitive_demo.add_argument("--max-feed-forward-latency-ns", type=float, default=10.0)
    primitive_demo.add_argument("--json", action="store_true", help="print JSON report")
    primitive_demo.add_argument("--out", help="write JSON report to path")
    primitive_demo.set_defaults(func=primitive_demo_audit_command)

    resources = subparsers.add_parser("resource-model", help="write non-Gaussian resource model")
    resources.add_argument("blueprint")
    resources.add_argument("--encoding", default="dual_rail", choices=["dual_rail", "cv_gkp"])
    resources.add_argument("--logical-qubits", type=int)
    resources.add_argument("--target-logical-error-rate", type=float, default=1e-6)
    resources.add_argument("--json", action="store_true", help="print JSON report")
    resources.add_argument("--out", help="write JSON report to path")
    resources.set_defaults(func=resource_model_command)

    resource_sweep = subparsers.add_parser("resource-sweep", help="run analytical Node Alpha resource scaling sweep")
    resource_sweep.add_argument("blueprint")
    resource_sweep.add_argument("--encoding", default="dual_rail", choices=["dual_rail", "cv_gkp"])
    resource_sweep.add_argument("--logical-qubits", default="2,4,8,18,36")
    resource_sweep.add_argument("--target-logical-error-rates", default="0.001,0.000001")
    resource_sweep.add_argument("--json", action="store_true", help="print JSON report")
    resource_sweep.add_argument("--out", default="reports/node-alpha/qc-path/resource-sweep", help="output directory")
    resource_sweep.set_defaults(func=resource_sweep_command)

    device_sweep = subparsers.add_parser("device-sweep", help="run a small MEEP FDTD device parameter sweep")
    device_sweep.add_argument("blueprint")
    device_sweep.add_argument("--devices", default="coupler,mzi,phase-shifter,truth-switch")
    device_sweep.add_argument("--coupling-gaps-um", default="0.18,0.2")
    device_sweep.add_argument("--coupling-lengths-um", default="2.0,3.0")
    device_sweep.add_argument("--phase-shifts-rad", default="0.0")
    device_sweep.add_argument("--waveguide-widths-um", default="0.45")
    device_sweep.add_argument("--resolution", type=int, default=10)
    device_sweep.add_argument("--until", type=float, default=20.0)
    device_sweep.add_argument("--max-runs", type=int, default=4)
    device_sweep.add_argument("--json", action="store_true", help="print JSON report")
    device_sweep.add_argument("--out", default="runs/device-sweep", help="output directory")
    device_sweep.set_defaults(func=device_sweep_command)

    device_sweep_rerank = subparsers.add_parser(
        "device-sweep-rerank",
        help="re-score existing device sweep JSON artifacts without rerunning MEEP",
    )
    device_sweep_rerank.add_argument("blueprint")
    device_sweep_rerank.add_argument("--evidence-dir", required=True)
    device_sweep_rerank.add_argument("--devices", default="coupler,mzi,phase-shifter,truth-switch")
    device_sweep_rerank.add_argument("--json", action="store_true", help="print JSON report")
    device_sweep_rerank.add_argument("--out", default="runs/device-sweep-reranked.json", help="write reranked JSON report")
    device_sweep_rerank.set_defaults(func=device_sweep_rerank_command)

    error_correction = subparsers.add_parser("error-correction-plan", help="write fault-tolerance and decoder plan")
    error_correction.add_argument("blueprint")
    error_correction.add_argument("--code", default="fusion_surface_code")
    error_correction.add_argument("--distance", type=int, default=3)
    error_correction.add_argument("--physical-error-rate", type=float, default=0.01)
    error_correction.add_argument("--threshold", type=float, default=0.005)
    error_correction.add_argument("--json", action="store_true", help="print JSON report")
    error_correction.add_argument("--out", help="write JSON report to path")
    error_correction.set_defaults(func=error_correction_plan_command)

    threshold_sweep = subparsers.add_parser("threshold-sweep", help="run fault-tolerance threshold parameter sweep")
    threshold_sweep.add_argument("blueprint")
    threshold_sweep.add_argument("--code", default="fusion_surface_code")
    threshold_sweep.add_argument("--device-report", help="eigenmode-device-run JSON artifact to derive device error terms")
    threshold_sweep.add_argument("--decoder-backend", default="analytical_erasure_matching")
    threshold_sweep.add_argument("--distances", default="3,5,7")
    threshold_sweep.add_argument("--physical-error-rates", default="0.001,0.003,0.005,0.01")
    threshold_sweep.add_argument("--loss-values-db", default="0.5,1.0,3.0")
    threshold_sweep.add_argument("--detector-efficiencies", default="0.9,0.95")
    threshold_sweep.add_argument("--dark-count-rates-hz", default="10,25")
    threshold_sweep.add_argument("--phase-errors-rad", default="0.005,0.01")
    threshold_sweep.add_argument("--feed-forward-latencies-ns", default="5,10")
    threshold_sweep.add_argument("--threshold", type=float, default=0.005)
    threshold_sweep.add_argument("--max-runs", type=int, default=64)
    threshold_sweep.add_argument("--json", action="store_true", help="print JSON report")
    threshold_sweep.add_argument("--out", default="runs/threshold-sweep", help="output directory")
    threshold_sweep.set_defaults(func=threshold_sweep_command)

    fault_tolerance_ingest = subparsers.add_parser(
        "fault-tolerance-ingest",
        help="ingest syndrome-noise event data into decoder and dataset manifests",
    )
    fault_tolerance_ingest.add_argument("blueprint")
    fault_tolerance_ingest.add_argument("--dataset", required=True, help="JSONL or JSON syndrome-noise event dataset")
    fault_tolerance_ingest.add_argument("--decoder", default="analytical_erasure_matching")
    fault_tolerance_ingest.add_argument("--implementation-status", default="benchmarked")
    fault_tolerance_ingest.add_argument("--decoder-report-out", default="reports/node-alpha/qc-path/decoder-report.json")
    fault_tolerance_ingest.add_argument("--noise-dataset-manifest-out", default="reports/node-alpha/qc-path/syndrome-noise-dataset.json")
    fault_tolerance_ingest.add_argument("--json", action="store_true", help="print JSON report")
    fault_tolerance_ingest.add_argument("--out", help="write JSON report to path")
    fault_tolerance_ingest.set_defaults(func=fault_tolerance_ingest_command)

    fault_tolerance = subparsers.add_parser(
        "fault-tolerance-audit",
        help="audit below-threshold, decoder, sampled-noise, and hardware-calibrated fault-tolerance evidence",
    )
    fault_tolerance.add_argument("blueprint")
    fault_tolerance.add_argument("--threshold-report", default="reports/node-alpha/qc-path/threshold-sweep.json")
    fault_tolerance.add_argument("--decoder-report", default="reports/node-alpha/qc-path/decoder-report.json")
    fault_tolerance.add_argument("--noise-dataset", default="reports/node-alpha/qc-path/syndrome-noise-dataset.json")
    fault_tolerance.add_argument("--hardware-audit", default="reports/node-alpha/qc-path/hardware-audit.json")
    fault_tolerance.add_argument("--target-logical-error-rate", type=float, default=1e-6)
    fault_tolerance.add_argument("--max-decoder-latency-ns", type=float, default=1000.0)
    fault_tolerance.add_argument("--min-sampled-syndrome-events", type=int, default=10000)
    fault_tolerance.add_argument("--json", action="store_true", help="print JSON report")
    fault_tolerance.add_argument("--out", help="write JSON report to path")
    fault_tolerance.set_defaults(func=fault_tolerance_audit_command)

    control = subparsers.add_parser("control-readiness", help="write feed-forward control readiness report")
    control.add_argument("blueprint")
    control.add_argument("--feed-forward-latency-ns", type=float, default=5.0)
    control.add_argument("--detector-jitter-ps", type=float, default=50.0)
    control.add_argument("--json", action="store_true", help="print JSON report")
    control.add_argument("--out", help="write JSON report to path")
    control.set_defaults(func=control_readiness_command)

    lab = subparsers.add_parser("lab-readiness", help="write lab and hardware readiness report")
    lab.add_argument("blueprint")
    lab.add_argument("--detector-type", default="SNSPD")
    lab.add_argument("--laser-wavelength-nm", type=int)
    lab.add_argument("--json", action="store_true", help="print JSON report")
    lab.add_argument("--out", help="write JSON report to path")
    lab.set_defaults(func=lab_readiness_command)

    hardware_ingest = subparsers.add_parser(
        "hardware-ingest",
        help="ingest hardware, calibration, and feed-forward evidence into audit reports",
    )
    hardware_ingest.add_argument("blueprint")
    hardware_ingest.add_argument("--dataset", required=True, help="JSONL or JSON hardware evidence dataset")
    hardware_ingest.add_argument("--source-out", default="reports/node-alpha/qc-path/source-hardware.json")
    hardware_ingest.add_argument("--detector-out", default="reports/node-alpha/qc-path/detector-hardware.json")
    hardware_ingest.add_argument("--packaging-out", default="reports/node-alpha/qc-path/packaging-plan.json")
    hardware_ingest.add_argument("--control-out", default="reports/node-alpha/qc-path/control-hardware.json")
    hardware_ingest.add_argument("--calibration-out", default="reports/node-alpha/qc-path/calibration-report.json")
    hardware_ingest.add_argument("--feed-forward-out", default="reports/node-alpha/qc-path/feed-forward-report.json")
    hardware_ingest.add_argument("--json", action="store_true", help="print JSON report")
    hardware_ingest.add_argument("--out", help="write JSON report to path")
    hardware_ingest.set_defaults(func=hardware_ingest_command)

    hardware_audit = subparsers.add_parser(
        "hardware-audit",
        help="audit source, detector, packaging, control, calibration, and feed-forward evidence",
    )
    hardware_audit.add_argument("blueprint")
    hardware_audit.add_argument("--source-report", default="reports/node-alpha/qc-path/source-hardware.json")
    hardware_audit.add_argument("--detector-report", default="reports/node-alpha/qc-path/detector-hardware.json")
    hardware_audit.add_argument("--packaging-report", default="reports/node-alpha/qc-path/packaging-plan.json")
    hardware_audit.add_argument("--control-report", default="reports/node-alpha/qc-path/control-hardware.json")
    hardware_audit.add_argument("--calibration-report", default="reports/node-alpha/qc-path/calibration-report.json")
    hardware_audit.add_argument("--feed-forward-report", default="reports/node-alpha/qc-path/feed-forward-report.json")
    hardware_audit.add_argument("--json", action="store_true", help="print JSON report")
    hardware_audit.add_argument("--out", help="write JSON report to path")
    hardware_audit.set_defaults(func=hardware_audit_command)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
