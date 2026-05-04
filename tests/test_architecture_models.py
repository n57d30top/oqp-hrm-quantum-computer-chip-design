import unittest
import builtins
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from oqp.blueprint import Blueprint, Metrics, SpatialModel
from oqp.compiler import compile_blueprint, runtime_trace
from oqp.complete_simulation import run_complete_simulation
from oqp.device_sweep import rerank_device_sweep, run_device_sweep, score_device
from oqp.design_dossier import generate_design_dossier
from oqp.demo import generate_primitive_demo_audit, ingest_primitive_demo_dataset
from oqp.encoding import generate_encoding_spec
from oqp.error_correction import generate_error_correction_plan
from oqp.error_budget import generate_error_budget
from oqp.eigenmode_device import DEVICE_SIMULATION_MODEL_VERSION, _geometry_spec, _make_geometry, _normalized_flux_metrics
from oqp.evidence_bundle import generate_evidence_bundle
from oqp.fault_tolerance import generate_fault_tolerance_audit, ingest_fault_tolerance_dataset
from oqp.gds import collect_device_evidence, generate_gds_artifacts, generate_gds_audit, generate_gds_manifest, generate_gds_plan
from oqp.hardware import generate_hardware_audit, ingest_hardware_dataset
from oqp.layout_readiness import generate_layout_readiness
from oqp.node_alpha import generate_node_alpha_closure
from oqp.node_alpha_compute import generate_node_alpha_compute_report
from oqp.pdk import generate_pdk_audit
from oqp.performance_upgrade import generate_performance_upgrade
from oqp.primitive import generate_fusion_primitive, generate_primitive_spec
from oqp.prototype_readiness import generate_device_acceptance_audit, generate_prototype_readiness
from oqp.readiness import generate_control_readiness, generate_lab_readiness
from oqp.resource_model import generate_resource_model
from oqp.resource_sweep import run_resource_sweep
from oqp.sparameters import generate_sparameter_audit
from oqp.signoff import generate_signoff_audit
from oqp.tapeout_readiness import generate_tapeout_readiness
from oqp.testchip_simulation import run_testchip_simulation
from oqp.threshold import run_threshold_sweep
from oqp.value_package import generate_value_package
from oqp.value_scorecard import generate_value_scorecard


class _FakeVector3:
    def __init__(self, x, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z


class _FakeMedium:
    def __init__(self, *, epsilon):
        self.epsilon = epsilon


class _FakeBlock:
    def __init__(self, *, size, center, material):
        self.size = size
        self.center = center
        self.material = material


class _FakeMeep:
    inf = float("inf")
    Vector3 = _FakeVector3
    Medium = _FakeMedium
    Block = _FakeBlock


def _max_qubit_row(report, physical_modes):
    return next(
        row for row in report["maxQubitEnvelope"]["rows"] if row["physicalModes"] == physical_modes
    )


class ArchitectureModelsTest(unittest.TestCase):
    def setUp(self):
        self.blueprint = Blueprint(
            topology_class="heralded_reset_truth_switch",
            solver_target="meep_fdtd",
            spatial_model=SpatialModel(
                network_style="small_world",
                lane_mode="device_component",
                waveguide_count=36,
                interferometer_count=24,
                laser_wavelength_nm=1550,
                pairing_stride=3,
            ),
            metrics=Metrics(
                attenuation_loss_score=0.29,
                crosstalk_risk_score=0.25,
                hop_latency_score=0.78,
                heralding_yield=0.705,
                effective_component_stage_count=4,
            ),
            documentation=[],
            source_path="test-blueprint.yaml",
        )

    def test_dual_rail_encoding_capacity(self):
        report = generate_encoding_spec(self.blueprint)
        self.assertEqual(report["schemaVersion"], "open-quantum.encoding-spec.v1")
        self.assertEqual(report["logicalQubitCapacity"], 18)
        self.assertIn("single_photon_sources", report["requiredNonGaussianResources"])

    def test_compiler_and_runtime_trace(self):
        compiled = compile_blueprint(self.blueprint, shots=10)
        trace = runtime_trace(compiled, feed_forward_latency_ns=7)
        ops = {instruction["op"] for instruction in compiled["instructions"]}
        self.assertEqual(compiled["schemaVersion"], "open-quantum.compiler-trace.v1")
        self.assertGreater(compiled["instructionCount"], 0)
        self.assertTrue({"PREPARE", "ROUTE", "MZI", "PHASE", "MEASURE", "HERALD_WAIT", "RESET", "RESULT_DECODE"}.issubset(ops))
        self.assertEqual(compiled["resultDecoding"]["method"], "dual_rail_occupancy")
        self.assertEqual(trace["schemaVersion"], "open-quantum.runtime-trace.v1")
        self.assertEqual(trace["feedForwardLatencyNs"], 7)
        self.assertGreater(trace["totalProgramTimeNsPerShot"], 0)

    def test_error_budget_lists_fault_tolerance_blockers(self):
        report = generate_error_budget(self.blueprint)
        self.assertEqual(report["schemaVersion"], "open-quantum.error-budget.v1")
        self.assertEqual(report["faultToleranceStatus"], "not_fault_tolerant")
        self.assertTrue(report["faultToleranceBlockers"])

    def test_layout_readiness_is_not_tapeout_ready(self):
        report = generate_layout_readiness(self.blueprint)
        self.assertEqual(report["schemaVersion"], "open-quantum.layout-readiness.v1")
        self.assertFalse(report["gdsReady"])
        self.assertFalse(report["tapeoutReady"])
        self.assertIn("directionalCoupler", report["componentLibraryStatus"])

    def test_gds_plan_manifest_and_audit_are_computable(self):
        report = generate_gds_plan(self.blueprint)
        self.assertEqual(report["schemaVersion"], "open-quantum.gds-plan.v1")
        self.assertTrue(report["layoutComputable"])
        self.assertFalse(report["gdsGenerated"])
        self.assertIn("WG", {layer["name"] for layer in report["layerMap"]["layers"]})
        self.assertIn("mzi", report["componentLibrary"]["cells"])

        manifest = generate_gds_manifest(self.blueprint)
        self.assertEqual(manifest["schemaVersion"], "open-quantum.gds-manifest.v1")
        self.assertEqual(manifest["topCell"], "OQP_HRM_TOP")
        self.assertGreater(len(manifest["instances"]), 0)
        self.assertGreater(len(manifest["ports"]), 0)
        self.assertGreater(len(manifest["pads"]), 0)
        self.assertFalse(manifest["readinessFlags"]["fdtd_gap_backed_placeholder"])
        self.assertFalse(any("fdtd_gap_backed_placeholder" in blocker for blocker in manifest["blockers"]))

        audit = generate_gds_audit(manifest=manifest)
        self.assertEqual(audit["schemaVersion"], "open-quantum.gds-audit.v1")
        self.assertTrue(audit["auditFlags"]["layout_computable"])
        self.assertTrue(audit["auditFlags"]["drc_not_run"])
        self.assertTrue(audit["auditFlags"]["lvs_not_run"])
        self.assertTrue(audit["auditFlags"]["not_tapeout_ready"])
        self.assertIn("foundryPdk", audit["finalGapAudit"])
        self.assertIn("accepted first-pass", audit["finalGapAudit"]["devicePhysics"])
        self.assertFalse(audit["layoutCompletion"]["quantumComputerLayoutComplete"])

    def test_gds_generate_writes_gds_and_artifact_manifests(self):
        with TemporaryDirectory() as tmp:
            report = generate_gds_artifacts(self.blueprint, out_dir=tmp, include_preview=False)
            self.assertEqual(report["schemaVersion"], "open-quantum.gds-generate.v1")
            self.assertTrue(report["gdsGenerated"])
            self.assertTrue(report["readinessFlags"]["gds_generated"])
            self.assertTrue(report["layoutCompletion"]["reproducibleGdsPackageComplete"])
            self.assertFalse(report["layoutCompletion"]["quantumComputerLayoutComplete"])
            self.assertGreater(report["gdsFile"]["byteSize"], 1024)
            with open(report["gdsFile"]["path"], "rb") as handle:
                self.assertEqual(handle.read(4), b"\x00\x06\x00\x02")
            self.assertIn("manifest", report["artifactRefs"])
            self.assertIn("audit", report["artifactRefs"])

    def test_device_acceptance_and_prototype_readiness_track_missing_gates(self):
        device_audit = generate_device_acceptance_audit(self.blueprint)
        self.assertEqual(device_audit["schemaVersion"], "open-quantum.device-acceptance-audit.v1")
        self.assertTrue(device_audit["readinessFlags"]["core_devices_accepted"])
        self.assertEqual(device_audit["summary"]["requiredDeviceCount"], 4)
        self.assertEqual(device_audit["summary"]["fdtdGapBackedPlaceholderCount"], 0)
        self.assertIn("s_parameters_missing", device_audit["readinessFlags"])

        prototype = generate_prototype_readiness(self.blueprint)
        self.assertEqual(prototype["schemaVersion"], "open-quantum.prototype-readiness.v1")
        self.assertEqual(prototype["summary"]["status"], "not_prototype_ready")
        self.assertFalse(prototype["readinessFlags"]["prototype_ready"])
        checklist_ids = {item["id"] for item in prototype["promptToArtifactChecklist"]}
        self.assertTrue({"core_device_acceptance", "foundry_pdk", "drc_lvs", "heralded_primitive_demo"}.issubset(checklist_ids))

    def test_device_acceptance_collects_candidate_json_files(self):
        with TemporaryDirectory() as tmp:
            for device in ["coupler", "mzi", "phase-shifter", "truth-switch"]:
                report = {
                    "schemaVersion": "open-quantum.eigenmode-device.v1",
                    "device": device,
                    "acceptanceStatus": "accepted_first_pass_candidate",
                    "physicalValidationLevel": "eigenmode_calibrated_2d_first_pass",
                    "simulationModelVersion": DEVICE_SIMULATION_MODEL_VERSION,
                    "fdtdMetrics": {
                        "usefulTransmission": 0.9,
                        "insertionLossDb": 0.2,
                        "reflectionRatio": 0.01,
                        "crosstalkRatio": 0.5,
                    },
                }
                with open(f"{tmp}/{device}-candidate.json", "w", encoding="utf-8") as handle:
                    json.dump(report, handle)

            audit = generate_device_acceptance_audit(self.blueprint, evidence_dir=tmp)

        self.assertEqual(audit["summary"]["missingEvidenceCount"], 0)
        self.assertEqual(audit["summary"]["fdtdGapBackedPlaceholderCount"], 4)
        self.assertFalse(audit["summary"]["allCoreDevicesAccepted"])

    def test_eigenmode_geometry_does_not_cut_waveguide_cores_in_coupler_region(self):
        geometry = _make_geometry(
            _FakeMeep,
            device="coupler",
            width=0.45,
            lane_sep=0.65,
            coupling_length_um=12.0,
            phase_shift_rad=0.0,
        )
        self.assertEqual(len(geometry), 2)
        self.assertTrue(all(block.material.epsilon == 12.0 for block in geometry))

        spec = _geometry_spec(
            self.blueprint,
            device="coupler",
            coupling_gap_um=0.2,
            coupling_length_um=12.0,
            phase_shift_rad=0.0,
            waveguide_width_um=0.45,
            resolution=16,
            until=40,
        )
        self.assertEqual(spec["couplingRegionModel"], "parallel_waveguides_no_core_cutout")
        self.assertGreaterEqual(spec["cellXUm"], 20.0)

    def test_primitive_and_resource_models(self):
        primitive = generate_primitive_spec(self.blueprint)
        resources = generate_resource_model(self.blueprint)
        self.assertEqual(primitive["schemaVersion"], "open-quantum.primitive-spec.v1")
        self.assertIn("feed_forward", primitive["requiredOperations"])
        self.assertEqual(resources["schemaVersion"], "open-quantum.resource-model.v1")
        self.assertIn("singlePhotonSources", resources["requiredNonGaussianResources"])
        self.assertIn("multiplexing", resources["requiredNonGaussianResources"])
        self.assertIn("hardwareCalibrationParameters", resources)

    def test_resource_sweep_scales_node_alpha_counts(self):
        report = run_resource_sweep(
            self.blueprint,
            logical_qubits=[2, 18],
            target_logical_error_rates=[1e-3, 1e-6],
        )

        self.assertEqual(report["schemaVersion"], "open-quantum.resource-sweep.v1")
        self.assertEqual(report["runCount"], 4)
        self.assertEqual(report["summary"]["maxSinglePhotonSources"], 36)
        self.assertEqual(report["summary"]["maxPnrDetectors"], 36)
        self.assertIn("analytical", report["limitations"][0])

    def test_fusion_primitive_scores_fdtd_evidence(self):
        device_report = {
            "schemaVersion": "open-quantum.eigenmode-device.v1",
            "device": "mzi",
            "physicalValidationLevel": "eigenmode_calibrated_2d_first_pass",
            "sourceModel": "eigenmode",
            "fdtdMetrics": {
                "throughRatio": 0.45,
                "crossRatio": 0.45,
                "reflectionRatio": 0.01,
                "usefulTransmission": 0.9,
                "insertionLossDb": 0.45,
                "crosstalkRatio": 0.01,
            },
        }
        report = generate_fusion_primitive(self.blueprint, device_report=device_report)
        self.assertEqual(report["schemaVersion"], "open-quantum.fusion-primitive.v1")
        self.assertTrue(report["readinessFlags"]["fdtdValidated"])
        self.assertIn(report["status"], {"primitive_ready", "not_primitive_ready"})

    def test_error_correction_control_and_lab_readiness(self):
        ec = generate_error_correction_plan(self.blueprint, distance=3)
        control = generate_control_readiness(self.blueprint)
        lab = generate_lab_readiness(self.blueprint)
        self.assertEqual(ec["schemaVersion"], "open-quantum.error-correction-plan.v1")
        self.assertFalse(ec["belowThreshold"])
        self.assertFalse(control["controlReady"])
        self.assertFalse(lab["labReady"])
        self.assertIn("shotSchedulerInterface", control)
        self.assertIn("measurementProtocols", lab)

    def test_threshold_sweep_and_tapeout_readiness(self):
        threshold = run_threshold_sweep(
            self.blueprint,
            device_report={
                "schemaVersion": "open-quantum.eigenmode-device.v1",
                "device": "mzi",
                "acceptanceStatus": "not_accepted_first_pass",
                "physicalValidationLevel": "eigenmode_calibrated_2d_first_pass",
                "fdtdMetrics": {
                    "usefulTransmission": 0.8,
                    "insertionLossDb": 0.9,
                    "reflectionRatio": 0.01,
                    "crosstalkRatio": 0.01,
                },
            },
            distances=[3],
            physical_error_rates=[0.001],
            loss_values_db=[0.5],
            detector_efficiencies=[0.95],
            dark_count_rates_hz=[10],
            phase_errors_rad=[0.005],
            feed_forward_latencies_ns=[5],
            max_runs=1,
        )
        tapeout = generate_tapeout_readiness(self.blueprint)
        self.assertEqual(threshold["schemaVersion"], "open-quantum.threshold-sweep.v1")
        self.assertEqual(threshold["runCount"], 1)
        self.assertIn("decoderInterface", threshold)
        self.assertTrue(threshold["deviceEvidence"]["provided"])
        self.assertIn("decoderBackend", threshold)
        self.assertEqual(tapeout["schemaVersion"], "open-quantum.tapeout-readiness.v1")
        self.assertIn("drcLvsStatus", tapeout)
        self.assertIn("gdsCellLibrary", tapeout)
        self.assertFalse(tapeout["tapeoutReady"])

    def test_threshold_sweep_promotes_below_threshold_champion(self):
        threshold = run_threshold_sweep(
            self.blueprint,
            device_report={
                "schemaVersion": "open-quantum.eigenmode-device.v1",
                "device": "truth-switch",
                "acceptanceStatus": "surrogate_accepted_candidate",
                "physicalValidationLevel": "node_alpha_surrogate_not_fdtd",
                "fdtdMetrics": {
                    "usefulTransmission": 4.0,
                    "insertionLossDb": 0.0,
                    "reflectionRatio": 0.018,
                    "crosstalkRatio": 0.0,
                },
            },
            distances=[3, 5],
            physical_error_rates=[0.00005, 0.0003],
            loss_values_db=[0.0],
            detector_efficiencies=[1.0, 0.999],
            dark_count_rates_hz=[0.0],
            phase_errors_rad=[0.0],
            feed_forward_latencies_ns=[0.0],
            max_runs=8,
        )

        self.assertEqual(threshold["status"], "below_threshold_candidate_found")
        self.assertTrue(threshold["champion"]["belowThreshold"])
        self.assertTrue(threshold["acceptedCandidates"])

    def test_foundry_pdk_audit_blocks_generic_and_accepts_complete_manifest(self):
        generic = generate_pdk_audit(self.blueprint, gds_audit_path=None)
        self.assertEqual(generic["schemaVersion"], "open-quantum.pdk-audit.v1")
        self.assertFalse(generic["readinessFlags"]["foundry_pdk_locked"])
        self.assertFalse(generic["readinessFlags"]["pdk_ready"])

        with TemporaryDirectory() as tmp:
            root = f"{tmp}/pdk"
            paths = {
                "drc": f"{root}/drc.deck",
                "lvs": f"{root}/lvs.deck",
                "pcell": f"{root}/pcells",
                "gdsAudit": f"{tmp}/gds-audit.json",
            }
            for path in [root, paths["pcell"]]:
                Path(path).mkdir(parents=True, exist_ok=True)
            for path in [paths["drc"], paths["lvs"]]:
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write("deck placeholder\n")
            compact_models = {}
            for device in ["coupler", "mzi", "phase-shifter", "truth-switch"]:
                path = f"{root}/{device}.sparam"
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write("s-parameter placeholder\n")
                compact_models[device] = path
            with open(paths["gdsAudit"], "w", encoding="utf-8") as handle:
                json.dump({"auditFlags": {"gds_generated": True, "not_tapeout_ready": True}}, handle)
            manifest = {
                "foundry": "test-foundry",
                "pdkName": "test-siph-220nm",
                "process": "220nm-SOI",
                "foundryPdkLocked": True,
                "layerMap": [
                    {"purpose": "waveguide"},
                    {"purpose": "etch"},
                    {"purpose": "metal"},
                    {"purpose": "pad"},
                    {"purpose": "port"},
                    {"purpose": "label"},
                    {"purpose": "keepout"},
                ],
                "ruleDecks": {"drc": paths["drc"], "lvs": paths["lvs"]},
                "processCorners": [{"name": "typical"}],
                "pcellLibrary": paths["pcell"],
                "compactModels": compact_models,
                "packageRules": {
                    "fiberArray": True,
                    "edgeCoupler": True,
                    "padOpening": True,
                    "thermalKeepout": True,
                    "probeCard": True,
                },
            }
            manifest_path = f"{tmp}/foundry-pdk.json"
            with open(manifest_path, "w", encoding="utf-8") as handle:
                json.dump(manifest, handle)

            complete = generate_pdk_audit(
                self.blueprint,
                pdk="test-siph-220nm",
                pdk_manifest=manifest_path,
                gds_audit_path=paths["gdsAudit"],
            )

        self.assertTrue(complete["readinessFlags"]["pdk_ready"])
        self.assertTrue(complete["readinessFlags"]["drc_lvs_runnable"])
        self.assertEqual(complete["blockers"], [])

    def test_signoff_audit_requires_pdk_and_clean_drc_lvs_reports(self):
        blocked = generate_signoff_audit(self.blueprint, gds_audit_path=None, pdk_audit_path=None)
        self.assertEqual(blocked["schemaVersion"], "open-quantum.signoff-audit.v1")
        self.assertFalse(blocked["readinessFlags"]["signoff_ready"])
        self.assertIn("pdk_ready", blocked["blockers"][1])

        with TemporaryDirectory() as tmp:
            gds_audit = f"{tmp}/gds-audit.json"
            pdk_audit = f"{tmp}/pdk-audit.json"
            drc_report = f"{tmp}/drc-report.json"
            lvs_report = f"{tmp}/lvs-report.json"
            with open(gds_audit, "w", encoding="utf-8") as handle:
                json.dump({"auditFlags": {"gds_generated": True}}, handle)
            with open(pdk_audit, "w", encoding="utf-8") as handle:
                json.dump({"readinessFlags": {"pdk_ready": True, "drc_lvs_runnable": True}}, handle)
            with open(drc_report, "w", encoding="utf-8") as handle:
                json.dump({"status": "clean", "violationCount": 0, "fatalCount": 0}, handle)
            with open(lvs_report, "w", encoding="utf-8") as handle:
                json.dump({"status": "clean", "mismatchCount": 0, "fatalCount": 0}, handle)

            clean = generate_signoff_audit(
                self.blueprint,
                gds_audit_path=gds_audit,
                pdk_audit_path=pdk_audit,
                drc_report_path=drc_report,
                lvs_report_path=lvs_report,
                waiver_report_path=None,
            )

        self.assertTrue(clean["readinessFlags"]["drc_lvs_clean"])
        self.assertTrue(clean["readinessFlags"]["signoff_ready"])
        self.assertEqual(clean["blockers"], [])

    def test_hardware_audit_blocks_missing_reports_and_accepts_measured_chain(self):
        blocked = generate_hardware_audit(self.blueprint)
        self.assertEqual(blocked["schemaVersion"], "open-quantum.hardware-audit.v1")
        self.assertFalse(blocked["readinessFlags"]["hardware_ready"])
        self.assertIn("source_hardware", blocked["blockers"][0])

        with TemporaryDirectory() as tmp:
            spatial = self.blueprint.spatial_model
            source = f"{tmp}/source.json"
            detector = f"{tmp}/detector.json"
            packaging = f"{tmp}/packaging.json"
            control = f"{tmp}/control.json"
            calibration = f"{tmp}/calibration.json"
            feed_forward = f"{tmp}/feed-forward.json"
            artifacts = {
                source: {
                    "status": "measured",
                    "sourceCount": spatial.waveguide_count,
                    "brightness": 0.82,
                    "indistinguishability": 0.995,
                    "multiphotonProbability": 0.0005,
                },
                detector: {
                    "status": "measured",
                    "detectorCount": spatial.waveguide_count,
                    "efficiency": 0.96,
                    "darkCountHz": 5,
                    "timingJitterPs": 25,
                    "photonNumberResolving": True,
                },
                packaging: {
                    "fiberPlanLocked": True,
                    "edgeCouplerPlanLocked": True,
                    "probeCardLocked": True,
                    "thermalPlanLocked": True,
                    "packageDrawingReleased": True,
                    "opticalPortCount": spatial.waveguide_count * 2,
                    "electricalPadCount": spatial.interferometer_count,
                },
                control: {
                    "timingFabric": "fpga",
                    "tdcChannels": spatial.waveguide_count,
                    "detectorReadoutChannels": spatial.waveguide_count,
                    "phaseDriverChannels": spatial.interferometer_count,
                    "switchDriverChannels": max(1, spatial.interferometer_count // 2),
                    "dacResolutionBits": 14,
                    "clockJitterPs": 5,
                },
                calibration: {
                    "status": "complete",
                    "completedCalibrations": {
                        "phase": True,
                        "loss": True,
                        "crosstalk": True,
                        "detector_timing": True,
                        "source_indistinguishability": True,
                        "switch_latency": True,
                    },
                },
                feed_forward: {
                    "status": "verified",
                    "measuredLatencyNs": 6,
                    "measuredJitterPs": 5,
                    "hardwareInLoopShots": 1000,
                },
            }
            for path, report in artifacts.items():
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(report, handle)

            complete = generate_hardware_audit(
                self.blueprint,
                source_report_path=source,
                detector_report_path=detector,
                packaging_report_path=packaging,
                control_report_path=control,
                calibration_report_path=calibration,
                feed_forward_report_path=feed_forward,
            )

        self.assertTrue(complete["readinessFlags"]["hardware_ready"])
        self.assertTrue(complete["readinessFlags"]["automatic_calibration_ready"])
        self.assertTrue(complete["readinessFlags"]["feed_forward_verified"])
        self.assertEqual(complete["blockers"], [])

    def test_hardware_ingest_writes_audit_compatible_reports(self):
        with TemporaryDirectory() as tmp:
            spatial = self.blueprint.spatial_model
            dataset = Path(tmp) / "hardware-events.jsonl"
            dataset.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "category": "source",
                                "status": "measured",
                                "sourceCount": spatial.waveguide_count,
                                "brightness": 0.84,
                                "indistinguishability": 0.996,
                                "multiphotonProbability": 0.0004,
                            }
                        ),
                        json.dumps(
                            {
                                "category": "detector",
                                "status": "measured",
                                "detectorCount": spatial.waveguide_count,
                                "efficiency": 0.97,
                                "darkCountHz": 4,
                                "timingJitterPs": 22,
                                "photonNumberResolving": True,
                            }
                        ),
                        json.dumps(
                            {
                                "category": "packaging",
                                "status": "locked",
                                "fiberPlanLocked": True,
                                "edgeCouplerPlanLocked": True,
                                "probeCardLocked": True,
                                "thermalPlanLocked": True,
                                "packageDrawingReleased": True,
                                "opticalPortCount": spatial.waveguide_count * 2,
                                "electricalPadCount": spatial.interferometer_count,
                            }
                        ),
                        json.dumps(
                            {
                                "category": "control",
                                "status": "measured",
                                "timingFabric": "fpga",
                                "tdcChannels": spatial.waveguide_count,
                                "detectorReadoutChannels": spatial.waveguide_count,
                                "phaseDriverChannels": spatial.interferometer_count,
                                "switchDriverChannels": max(1, spatial.interferometer_count // 2),
                                "dacResolutionBits": 16,
                                "clockJitterPs": 4,
                            }
                        ),
                        json.dumps(
                            {
                                "category": "calibration",
                                "status": "complete",
                                "completedCalibrations": {
                                    "phase": True,
                                    "loss": True,
                                    "crosstalk": True,
                                    "detector_timing": True,
                                    "source_indistinguishability": True,
                                    "switch_latency": True,
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "category": "feed_forward",
                                "status": "verified",
                                "measuredLatencyNs": 6.0,
                                "measuredJitterPs": 5.0,
                                "hardwareInLoopShots": 1200,
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            paths = {
                "source": Path(tmp) / "source-hardware.json",
                "detector": Path(tmp) / "detector-hardware.json",
                "packaging": Path(tmp) / "packaging-plan.json",
                "control": Path(tmp) / "control-hardware.json",
                "calibration": Path(tmp) / "calibration-report.json",
                "feed_forward": Path(tmp) / "feed-forward-report.json",
            }

            ingest = ingest_hardware_dataset(
                self.blueprint,
                dataset_path=dataset,
                source_out=paths["source"],
                detector_out=paths["detector"],
                packaging_out=paths["packaging"],
                control_out=paths["control"],
                calibration_out=paths["calibration"],
                feed_forward_out=paths["feed_forward"],
            )
            audit = generate_hardware_audit(
                self.blueprint,
                source_report_path=paths["source"],
                detector_report_path=paths["detector"],
                packaging_report_path=paths["packaging"],
                control_report_path=paths["control"],
                calibration_report_path=paths["calibration"],
                feed_forward_report_path=paths["feed_forward"],
            )
            source_written = paths["source"].is_file()

        self.assertEqual(ingest["schemaVersion"], "open-quantum.hardware-ingest.v1")
        self.assertEqual(ingest["summary"]["recordCount"], 6)
        self.assertEqual(ingest["blockers"], [])
        self.assertTrue(source_written)
        self.assertTrue(audit["readinessFlags"]["hardware_ready"])
        self.assertEqual(audit["blockers"], [])

    def test_primitive_demo_audit_requires_measured_dataset_and_hardware(self):
        blocked = generate_primitive_demo_audit(self.blueprint)
        self.assertEqual(blocked["schemaVersion"], "open-quantum.primitive-demo-audit.v1")
        self.assertFalse(blocked["readinessFlags"]["primitive_demonstrated"])
        self.assertIn("no measured primitive report", blocked["blockers"][0])

        with TemporaryDirectory() as tmp:
            dataset_path = Path(tmp) / "primitive-events.jsonl"
            dataset_bytes = b'{"shot":1,"heralded":true}\n'
            dataset_path.write_bytes(dataset_bytes)
            measurement = Path(tmp) / "measurement.json"
            measurement.write_text(
                json.dumps(
                    {
                        "primitive": "two_qubit_heralded_fusion",
                        "experimentalStatus": "measured",
                        "shotCount": 2000,
                        "heraldedEventCount": 50,
                        "measuredHeraldingSuccessProbability": 0.025,
                        "measuredProcessFidelity": 0.995,
                        "processFidelityUncertainty": 0.002,
                        "measuredFeedForwardLatencyNs": 6.0,
                    }
                ),
                encoding="utf-8",
            )
            dataset_manifest = Path(tmp) / "dataset.json"
            dataset_manifest.write_text(
                json.dumps(
                    {
                        "path": str(dataset_path),
                        "sha256": sha256(dataset_bytes).hexdigest(),
                        "recordCount": 1,
                    }
                ),
                encoding="utf-8",
            )
            hardware = Path(tmp) / "hardware-audit.json"
            hardware.write_text(json.dumps({"readinessFlags": {"hardware_ready": True}}), encoding="utf-8")
            fusion = Path(tmp) / "fusion-primitive.json"
            fusion.write_text(
                json.dumps({"status": "primitive_ready", "readinessFlags": {"primitiveReady": True}}),
                encoding="utf-8",
            )

            complete = generate_primitive_demo_audit(
                self.blueprint,
                measurement_report_path=measurement,
                dataset_manifest_path=dataset_manifest,
                hardware_audit_path=hardware,
                fusion_report_path=fusion,
            )

        self.assertTrue(complete["readinessFlags"]["primitive_demonstrated"])
        self.assertTrue(complete["readinessFlags"]["dataset_verified"])
        self.assertEqual(complete["blockers"], [])

    def test_primitive_demo_ingest_writes_measurement_and_hash_manifest(self):
        with TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "primitive-events.jsonl"
            dataset.write_text(
                "\n".join(
                    [
                        json.dumps({"shot": 1, "heralded": True, "processFidelity": 0.997, "feedForwardLatencyNs": 6.0}),
                        json.dumps({"shot": 2, "heralded": False, "feedForwardLatencyNs": 5.0}),
                        json.dumps({"shot": 3, "outcome": "success", "fidelity": 0.996, "latencyNs": 7.0}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            measurement = Path(tmp) / "measurement.json"
            manifest = Path(tmp) / "dataset.json"

            report = ingest_primitive_demo_dataset(
                self.blueprint,
                dataset_path=dataset,
                measurement_out=measurement,
                dataset_manifest_out=manifest,
            )

            hardware = Path(tmp) / "hardware-audit.json"
            hardware.write_text(json.dumps({"readinessFlags": {"hardware_ready": True}}), encoding="utf-8")
            fusion = Path(tmp) / "fusion-primitive.json"
            fusion.write_text(json.dumps({"readinessFlags": {"primitiveReady": True}}), encoding="utf-8")
            audit = generate_primitive_demo_audit(
                self.blueprint,
                measurement_report_path=measurement,
                dataset_manifest_path=manifest,
                hardware_audit_path=hardware,
                fusion_report_path=fusion,
                min_shots=3,
                min_heralded_events=2,
            )

        self.assertEqual(report["schemaVersion"], "open-quantum.primitive-demo-ingest.v1")
        self.assertEqual(report["summary"]["shotCount"], 3)
        self.assertEqual(report["summary"]["heraldedEventCount"], 2)
        self.assertEqual(report["blockers"], [])
        self.assertTrue(audit["readinessFlags"]["primitive_demonstrated"])

    def test_fault_tolerance_audit_requires_decoder_and_sampled_noise(self):
        blocked = generate_fault_tolerance_audit(
            self.blueprint,
            threshold_report_path=None,
            decoder_report_path=None,
            noise_dataset_manifest_path=None,
            hardware_audit_path=None,
        )
        self.assertEqual(blocked["schemaVersion"], "open-quantum.fault-tolerance-audit.v1")
        self.assertFalse(blocked["readinessFlags"]["fault_tolerance_ready"])
        self.assertTrue(any("no below-threshold" in blocker for blocker in blocked["blockers"]))

        with TemporaryDirectory() as tmp:
            dataset_path = Path(tmp) / "syndrome-events.jsonl"
            dataset_bytes = b'{"round":1,"defects":[1,3],"logical_error":false}\n'
            dataset_path.write_bytes(dataset_bytes)
            threshold = Path(tmp) / "threshold.json"
            threshold.write_text(
                json.dumps(
                    {
                        "status": "below_threshold_candidate_found",
                        "acceptedCandidates": [{"candidateId": "d5"}],
                        "champion": {"estimatedLogicalErrorRatePerCycle": 5e-7},
                        "decoderInterface": {"status": "implemented"},
                    }
                ),
                encoding="utf-8",
            )
            decoder = Path(tmp) / "decoder.json"
            decoder.write_text(
                json.dumps(
                    {
                        "decoder": "mwpm",
                        "implementationStatus": "validated",
                        "measuredLatencyNs": 250.0,
                        "validatedLogicalErrorRate": 5e-7,
                        "sampledSyndromeEvents": 12000,
                    }
                ),
                encoding="utf-8",
            )
            dataset_manifest = Path(tmp) / "dataset.json"
            dataset_manifest.write_text(
                json.dumps(
                    {
                        "path": str(dataset_path),
                        "sha256": sha256(dataset_bytes).hexdigest(),
                        "recordCount": 12000,
                    }
                ),
                encoding="utf-8",
            )
            hardware = Path(tmp) / "hardware.json"
            hardware.write_text(json.dumps({"readinessFlags": {"hardware_ready": True}}), encoding="utf-8")

            complete = generate_fault_tolerance_audit(
                self.blueprint,
                threshold_report_path=threshold,
                decoder_report_path=decoder,
                noise_dataset_manifest_path=dataset_manifest,
                hardware_audit_path=hardware,
            )

        self.assertTrue(complete["readinessFlags"]["fault_tolerance_ready"])
        self.assertTrue(complete["readinessFlags"]["decoder_implemented"])
        self.assertTrue(complete["readinessFlags"]["noise_dataset_verified"])
        self.assertEqual(complete["blockers"], [])

    def test_fault_tolerance_ingest_writes_decoder_and_noise_manifest(self):
        with TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "syndrome-events.jsonl"
            dataset.write_text(
                "\n".join(
                    [
                        json.dumps({"round": 1, "defects": [1, 3], "logical_error": False, "decoderLatencyNs": 120.0}),
                        json.dumps({"round": 2, "defects": [], "logical_error": False, "decoderLatencyNs": 110.0}),
                        json.dumps({"round": 3, "syndrome": [2], "logical_error": False, "latencyNs": 130.0}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            decoder = Path(tmp) / "decoder-report.json"
            manifest = Path(tmp) / "syndrome-noise-dataset.json"

            report = ingest_fault_tolerance_dataset(
                self.blueprint,
                dataset_path=dataset,
                decoder_report_out=decoder,
                noise_dataset_manifest_out=manifest,
                decoder="mwpm",
                implementation_status="validated",
            )

            threshold = Path(tmp) / "threshold.json"
            threshold.write_text(
                json.dumps(
                    {
                        "status": "below_threshold_candidate_found",
                        "acceptedCandidates": [{"candidateId": "d3"}],
                        "champion": {"estimatedLogicalErrorRatePerCycle": 0.0},
                    }
                ),
                encoding="utf-8",
            )
            hardware = Path(tmp) / "hardware.json"
            hardware.write_text(json.dumps({"readinessFlags": {"hardware_ready": True}}), encoding="utf-8")
            audit = generate_fault_tolerance_audit(
                self.blueprint,
                threshold_report_path=threshold,
                decoder_report_path=decoder,
                noise_dataset_manifest_path=manifest,
                hardware_audit_path=hardware,
                min_sampled_syndrome_events=3,
            )

        self.assertEqual(report["schemaVersion"], "open-quantum.fault-tolerance-ingest.v1")
        self.assertEqual(report["summary"]["recordCount"], 3)
        self.assertEqual(report["summary"]["logicalErrorCount"], 0)
        self.assertEqual(report["blockers"], [])
        self.assertTrue(audit["readinessFlags"]["fault_tolerance_ready"])

    def test_sparameter_audit_requires_calibrated_hashed_models(self):
        blocked = generate_sparameter_audit(self.blueprint, model_manifest_path=None)
        self.assertEqual(blocked["schemaVersion"], "open-quantum.sparameter-audit.v1")
        self.assertFalse(blocked["readinessFlags"]["sparameter_models_ready"])
        self.assertEqual(blocked["summary"]["missingDeviceCount"], 4)

        with TemporaryDirectory() as tmp:
            models = {}
            for device in ["coupler", "mzi", "phase-shifter", "truth-switch"]:
                path = Path(tmp) / f"{device}.sparam"
                data = f"{device} s-parameter model\n".encode()
                path.write_bytes(data)
                models[device] = {
                    "path": str(path),
                    "sha256": sha256(data).hexdigest(),
                    "calibrationStatus": "foundry_calibrated",
                    "validationLevel": "3d_mpb_sparameter",
                    "processCorners": ["tt", "ff", "ss"],
                    "wavelengthRangeNm": [1500, 1600],
                    "portCount": 4,
                    "metrics": {
                        "insertionLossDb": 0.4,
                        "reflectionRatio": 0.01,
                        "crosstalkRatio": 0.02,
                        "passivityMaxSingularValue": 0.999,
                        "reciprocityError": 1e-4,
                        "energyBalanceError": 0.01,
                    },
                }
            manifest = Path(tmp) / "models.json"
            manifest.write_text(json.dumps({"models": models}), encoding="utf-8")

            complete = generate_sparameter_audit(self.blueprint, model_manifest_path=manifest)

        self.assertTrue(complete["readinessFlags"]["sparameter_models_ready"])
        self.assertTrue(complete["readinessFlags"]["all_hashes_verified"])
        self.assertEqual(complete["blockers"], [])

    def test_evidence_bundle_maps_required_prototype_artifacts(self):
        with TemporaryDirectory() as tmp:
            blocked = generate_evidence_bundle(self.blueprint, artifact_root=tmp, write_templates=True)

            self.assertEqual(blocked["schemaVersion"], "open-quantum.evidence-bundle.v1")
            self.assertFalse(blocked["readinessFlags"]["prototype_evidence_complete"])
            self.assertGreater(blocked["summary"]["missingArtifactCount"], 0)
            self.assertTrue(blocked["templateOutputs"])
            self.assertTrue(Path(blocked["templateOutputs"][0]["path"]).is_file())

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            gds = root / "gds-path"
            qc = root / "qc-path"
            gds.mkdir(parents=True)
            qc.mkdir(parents=True)
            (gds / "oqp-hrm-generic-siph.gds").write_bytes(b"GDS")
            self._write_json(gds / "gds-audit.json", {"auditFlags": {"gds_generated": True}})
            self._write_json(gds / "foundry-pdk-manifest.json", {"foundryPdkLocked": True})
            self._write_json(gds / "pdk-audit.json", {"readinessFlags": {"pdk_ready": True}})
            self._write_json(
                gds / "signoff-audit.json",
                {"readinessFlags": {"drc_lvs_clean": True, "signoff_ready": True}},
            )
            self._write_json(qc / "device-acceptance-audit.json", {"readinessFlags": {"core_devices_accepted": True}})
            self._write_json(qc / "sparameter-models.json", {"models": {}})
            self._write_json(qc / "sparameter-audit.json", {"readinessFlags": {"sparameter_models_ready": True}})
            for name in [
                "source-hardware.json",
                "detector-hardware.json",
                "packaging-plan.json",
                "control-hardware.json",
                "calibration-report.json",
                "feed-forward-report.json",
                "threshold-sweep.json",
                "decoder-report.json",
                "fusion-primitive.json",
                "primitive-demo-measurement.json",
            ]:
                self._write_json(qc / name, {"status": "present"})
            self._write_json(
                qc / "hardware-audit.json",
                {
                    "readinessFlags": {
                        "hardware_ready": True,
                        "automatic_calibration_ready": True,
                        "feed_forward_verified": True,
                    }
                },
            )
            syndrome = qc / "syndrome-events.jsonl"
            syndrome_bytes = b'{"round":1}\n'
            syndrome.write_bytes(syndrome_bytes)
            self._write_json(
                qc / "syndrome-noise-dataset.json",
                {"path": str(syndrome), "sha256": sha256(syndrome_bytes).hexdigest(), "recordCount": 1},
            )
            self._write_json(qc / "fault-tolerance-audit.json", {"readinessFlags": {"fault_tolerance_ready": True}})
            primitive = qc / "primitive-events.jsonl"
            primitive_bytes = b'{"shot":1}\n'
            primitive.write_bytes(primitive_bytes)
            self._write_json(
                qc / "primitive-demo-dataset.json",
                {"path": str(primitive), "sha256": sha256(primitive_bytes).hexdigest(), "recordCount": 1},
            )
            self._write_json(qc / "primitive-demo-audit.json", {"readinessFlags": {"primitive_demonstrated": True}})
            self._write_json(qc / "prototype-readiness.json", {"readinessFlags": {"prototype_ready": True}})

            complete = generate_evidence_bundle(self.blueprint, artifact_root=root)

        self.assertTrue(complete["readinessFlags"]["prototype_evidence_complete"])
        self.assertEqual(complete["summary"]["missingArtifactCount"], 0)
        self.assertEqual(complete["summary"]["hashGapCount"], 0)
        self.assertTrue(all(item["status"] == "complete" for item in complete["requirements"]))

    def test_design_dossier_closes_architecture_without_overstating_hardware(self):
        with TemporaryDirectory() as tmp:
            dossier = generate_design_dossier(self.blueprint, artifact_root=tmp)

        self.assertEqual(dossier["schemaVersion"], "open-quantum.design-dossier.v1")
        self.assertEqual(dossier["summary"]["status"], "architecture_dossier_complete")
        self.assertTrue(dossier["readinessFlags"]["architecture_dossier_complete"])
        self.assertFalse(dossier["readinessFlags"]["prototype_ready"])
        self.assertFalse(dossier["readinessFlags"]["tapeout_ready"])
        self.assertFalse(dossier["readinessFlags"]["hardware_evidence_complete"])
        self.assertFalse(dossier["readinessFlags"]["fault_tolerance_ready"])
        self.assertFalse(dossier["readinessFlags"]["experimental_primitive_demonstrated"])
        self.assertEqual(dossier["scopeBoundary"]["claim"], "complete_architecture_dossier")
        self.assertIn("foundry-ready tapeout", dossier["scopeBoundary"]["notClaimed"])
        self.assertTrue(dossier["prioritizedRoadmap"])
        self.assertEqual(dossier["prioritizedRoadmap"][0]["requirement"], "core_device_models")

    def test_node_alpha_closure_maxes_local_work_without_external_claims(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            gds = root / "gds-path"
            qc = root / "qc-path"
            templates = root / "evidence-intake" / "templates"
            gds.mkdir(parents=True)
            qc.mkdir(parents=True)
            templates.mkdir(parents=True)
            (gds / "oqp-hrm-generic-siph.gds").write_bytes(b"GDS")
            self._write_json(gds / "gds-manifest.json", {"schemaVersion": "open-quantum.gds-manifest.v1"})
            self._write_json(
                gds / "gds-audit.json",
                {"auditFlags": {"gds_generated": True, "layout_computable": True, "not_tapeout_ready": True}},
            )
            for name in ["pdk-audit.json", "signoff-audit.json"]:
                self._write_json(gds / name, {"readinessFlags": {"pdk_ready": False, "signoff_ready": False}})
            for name in [
                "compiler-trace.json",
                "runtime-trace.json",
                "resource-model.json",
                "threshold-sweep.json",
                "primitive-spec.json",
                "fusion-primitive.json",
                "error-budget.json",
                "sparameter-audit.json",
                "hardware-audit.json",
                "fault-tolerance-audit.json",
                "primitive-demo-audit.json",
            ]:
                self._write_json(qc / name, {"readinessFlags": {}})
            self._write_json(
                qc / "device-acceptance-audit.json",
                {
                    "summary": {
                        "requiredDeviceCount": 4,
                        "missingEvidenceCount": 0,
                        "staleEvidenceCount": 0,
                    },
                    "devices": [{"device": device} for device in ["coupler", "mzi", "phase-shifter", "truth-switch"]],
                },
            )
            self._write_json(
                qc / "prototype-readiness.json",
                {
                    "summary": {"completeCriteria": 1, "totalCriteria": 9},
                    "promptToArtifactChecklist": [
                        {"id": "pre_tapeout_gds", "status": "complete"},
                        {"id": "core_device_acceptance", "status": "missing", "blockers": ["device gap"]},
                        {"id": "foundry_pdk", "status": "missing", "blockers": ["pdk gap"]},
                        {"id": "drc_lvs", "status": "missing", "blockers": ["signoff gap"]},
                        {"id": "source_detector_packaging", "status": "missing", "blockers": ["hardware gap"]},
                        {"id": "control_feed_forward", "status": "missing", "blockers": ["control gap"]},
                        {"id": "automatic_calibration", "status": "missing", "blockers": ["calibration gap"]},
                        {"id": "fault_tolerance", "status": "missing", "blockers": ["decoder gap"]},
                        {"id": "heralded_primitive_demo", "status": "missing", "blockers": ["demo gap"]},
                    ],
                },
            )
            self._write_json(
                qc / "evidence-bundle.json",
                {
                    "summary": {
                        "requiredArtifactCount": 24,
                        "completeRequirementCount": 0,
                        "totalRequirementCount": 9,
                    },
                    "requirements": [
                        {
                            "id": "foundry_pdk",
                            "status": "blocked",
                            "description": "Real PDK",
                            "artifactIds": ["foundry_pdk_manifest"],
                            "blockers": ["missing PDK"],
                        }
                    ],
                },
            )
            self._write_json(
                qc / "complete-design-dossier.json",
                {
                    "readinessFlags": {
                        "architecture_dossier_complete": True,
                        "prototype_ready": False,
                        "tapeout_ready": False,
                        "hardware_evidence_complete": False,
                        "fault_tolerance_ready": False,
                        "experimental_primitive_demonstrated": False,
                    }
                },
            )

            report = generate_node_alpha_closure(self.blueprint, artifact_root=root)

        self.assertTrue(report["readinessFlags"]["node_alpha_maxed_without_realworld_input"])
        self.assertTrue(report["readinessFlags"]["core_device_gap_quantified"])
        self.assertFalse(report["readinessFlags"]["complete_quantum_computer"])
        self.assertGreaterEqual(len(report["hardStopsRequiringRealWorldInput"]), 1)

    def test_node_alpha_compute_report_marks_simulated_only(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            device = root / "device.json"
            threshold = root / "threshold.json"
            resources = root / "resources.json"
            closure = root / "closure.json"
            self._write_json(
                device,
                {
                    "status": "high_resolution_gap_quantified",
                    "runCount": 1,
                    "validationTier": "node_alpha_surrogate_gap_probe",
                    "champion": {
                        "candidateId": "c1",
                        "device": "coupler",
                        "backend": "node_alpha_analytical_surrogate",
                        "physicalValidationLevel": "node_alpha_surrogate_not_fdtd",
                        "fdtdMetrics": {"usefulTransmission": 0.9},
                    },
                    "perDeviceChampions": {},
                    "perDeviceGapToAcceptance": {},
                },
            )
            self._write_json(
                threshold,
                {"status": "no_below_threshold_candidate", "runCount": 2, "acceptedCandidates": [], "champion": {}},
            )
            self._write_json(resources, {"runCount": 3, "summary": {"maxSinglePhotonSources": 4}})
            self._write_json(
                closure,
                {
                    "summary": {"status": "node_alpha_maxed"},
                    "readinessFlags": {
                        "node_alpha_maxed_without_realworld_input": True,
                        "prototype_ready": False,
                        "complete_quantum_computer": False,
                    },
                    "hardStopsRequiringRealWorldInput": [{"requirement": "foundry_pdk"}],
                },
            )

            report = generate_node_alpha_compute_report(
                self.blueprint,
                device_sweep_path=device,
                threshold_sweep_path=threshold,
                resource_sweep_path=resources,
                closure_path=closure,
            )

        self.assertEqual(report["schemaVersion"], "open-quantum.node-alpha-compute-report.v1")
        self.assertTrue(report["scope"]["simulatedOnly"])
        self.assertFalse(report["readinessImpact"]["prototypeReady"])
        self.assertEqual(report["summary"]["deviceRunCount"], 1)

    def test_complete_simulation_executes_full_available_stack_without_overclaiming(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "node-alpha"
            qc = root / "qc-path"
            qc.mkdir(parents=True)
            device = qc / "device-sweep.json"
            threshold = qc / "threshold-sweep.json"
            resources = qc / "resource-sweep.json"
            compute = qc / "node-alpha-compute-report-20260502.json"
            closure = qc / "node-alpha-closure.json"
            dossier = qc / "complete-design-dossier.json"
            mzi = {
                "candidateId": "mzi_best",
                "device": "mzi",
                "acceptanceStatus": "surrogate_gap_probe_only",
                "physicalValidationLevel": "node_alpha_surrogate_not_fdtd",
                "sourceModel": "node_alpha_analytical_surrogate",
                "fdtdMetrics": {
                    "throughRatio": 0.48,
                    "crossRatio": 0.49,
                    "usefulTransmission": 0.97,
                    "insertionLossDb": 0.1,
                    "reflectionRatio": 0.03,
                    "crosstalkRatio": 0.06,
                },
            }
            self._write_json(
                device,
                {
                    "schemaVersion": "open-quantum.device-sweep.v1",
                    "status": "high_resolution_gap_quantified",
                    "runCount": 4,
                    "champion": mzi,
                    "perDeviceChampions": {
                        "coupler": {
                            **mzi,
                            "candidateId": "coupler_best",
                            "device": "coupler",
                            "acceptanceStatus": "surrogate_accepted_candidate",
                        },
                        "mzi": mzi,
                        "phase-shifter": {**mzi, "candidateId": "phase_best", "device": "phase-shifter"},
                        "truth-switch": {**mzi, "candidateId": "truth_best", "device": "truth-switch"},
                    },
                    "perDeviceGapToAcceptance": {
                        "mzi": {"candidateId": "mzi_best", "crosstalkRatioExcess": 0.01},
                    },
                },
            )
            self._write_json(
                threshold,
                {
                    "schemaVersion": "open-quantum.threshold-sweep.v1",
                    "status": "no_below_threshold_candidate",
                    "runCount": 8,
                    "champion": {
                        "candidateId": "d3",
                        "belowThreshold": False,
                        "effectivePhysicalErrorRate": 0.02,
                        "estimatedLogicalErrorRatePerCycle": 0.02,
                    },
                    "acceptedCandidates": [],
                    "blockers": ["No candidate in this sweep falls below the threshold assumption."],
                },
            )
            self._write_json(
                resources,
                {
                    "schemaVersion": "open-quantum.resource-sweep.v1",
                    "runCount": 2,
                    "summary": {"maxLogicalQubits": 18, "maxSinglePhotonSources": 36},
                },
            )
            self._write_json(
                compute,
                {
                    "schemaVersion": "open-quantum.node-alpha-compute-report.v1",
                    "summary": {"deviceRunCount": 4, "thresholdRunCount": 8, "resourceRunCount": 2},
                },
            )
            self._write_json(
                dossier,
                {
                    "schemaVersion": "open-quantum.design-dossier.v1",
                    "summary": {"status": "architecture_dossier_complete"},
                },
            )
            self._write_json(
                closure,
                {
                    "schemaVersion": "open-quantum.node-alpha-closure.v1",
                    "summary": {"status": "node_alpha_maxed"},
                    "readinessFlags": {
                        "node_alpha_maxed_without_realworld_input": True,
                        "prototype_ready": False,
                        "complete_quantum_computer": False,
                    },
                    "hardStopsRequiringRealWorldInput": [
                        {
                            "prototypeCriterion": "foundry_pdk",
                            "reason": "Needs a real version-locked foundry PDK manifest and decks.",
                            "firstBlocker": "missing artifacts: ['foundry_pdk_manifest']",
                        }
                    ],
                },
            )

            report = run_complete_simulation(self.blueprint, artifact_root=root)

        self.assertEqual(report["schemaVersion"], "open-quantum.complete-simulation.v1")
        self.assertTrue(report["scope"]["simulatedOnly"])
        self.assertTrue(report["readinessFlags"]["completeSimulationExecuted"])
        self.assertTrue(report["readinessFlags"]["allReferencedSimulationArtifactsComplete"])
        self.assertFalse(report["readinessFlags"]["simulatedQuantumComputerComplete"])
        self.assertEqual(report["summary"]["status"], "complete_simulation_executed_not_viable")
        self.assertFalse(report["readinessFlags"]["belowThresholdCandidateFound"])
        self.assertIn("mzi", report["simulationLayers"]["deviceSweep"]["perDeviceBestCandidates"])
        self.assertTrue(report["failedReadinessGates"])

    def test_complete_simulation_can_pass_simulation_only_gates(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "node-alpha"
            qc = root / "qc-path"
            qc.mkdir(parents=True)
            device = qc / "device-sweep.json"
            threshold = qc / "threshold-sweep.json"
            resources = qc / "resource-sweep.json"
            compute = qc / "node-alpha-compute-report-pass.json"
            closure = qc / "node-alpha-closure.json"
            dossier = qc / "complete-design-dossier.json"
            truth = {
                "candidateId": "truth_pass",
                "device": "truth-switch",
                "acceptanceStatus": "accepted_first_pass_candidate",
                "physicalValidationLevel": "node_alpha_surrogate_not_fdtd",
                "sourceModel": "node_alpha_analytical_surrogate",
                "fdtdMetrics": {
                    "throughRatio": 2.0,
                    "crossRatio": 2.0,
                    "usefulTransmission": 4.0,
                    "insertionLossDb": 0.0,
                    "reflectionRatio": 0.049,
                    "crosstalkRatio": 0.01,
                    "normalizationReliable": True,
                },
            }
            mzi = {
                **truth,
                "candidateId": "mzi_pass",
                "device": "mzi",
                "fdtdMetrics": {
                    "throughRatio": 0.84,
                    "crossRatio": 0.004,
                    "usefulTransmission": 0.844,
                    "insertionLossDb": 0.73,
                    "reflectionRatio": 0.008,
                    "crosstalkRatio": 0.004,
                    "normalizationReliable": True,
                },
            }
            self._write_json(
                device,
                {
                    "schemaVersion": "open-quantum.device-sweep.v1",
                    "status": "all_requested_devices_accepted",
                    "runCount": 4,
                    "champion": truth,
                    "perDeviceChampions": {
                        "coupler": {
                            **mzi,
                            "candidateId": "coupler_pass",
                            "device": "coupler",
                            "fdtdMetrics": {
                                "throughRatio": 1.0,
                                "crossRatio": 0.99,
                                "usefulTransmission": 1.99,
                                "insertionLossDb": 0.0,
                                "reflectionRatio": 0.0,
                                "crosstalkRatio": 0.01,
                                "normalizationReliable": True,
                            },
                        },
                        "mzi": mzi,
                        "phase-shifter": {**mzi, "candidateId": "phase_pass", "device": "phase-shifter"},
                        "truth-switch": truth,
                    },
                    "perDeviceGapToAcceptance": {
                        device_name: {"candidateId": candidate["candidateId"], "crosstalkRatioExcess": 0.0}
                        for device_name, candidate in {
                            "coupler": {**mzi, "candidateId": "coupler_pass"},
                            "mzi": mzi,
                            "phase-shifter": {**mzi, "candidateId": "phase_pass"},
                            "truth-switch": truth,
                        }.items()
                    },
                },
            )
            self._write_json(
                threshold,
                {
                    "schemaVersion": "open-quantum.threshold-sweep.v1",
                    "status": "below_threshold_candidate_found",
                    "runCount": 8,
                    "champion": {
                        "candidateId": "d5",
                        "belowThreshold": True,
                        "effectivePhysicalErrorRate": 0.0045,
                        "estimatedLogicalErrorRatePerCycle": 0.07,
                    },
                    "acceptedCandidates": [{"candidateId": "d5", "belowThreshold": True}],
                    "blockers": ["analytical only"],
                },
            )
            self._write_json(
                resources,
                {
                    "schemaVersion": "open-quantum.resource-sweep.v1",
                    "runCount": 2,
                    "summary": {"maxLogicalQubits": 18},
                },
            )
            self._write_json(compute, {"schemaVersion": "open-quantum.node-alpha-compute-report.v1", "summary": {}})
            self._write_json(dossier, {"schemaVersion": "open-quantum.design-dossier.v1", "summary": {"status": "architecture_dossier_complete"}})
            self._write_json(
                closure,
                {
                    "schemaVersion": "open-quantum.node-alpha-closure.v1",
                    "summary": {"status": "node_alpha_maxed"},
                    "readinessFlags": {
                        "node_alpha_maxed_without_realworld_input": True,
                        "prototype_ready": False,
                        "complete_quantum_computer": False,
                    },
                    "hardStopsRequiringRealWorldInput": [
                        {"prototypeCriterion": "foundry_pdk", "reason": "Needs foundry PDK."}
                    ],
                },
            )

            report = run_complete_simulation(
                self.blueprint,
                artifact_root=root,
                compute_report_path=compute,
            )

        self.assertEqual(report["summary"]["status"], "complete_simulation_passed")
        self.assertTrue(report["readinessFlags"]["simulatedQuantumComputerComplete"])
        self.assertTrue(report["readinessFlags"]["allReferencedSimulationArtifactsComplete"])
        self.assertFalse(report["readinessFlags"]["realWorldPrototypeReady"])
        self.assertEqual(report["failedReadinessGates"], [])
        self.assertTrue(report["hardStopsRequiringRealWorldInput"])

    def test_testchip_simulation_pipeline_generates_virtual_artifacts(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "testchip"
            report = run_testchip_simulation(self.blueprint, out_dir=out, shots=1000)
            report_written = (out / "testchip-simulation.json").is_file()
            sparams_written = (out / "virtual-sparameters.json").is_file()
            yield_written = (out / "yield-sweep.json").is_file()

        self.assertEqual(report["schemaVersion"], "open-quantum.testchip-simulation.v1")
        self.assertEqual(report["summary"]["status"], "testchip_simulation_complete")
        self.assertTrue(report["readinessFlags"]["testchipSimulationComplete"])
        self.assertTrue(report["readinessFlags"]["deviceSweepAccepted"])
        self.assertTrue(report["readinessFlags"]["virtualSparametersGenerated"])
        self.assertTrue(report["readinessFlags"]["yieldSweepPassing"])
        self.assertTrue(report["readinessFlags"]["fusionTestcellPass"])
        self.assertFalse(report["readinessFlags"]["readyForFabrication"])
        self.assertFalse(
            report["virtualSParameters"]["models"]["coupler"]["foundryCalibrated"]
        )
        self.assertEqual(report["fusionTestcell"]["shots"], 1000)
        self.assertTrue(report_written)
        self.assertTrue(sparams_written)
        self.assertTrue(yield_written)

    def test_testchip_simulation_prefers_best_fusion_candidate(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            device = root / "device-sweep.json"
            coupler = {
                "candidateId": "coupler_best",
                "device": "coupler",
                "acceptanceStatus": "accepted_first_pass_candidate",
                "fdtdMetrics": {
                    "throughRatio": 1.0,
                    "crossRatio": 0.995,
                    "usefulTransmission": 1.995,
                    "insertionLossDb": 0.0,
                    "reflectionRatio": 0.0,
                    "crosstalkRatio": 0.005,
                    "normalizationReliable": True,
                },
            }
            truth = {
                **coupler,
                "candidateId": "truth_pass",
                "device": "truth-switch",
                "fdtdMetrics": {
                    "throughRatio": 1.0,
                    "crossRatio": 0.98,
                    "usefulTransmission": 1.98,
                    "insertionLossDb": 0.0,
                    "reflectionRatio": 0.018,
                    "crosstalkRatio": 0.015,
                    "normalizationReliable": True,
                },
            }
            mzi = {
                **coupler,
                "candidateId": "mzi_pass",
                "device": "mzi",
                "fdtdMetrics": {
                    "throughRatio": 0.98,
                    "crossRatio": 0.01,
                    "usefulTransmission": 0.99,
                    "insertionLossDb": 0.05,
                    "reflectionRatio": 0.005,
                    "crosstalkRatio": 0.01,
                    "normalizationReliable": True,
                },
            }
            self._write_json(
                device,
                {
                    "schemaVersion": "open-quantum.device-sweep.v1",
                    "status": "all_requested_devices_accepted",
                    "runCount": 4,
                    "champion": truth,
                    "perDeviceChampions": {
                        "coupler": coupler,
                        "mzi": mzi,
                        "phase-shifter": {**mzi, "candidateId": "phase_pass", "device": "phase-shifter"},
                        "truth-switch": truth,
                    },
                },
            )

            report = run_testchip_simulation(self.blueprint, out_dir=root / "testchip", device_sweep_path=device)

        self.assertEqual(report["fusionTestcell"]["device"], "coupler")
        self.assertEqual(report["fusionTestcell"]["status"], "fusion_testcell_pass")

    def test_value_package_writes_value_upgrade_artifacts_without_hardware_claim(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "node-alpha"
            qc = root / "qc-path"
            qc.mkdir(parents=True)
            device = qc / "device-sweep.json"
            base = {
                "candidateId": "coupler_best",
                "device": "coupler",
                "acceptanceStatus": "accepted_first_pass_candidate",
                "fdtdMetrics": {
                    "throughRatio": 1.0,
                    "crossRatio": 0.995,
                    "usefulTransmission": 1.995,
                    "insertionLossDb": 0.0,
                    "reflectionRatio": 0.0,
                    "crosstalkRatio": 0.005,
                    "normalizationReliable": True,
                },
            }
            self._write_json(
                device,
                {
                    "schemaVersion": "open-quantum.device-sweep.v1",
                    "status": "all_requested_devices_accepted",
                    "runCount": 4,
                    "champion": base,
                    "perDeviceChampions": {
                        "coupler": base,
                        "mzi": {**base, "candidateId": "mzi_best", "device": "mzi"},
                        "phase-shifter": {**base, "candidateId": "phase_best", "device": "phase-shifter"},
                        "truth-switch": {**base, "candidateId": "truth_best", "device": "truth-switch"},
                    },
                },
            )

            report = generate_value_package(
                self.blueprint,
                artifact_root=root,
                out_dir=root / "value-upgrade",
                device_sweep_path=device,
                syndrome_event_count=12,
                shots=100,
            )
            sparam_manifest_written = (root / "qc-path" / "sparameter-models.json").is_file()
            decoder_written = (root / "qc-path" / "decoder-report.json").is_file()
            syndrome_manifest_written = (root / "qc-path" / "syndrome-noise-dataset.json").is_file()
            templates_written = (root / "evidence-intake" / "templates").is_dir()
            ip_dossier_written = (root / "value-upgrade" / "ip-value-dossier.md").is_file()
            repro_manifest_written = (root / "value-upgrade" / "reproducibility-manifest.json").is_file()
            yield_optimized_written = (root / "value-upgrade" / "yield-optimized-device-sweep.json").is_file()

        self.assertEqual(report["schemaVersion"], "open-quantum.value-upgrade-package.v1")
        self.assertEqual(report["summary"]["status"], "value_package_generated")
        self.assertFalse(report["summary"]["virtualSparameterModelsReadyForFoundryGate"])
        self.assertFalse(report["summary"]["faultToleranceReady"])
        self.assertTrue(report["summary"]["faultToleranceBlocksOnlyOnHardware"])
        self.assertTrue(sparam_manifest_written)
        self.assertTrue(decoder_written)
        self.assertTrue(syndrome_manifest_written)
        self.assertTrue(templates_written)
        self.assertTrue(ip_dossier_written)
        self.assertTrue(repro_manifest_written)
        self.assertTrue(yield_optimized_written)

    def test_value_package_promotes_high_resolution_candidates_for_testchip_yield(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "node-alpha"
            qc = root / "qc-path"
            qc.mkdir(parents=True)
            device = qc / "device-sweep.json"
            weak = {
                "candidateId": "weak",
                "device": "coupler",
                "acceptanceStatus": "accepted_first_pass_candidate",
                "fdtdMetrics": {
                    "throughRatio": 0.96,
                    "crossRatio": 0.047,
                    "usefulTransmission": 1.007,
                    "insertionLossDb": 0.0,
                    "reflectionRatio": 0.049,
                    "crosstalkRatio": 0.047,
                    "normalizationReliable": True,
                },
            }
            self._write_json(
                device,
                {
                    "schemaVersion": "open-quantum.device-sweep.v1",
                    "status": "all_requested_devices_accepted",
                    "runCount": 4,
                    "perDeviceChampions": {
                        "coupler": {**weak, "candidateId": "weak_coupler", "device": "coupler"},
                        "mzi": {**weak, "candidateId": "weak_mzi", "device": "mzi"},
                        "phase-shifter": {**weak, "candidateId": "weak_phase", "device": "phase-shifter"},
                        "truth-switch": {**weak, "candidateId": "weak_truth", "device": "truth-switch"},
                    },
                },
            )
            strong_metrics = {
                "throughRatio": 0.97,
                "crossRatio": 0.01,
                "usefulTransmission": 0.98,
                "insertionLossDb": 0.0,
                "reflectionRatio": 0.001,
                "crosstalkRatio": 0.01,
                "normalizationReliable": True,
            }
            per_device = {
                device_name: {
                    "candidateId": f"strong_{device_name}",
                    "device": device_name,
                    "acceptanceStatus": "accepted_first_pass_candidate",
                    "fdtdMetrics": strong_metrics,
                }
                for device_name in ("coupler", "mzi", "phase-shifter", "truth-switch")
            }
            self._write_json(
                qc / "mission-20990101000000-yield-device-sweep.json",
                {
                    "runId": "mission-20990101000000-yield",
                    "report": {
                        "schemaVersion": "open-quantum.device-sweep.v1",
                        "status": "all_requested_devices_accepted",
                        "resolution": 20,
                        "until": 60,
                        "runCount": 4,
                        "deviceCoverage": {
                            "requestedDevices": ["coupler", "mzi", "phase-shifter", "truth-switch"],
                            "observedDevices": ["coupler", "mzi", "phase-shifter", "truth-switch"],
                            "missingDevices": [],
                            "complete": True,
                        },
                        "perDeviceChampions": per_device,
                        "perDeviceGapToAcceptance": {
                            device_name: {
                                "device": device_name,
                                "candidateId": f"strong_{device_name}",
                                "normalizationReliable": True,
                                "crosstalkRatioExcess": 0.0,
                                "reflectionRatioExcess": 0.0,
                                "insertionLossDbExcess": 0.0,
                                "usefulTransmission": 0.98,
                                "usefulTransmissionTarget": 0.5,
                                "outputPortNormalizationFlux": 1.0,
                                "outputPortNormalizationFluxTarget": 1e-8,
                            }
                            for device_name in ("coupler", "mzi", "phase-shifter", "truth-switch")
                        },
                    },
                },
            )

            report = generate_value_package(
                self.blueprint,
                artifact_root=root,
                out_dir=root / "value-upgrade",
                device_sweep_path=device,
                syndrome_event_count=12,
                shots=100,
            )
            optimized = json.loads((root / "value-upgrade" / "yield-optimized-device-sweep.json").read_text())

        self.assertEqual(report["summary"]["testchipYieldDeviceSource"], "promote_accepted_20_60_high_resolution_candidates_for_testchip_yield")
        self.assertEqual(report["summary"]["testchipSystemYieldEstimate"], 1.0)
        self.assertEqual(report["summary"]["testchipYieldAcceptedDevices"], 4)
        self.assertEqual(optimized["sourceSelection"]["promotedDevices"], ["coupler", "mzi", "phase-shifter", "truth-switch"])

    def test_value_scorecard_writes_diligence_artifacts_without_prototype_claim(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "node-alpha"
            docs = Path(tmp) / "docs"
            for directory in [
                root / "value-upgrade-20260502" / "testchip",
                root / "qc-path",
                root / "gds-path",
                root / "no-budget-package",
            ]:
                directory.mkdir(parents=True, exist_ok=True)
            self._write_json(
                root / "value-upgrade-20260502" / "value-upgrade-report.json",
                {
                    "summary": {
                        "status": "value_package_generated",
                        "thresholdStatus": "below_threshold_candidate_found",
                        "thresholdChampionLogicalErrorRate": 2.5e-7,
                        "syntheticSyndromeEventCount": 10000,
                    }
                },
            )
            self._write_json(
                root / "value-upgrade-20260502" / "high-resolution-robustness-report.json",
                {
                    "summary": {
                        "status": "all_core_devices_high_resolution_accepted",
                        "acceptedDevices": ["coupler", "mzi", "phase-shifter", "truth-switch"],
                        "blockedDevices": [],
                        "allRequiredDevicesAccepted": True,
                    }
                },
            )
            self._write_json(
                root / "value-upgrade-20260502" / "testchip" / "yield-sweep.json",
                {"summary": {"allDevicesYieldPassing": False, "systemYieldEstimate": 0.024}},
            )
            self._write_json(
                root / "qc-path" / "fault-tolerance-audit.json",
                {
                    "readinessFlags": {
                        "fault_tolerance_ready": False,
                        "hardware_calibrated_noise_available": False,
                        "below_threshold_evidence": True,
                        "decoder_implemented": True,
                    }
                },
            )
            self._write_json(
                root / "qc-path" / "sparameter-audit.json",
                {
                    "readinessFlags": {
                        "all_core_sparameters_present": True,
                        "all_hashes_verified": True,
                        "foundry_calibrated_sparameters": False,
                        "sparameter_models_ready": False,
                    }
                },
            )
            self._write_json(
                root / "gds-path" / "gds-audit.json",
                {
                    "auditFlags": {
                        "gds_generated": True,
                        "layout_computable": True,
                        "not_tapeout_ready": True,
                        "foundry_pdk_missing": True,
                        "drc_not_run": True,
                        "lvs_not_run": True,
                    }
                },
            )
            self._write_json(
                root / "qc-path" / "prototype-readiness.json",
                {
                    "summary": {
                        "status": "not_prototype_ready",
                        "completeCriteria": 1,
                        "totalCriteria": 9,
                        "highestPriorityBlocker": "No foundry-calibrated S-parameter compact models are attached.",
                    }
                },
            )
            self._write_json(
                root / "report-index.json",
                {"artifactCount": 3, "presentArtifactCount": 3, "missingArtifactCount": 0},
            )
            self._write_json(
                root / "no-budget-package" / "no-budget-readiness.json",
                {"constraint": "zero_cash_budget_no_paid_foundry_no_paid_lab_no_paid_patent_work"},
            )
            for name in [
                "no-budget-partner-package.md",
                "30-minute-reproduction.md",
                "preprint-outline.md",
                "open-validation-issues.md",
            ]:
                target = docs / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("# doc\n", encoding="utf-8")

            report = generate_value_scorecard(self.blueprint, artifact_root=root, out_dir=root / "score", docs_dir=docs)
            scorecard_markdown_written = (root / "score" / "value-scorecard.md").is_file()
            partner_outreach_written = (docs / "partner-outreach.md").is_file()
            grant_concept_written = (docs / "grant-concept-note.md").is_file()
            data_room_written = (docs / "data-room-index.md").is_file()
            reviewer_pack_written = (docs / "reviewer-pack.md").is_file()
            partner_pipeline_written = (docs / "partner-pipeline.md").is_file()

        self.assertEqual(report["schemaVersion"], "open-quantum.value-scorecard.v1")
        self.assertEqual(report["summary"]["status"], "value_scorecard_generated")
        self.assertFalse(report["summary"]["prototypeReady"])
        self.assertFalse(report["summary"]["tapeoutReady"])
        self.assertFalse(report["summary"]["foundrySparametersReady"])
        self.assertGreaterEqual(report["summary"]["partnerDiligenceReadiness"], 70)
        self.assertEqual(report["summary"]["reviewerQuestionCount"], 6)
        self.assertEqual(report["summary"]["partnerPipelineStageCount"], 4)
        self.assertGreaterEqual(report["summary"]["activeCriticalRiskCount"], 2)
        self.assertIn("scoreBreakdown", report)
        self.assertIn("diligenceRiskRegister", report)
        self.assertIn("claimReadinessMatrix", report)
        self.assertIn("valueLadder", report)
        self.assertIn("valuationConfidence", report)
        self.assertIn("assumptionRegister", report)
        self.assertIn("reviewerQuestionBank", report)
        self.assertIn("partnerPipeline", report)
        self.assertEqual(len(report["assumptionRegister"]), 5)
        self.assertEqual(len(report["reviewerQuestionBank"]), 6)
        self.assertEqual(len(report["partnerPipeline"]), 4)
        self.assertTrue(any(risk["id"] == "virtual_sparameter_gap" for risk in report["diligenceRiskRegister"]))
        self.assertTrue(any(claim["id"] == "tapeout_ready" and not claim["ready"] for claim in report["claimReadinessMatrix"]))
        self.assertTrue(scorecard_markdown_written)
        self.assertTrue(partner_outreach_written)
        self.assertTrue(grant_concept_written)
        self.assertTrue(data_room_written)
        self.assertTrue(reviewer_pack_written)
        self.assertTrue(partner_pipeline_written)

    def test_performance_upgrade_writes_scaling_threshold_and_throughput_reports(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "node-alpha"
            out = root / "performance"
            threshold_dir = root / "value-upgrade-20260502"
            threshold_dir.mkdir(parents=True, exist_ok=True)
            self._write_json(
                threshold_dir / "threshold-device-candidate.json",
                {
                    "schemaVersion": "open-quantum.eigenmode-device.v1",
                    "device": "coupler",
                    "candidateId": "coupler_test_threshold",
                    "physicalValidationLevel": "eigenmode_calibrated_2d_first_pass",
                    "fdtdMetrics": {
                        "usefulTransmission": 1.9904991626163309,
                        "insertionLossDb": 0.0,
                        "reflectionRatio": 0.0,
                        "crosstalkRatio": 0.009500837383627836,
                        "normalizationReliable": True,
                    },
                },
            )
            truth_dir = root / "qc-path"
            truth_dir.mkdir(parents=True, exist_ok=True)
            self._write_json(
                truth_dir / "truth-switch-low-crosstalk.json",
                {
                    "schemaVersion": "open-quantum.eigenmode-device.v1",
                    "device": "truth-switch",
                    "candidateId": "truth_switch_low_crosstalk_seed",
                    "physicalValidationLevel": "node_alpha_surrogate_not_fdtd",
                    "sourceModel": "node_alpha_analytical_surrogate",
                    "fdtdMetrics": {
                        "usefulTransmission": 4.0,
                        "insertionLossDb": 0.0,
                        "reflectionRatio": 0.018,
                        "crosstalkRatio": 0.0,
                        "normalizationReliable": True,
                    },
                },
            )

            report = generate_performance_upgrade(
                self.blueprint,
                artifact_root=root,
                out_dir=out,
                focused_max_runs=160,
            )
            performance_written = (out / "performance-upgrade-report.json").is_file()
            throughput_written = (out / "throughput-report.json").is_file()
            resource_written = (out / "resource-scaling-report.json").is_file()
            envelope_written = (out / "operational-envelope-report.json").is_file()
            joint_budget_written = (out / "joint-error-budget-report.json").is_file()
            optimizer_written = (out / "budget-optimizer-report.json").is_file()
            hardened_profile_written = (out / "hardened-simulation-profile.json").is_file()
            virtual_sparams_written = (out / "virtual-sparameter-acceptance-report.json").is_file()
            scaled_layout_written = (out / "scaled-layout-envelope-report.json").is_file()
            max_qubit_written = (out / "max-qubit-envelope-report.json").is_file()
            control_timing_written = (out / "control-timing-model-report.json").is_file()
            decoder_written = (out / "decoder-evidence-report.json").is_file()
            stress_written = (out / "stress-recovery-report.json").is_file()
            truth_raw_written = (out / "truth-switch-raw-closure-report.json").is_file()
            pareto_written = (out / "multiobjective-pareto-report.json").is_file()
            corner_written = (out / "worst-case-corner-sweep-report.json").is_file()
            monte_carlo_written = (out / "monte-carlo-robustness-report.json").is_file()
            consistency_written = (out / "internal-consistency-audit.json").is_file()
            scorecard_written = (out / "deep-hardening-v3-scorecard.json").is_file()
            deep_markdown_written = (out / "deep-hardening-v3-report.md").is_file()
            no_go_written = (out / "max-qubit-no-go-map-report.json").is_file()
            prototype_gap_written = (out / "prototype-gap-reduction-report.json").is_file()

        self.assertEqual(report["schemaVersion"], "open-quantum.deep-hardening-v3.v1")
        self.assertEqual(report["summary"]["status"], "deep_hardening_v3_generated")
        self.assertEqual(report["summary"]["maxScaledPhysicalModes"], 760)
        self.assertEqual(report["summary"]["maxScaledLogicalQubits"], 380)
        self.assertEqual(report["summary"]["maxQubitEnvelopePhysicalModes"], 760)
        self.assertEqual(report["summary"]["maxQubitEnvelopeLogicalQubits"], 380)
        self.assertEqual(report["summary"]["nextRejectedQubitEnvelopePhysicalModes"], 768)
        self.assertTrue(report["summary"]["target1e8LogicalErrorMet"])
        self.assertTrue(report["summary"]["target1e9LogicalErrorMet"])
        self.assertTrue(report["summary"]["fusionTargetMetInNominalScenario"])
        self.assertGreater(report["summary"]["bestNominalFusionSuccessProbability"], 0.9995)
        self.assertGreaterEqual(report["summary"]["bestNominalFusionFidelity"], 0.999995)
        self.assertGreater(report["summary"]["bestStretchFusionSuccessProbability"], 0.9999)
        self.assertGreaterEqual(report["summary"]["bestStretchFusionFidelity"], 0.999995)
        self.assertTrue(report["summary"]["fusionStretchTargetMet"])
        self.assertTrue(report["summary"]["truthSwitchStrictTargetMet"])
        self.assertEqual(report["summary"]["target1e9OperationalEnvelopeDistance"], 61)
        self.assertGreater(report["summary"]["target1e9MaxSingleAxisLossDb"], 0.40)
        self.assertLess(report["summary"]["target1e9MinSingleAxisDetectorEfficiency"], 0.85)
        self.assertGreater(report["summary"]["target1e9MaxSingleAxisPhaseErrorRad"], 0.25)
        self.assertGreater(report["summary"]["target1e9MaxSingleAxisFeedForwardLatencyNs"], 350.0)
        self.assertTrue(report["summary"]["target1e9HardeningMarginTargetsMet"])
        self.assertTrue(report["summary"]["target1e9JointBudgetPass"])
        self.assertLessEqual(report["summary"]["target1e9JointBudgetLogicalErrorRate"], 1e-9)
        self.assertGreater(report["summary"]["target1e9JointBudgetReserve"], 0.0)
        self.assertGreater(report["summary"]["target1e9OptimizedProfileCount"], 0)
        self.assertLessEqual(report["summary"]["target1e9OptimizedBalancedLogicalErrorRate"], 1e-9)
        self.assertLess(report["summary"]["target1e9DetectorRelaxedMinEfficiency"], 0.85)
        self.assertGreater(report["summary"]["target1e9LatencyRelaxedMaxFeedForwardLatencyNs"], 350.0)
        self.assertGreater(report["summary"]["maxUpperBoundHeraldedEventsPerSecond"], 0)
        self.assertLessEqual(report["summary"]["maxUpperBoundFusionAttemptsPerSecond"], 200_000_000.0)
        self.assertIn("virtualSparameterAcceptance", report)
        self.assertEqual(report["summary"]["virtualSparameterAcceptedDeviceCount"], 4)
        self.assertLess(report["summary"]["maxVirtualSparameterCrosstalkRatio"], 0.003)
        self.assertLess(report["summary"]["maxVirtualSparameterReflectionRatio"], 0.00008)
        self.assertTrue(report["summary"]["allVirtualSparameterCrosstalkBelow1Percent"])
        self.assertTrue(report["summary"]["allVirtualSparameterReflectionBelow0p05Percent"])
        self.assertTrue(report["summary"]["allVirtualSparameterCrosstalkBelow0p30Percent"])
        self.assertTrue(report["summary"]["allVirtualSparameterReflectionBelow0p008Percent"])
        self.assertTrue(report["summary"]["allVirtualSparameterCrosstalkBelow0p25Percent"])
        self.assertTrue(report["summary"]["allVirtualSparameterReflectionBelow0p005Percent"])
        self.assertEqual(report["summary"]["maxScaledPhysicalModes"], report["scaledLayoutEnvelope"]["summary"]["maxPhysicalModes"])
        self.assertLess(report["summary"]["maxScaledLayoutAreaMm2"], 22.0)
        self.assertLess(report["summary"]["maxScaledLayoutAreaMm2"], 18.0)
        self.assertLess(_max_qubit_row(report, 704)["chipAreaMm2"], 17.5)
        self.assertLess(_max_qubit_row(report, 712)["chipAreaMm2"], 18.0)
        self.assertTrue(_max_qubit_row(report, 760)["feasibleUnderV3Envelope"])
        self.assertFalse(_max_qubit_row(report, 768)["feasibleUnderV3Envelope"])
        self.assertGreater(report["summary"]["maxScaledLayoutRouteReductionFraction"], 0.45)
        self.assertLessEqual(report["summary"]["maxEffectiveOpticalPackagePortCount"], 96)
        self.assertLessEqual(report["summary"]["maxEffectiveElectricalPackagePadCount"], 176)
        self.assertTrue(report["scaledLayoutEnvelope"]["summary"]["packageEnvelopeTargetMet"])
        self.assertTrue(report["summary"]["scaledLayoutAreaTargetMet"])
        self.assertTrue(report["summary"]["scaledLayoutAreaStretchTargetMet"])
        self.assertTrue(report["summary"]["target1e9ControlTimingPass"])
        self.assertLess(report["summary"]["fastPathBestLatencyNs"], 1.3)
        self.assertTrue(report["summary"]["fullDecoderSeparatedFromFastPath"])
        self.assertIsNotNone(report["summary"]["target1e9ToyDecoderLatencyNs"])
        self.assertLess(report["summary"]["target1e9ToyDecoderLatencyNs"], 15.0)
        self.assertGreaterEqual(report["summary"]["target1e9StressRecoveryScaleFactor"], 1.0)
        self.assertLessEqual(report["summary"]["target1e9StressRecoveryScaleFactor"], 1.0)
        self.assertTrue(report["summary"]["combinedStressPointPass"])
        self.assertTrue(report["summary"]["worstCaseStressPointPass"])
        self.assertTrue(report["summary"]["truthSwitchRawStrictTargetMet"])
        self.assertLess(report["summary"]["truthSwitchRawBestCrosstalkRatio"], 0.003)
        self.assertLess(report["summary"]["truthSwitchRawBestReflectionRatio"], 0.00008)
        self.assertTrue(report["summary"]["truthSwitchRawStretchTargetMet"])
        self.assertFalse(report["summary"]["virtualSparameterReadyForFoundryClaim"])
        self.assertTrue(report["maxQubitNoGoMap"]["closedMilestones"]["target712ClosedUnder18mm2"])
        self.assertTrue(report["maxQubitNoGoMap"]["closedMilestones"]["target760ClosedUnder18mm2"])
        self.assertTrue(report["maxQubitNoGoMap"]["closedMilestones"]["target760WithinPackageCeilings"])
        self.assertGreater(report["summary"]["paretoFrontCandidateCount"], 0)
        self.assertTrue(report["summary"]["worstCaseCornerSweepPass"])
        self.assertTrue(report["summary"]["monteCarloRobustnessPass"])
        self.assertEqual(report["monteCarloRobustness"]["summary"]["passFraction"], 1.0)
        self.assertLess(report["monteCarloRobustness"]["summary"]["worstTruthSwitchCrosstalkRatio"], 0.0035)
        self.assertLess(report["monteCarloRobustness"]["summary"]["worstTruthSwitchReflectionRatio"], 0.0001)
        self.assertEqual(report["worstCaseCornerSweep"]["summary"]["cornerCountPerDevice"], 1875)
        self.assertTrue(report["summary"]["internalConsistencyPass"])
        self.assertEqual(report["summary"]["deepHardeningScore"], 110)
        self.assertGreaterEqual(report["summary"]["prototypeLocalSimulationCriteriaImproved"], 5)
        self.assertEqual(report["completionAudit"]["decision"], "complete")
        self.assertTrue(performance_written)
        self.assertTrue(throughput_written)
        self.assertTrue(resource_written)
        self.assertTrue(envelope_written)
        self.assertTrue(joint_budget_written)
        self.assertTrue(optimizer_written)
        self.assertTrue(hardened_profile_written)
        self.assertTrue(virtual_sparams_written)
        self.assertTrue(scaled_layout_written)
        self.assertTrue(max_qubit_written)
        self.assertTrue(control_timing_written)
        self.assertTrue(decoder_written)
        self.assertTrue(stress_written)
        self.assertTrue(truth_raw_written)
        self.assertTrue(pareto_written)
        self.assertTrue(corner_written)
        self.assertTrue(monte_carlo_written)
        self.assertTrue(consistency_written)
        self.assertTrue(scorecard_written)
        self.assertTrue(deep_markdown_written)
        self.assertTrue(no_go_written)
        self.assertTrue(prototype_gap_written)

    def test_public_docs_and_committed_reports_do_not_reference_excluded_artifact_paths(self):
        root = Path(__file__).resolve().parents[1]
        inspected_paths = [
            root / "README.md",
            root / "ARTIFACTS.md",
            root / "docs" / "evidence-ledger.json",
            root / "docs" / "assumption-ledger.md",
            root / "reports" / "node-alpha" / "report-index.json",
        ]
        inspected_paths.extend(sorted((root / "docs").glob("*.md")))
        inspected_paths.extend(sorted((root / "reports" / "node-alpha" / "deep-hardening-v3-20260502").glob("*")))
        forbidden_fragments = [
            "reports/node-alpha/value-upgrade-20260502",
            "reports/node-alpha/no-budget-package",
            "reports/node-alpha/gds-path",
            "notebooks/node-alpha-report-summary.ipynb",
            "Technical evidence score",
            "MZI useful transmission",
        ]
        offenders = []
        for path in inspected_paths:
            text = path.read_text(encoding="utf-8")
            for fragment in forbidden_fragments:
                if fragment in text:
                    offenders.append(f"{path.relative_to(root)} contains {fragment}")

        self.assertEqual(offenders, [])

    def test_public_evidence_ledger_keeps_strong_metrics_non_hardware(self):
        root = Path(__file__).resolve().parents[1]
        ledger = json.loads((root / "docs" / "evidence-ledger.json").read_text(encoding="utf-8"))
        self.assertEqual(ledger["schemaVersion"], "open-quantum.public-evidence-ledger.v1")
        self.assertFalse(ledger["readiness"]["tapeoutReady"])
        self.assertFalse(ledger["readiness"]["prototypeReady"])
        self.assertEqual(ledger["readiness"]["foundryCalibratedSparameters"], "absent_0_of_4")
        self.assertGreaterEqual(len(ledger["metrics"]), 10)
        for metric in ledger["metrics"]:
            self.assertIn("artifact", metric)
            self.assertIn("evidenceLevel", metric)
            self.assertIn("notEvidenceFor", metric)
            self.assertTrue(metric["notEvidenceFor"])
            self.assertNotIn("hardware_measured", metric["evidenceLevel"])

    def test_artifacts_markdown_matches_machine_readable_hash_manifest(self):
        root = Path(__file__).resolve().parents[1]
        manifest_rows = {}
        for line in (root / "ARTIFACTS.sha256").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, artifact = line.split("  ", 1)
            manifest_rows[artifact] = digest

        markdown = (root / "ARTIFACTS.md").read_text(encoding="utf-8")
        self.assertIn("generated from `ARTIFACTS.sha256`", markdown)
        missing = []
        for artifact, digest in manifest_rows.items():
            row = f"| `{digest}` | `{artifact}` |"
            if row not in markdown:
                missing.append(row)

        self.assertEqual(missing, [])

    def test_device_score_penalizes_reflection_and_loss(self):
        report = {
            "fdtdMetrics": {
                "throughRatio": 0.45,
                "crossRatio": 0.45,
                "reflectionRatio": 0.1,
                "insertionLossDb": 0.5,
            }
        }
        self.assertGreater(score_device(report), 0)

    def test_device_score_rejects_unreliable_normalization_champions(self):
        unreliable = {
            "fdtdMetrics": {
                "throughRatio": 40.0,
                "crossRatio": 5.0,
                "reflectionRatio": 0.0,
                "insertionLossDb": 0.0,
                "usefulTransmission": 45.0,
                "crosstalkRatio": 8.0,
                "normalizationReliable": False,
                "outputPortNormalizationFlux": 1e-10,
            }
        }
        reliable = {
            "fdtdMetrics": {
                "throughRatio": 0.6,
                "crossRatio": 0.3,
                "reflectionRatio": 0.01,
                "insertionLossDb": 0.4,
                "usefulTransmission": 0.9,
                "crosstalkRatio": 0.02,
                "normalizationReliable": True,
                "outputPortNormalizationFlux": 1e-6,
            }
        }
        self.assertGreater(score_device(reliable), score_device(unreliable))

    def test_eigenmode_metrics_use_output_port_reference(self):
        metrics = _normalized_flux_metrics(
            device="mzi",
            reference={"inputFlux": 10.0, "throughFlux": 0.005, "crossFlux": 0.0},
            measured={"inputFlux": 9.9, "throughFlux": 0.0045, "crossFlux": 0.00025},
        )
        self.assertAlmostEqual(metrics["throughRatio"], 0.9)
        self.assertAlmostEqual(metrics["crossRatio"], 0.05)
        self.assertAlmostEqual(metrics["usefulTransmission"], 0.95)
        self.assertLess(metrics["insertionLossDb"], 0.3)
        self.assertAlmostEqual(metrics["reflectionRatio"], 0.01)

    def test_eigenmode_device_uses_node_alpha_surrogate_when_meep_missing(self):
        from oqp.eigenmode_device import run_eigenmode_device

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "meep":
                raise ModuleNotFoundError("No module named 'meep'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            report = run_eigenmode_device(
                self.blueprint,
                device="coupler",
                coupling_gap_um=0.14,
                coupling_length_um=8.0,
                phase_shift_rad=0.0,
                waveguide_width_um=0.45,
                resolution=16,
                until=40,
            )

        self.assertEqual(report["backend"], "node_alpha_analytical_surrogate")
        self.assertEqual(report["physicalValidationLevel"], "node_alpha_surrogate_not_fdtd")
        self.assertEqual(report["sourceModel"], "node_alpha_analytical_surrogate")
        self.assertIn("Analytical surrogate", report["limitations"][0])
        self.assertTrue(report["fdtdMetrics"]["normalizationReliable"])

    def test_device_sweep_interleaves_devices_with_run_budget(self):
        devices = ["coupler", "mzi", "phase-shifter", "truth-switch"]

        def fake_device_report(
            blueprint,
            *,
            device,
            resolution,
            until,
            coupling_gap_um,
            coupling_length_um,
            phase_shift_rad,
            waveguide_width_um,
        ):
            return {
                "schemaVersion": "open-quantum.eigenmode-device.v1",
                "sourcePath": blueprint.source_path,
                "device": device,
                "accepted": False,
                "acceptanceStatus": "not_accepted_first_pass",
                "physicalValidationLevel": "eigenmode_calibrated_2d_first_pass",
                "fdtdMetrics": {
                    "throughRatio": 0.1,
                    "crossRatio": 0.01,
                    "reflectionRatio": 0.0,
                    "insertionLossDb": 10.0,
                    "usefulTransmission": 0.11,
                },
            }

        with patch("oqp.device_sweep.run_eigenmode_device", side_effect=fake_device_report):
            report = run_device_sweep(
                self.blueprint,
                devices=devices,
                coupling_gaps_um=[0.18, 0.2],
                coupling_lengths_um=[3.0, 6.0],
                phase_shifts_rad=[0.0, 1.5708],
                waveguide_widths_um=[0.45],
                max_runs=len(devices),
            )

        self.assertEqual(report["runCount"], len(devices))
        self.assertTrue(report["deviceCoverage"]["complete"])
        self.assertEqual(report["deviceCoverage"]["observedDevices"], sorted(devices))
        self.assertEqual(set(report["perDeviceChampions"]), set(devices))

    def test_device_evidence_prefers_reliable_candidate_over_inflated_ratios(self):
        with TemporaryDirectory() as tmp:
            unreliable = {
                "schemaVersion": "open-quantum.eigenmode-device.v1",
                "device": "coupler",
                "physicalValidationLevel": "eigenmode_calibrated_2d_first_pass",
                "simulationModelVersion": DEVICE_SIMULATION_MODEL_VERSION,
                "fdtdMetrics": {
                    "usefulTransmission": 50.0,
                    "insertionLossDb": 0.0,
                    "reflectionRatio": 0.0,
                    "crosstalkRatio": 5.0,
                    "normalizationReliable": False,
                    "outputPortNormalizationFlux": 1e-10,
                },
            }
            reliable = {
                "schemaVersion": "open-quantum.eigenmode-device.v1",
                "device": "coupler",
                "physicalValidationLevel": "eigenmode_calibrated_2d_first_pass",
                "simulationModelVersion": DEVICE_SIMULATION_MODEL_VERSION,
                "fdtdMetrics": {
                    "usefulTransmission": 0.8,
                    "insertionLossDb": 0.5,
                    "reflectionRatio": 0.01,
                    "crosstalkRatio": 0.1,
                    "normalizationReliable": True,
                    "outputPortNormalizationFlux": 1e-6,
                },
            }
            with open(f"{tmp}/coupler-unreliable.json", "w", encoding="utf-8") as handle:
                json.dump(unreliable, handle)
            with open(f"{tmp}/coupler-reliable.json", "w", encoding="utf-8") as handle:
                json.dump(reliable, handle)

            evidence = collect_device_evidence(evidence_dir=tmp)

        self.assertEqual(evidence["byDevice"]["coupler"]["evidenceId"], "coupler:coupler-reliable.json")

    def test_device_sweep_rerank_uses_existing_candidate_files(self):
        with TemporaryDirectory() as tmp:
            unreliable = {
                "schemaVersion": "open-quantum.eigenmode-device.v1",
                "device": "coupler",
                "candidateId": "coupler_bad_norm",
                "fdtdMetrics": {
                    "throughRatio": 40.0,
                    "crossRatio": 5.0,
                    "usefulTransmission": 45.0,
                    "insertionLossDb": 0.0,
                    "reflectionRatio": 0.0,
                    "crosstalkRatio": 8.0,
                    "normalizationReliable": False,
                    "outputPortNormalizationFlux": 1e-10,
                    "timing": {"resolution": 16, "until": 40},
                },
            }
            reliable = {
                "schemaVersion": "open-quantum.eigenmode-device.v1",
                "device": "coupler",
                "candidateId": "coupler_reliable",
                "fdtdMetrics": {
                    "throughRatio": 0.7,
                    "crossRatio": 0.1,
                    "usefulTransmission": 0.8,
                    "insertionLossDb": 0.2,
                    "reflectionRatio": 0.01,
                    "crosstalkRatio": 0.05,
                    "normalizationReliable": True,
                    "outputPortNormalizationFlux": 1e-6,
                    "timing": {"resolution": 16, "until": 40},
                },
            }
            with open(f"{tmp}/bad.json", "w", encoding="utf-8") as handle:
                json.dump(unreliable, handle)
            with open(f"{tmp}/reliable.json", "w", encoding="utf-8") as handle:
                json.dump(reliable, handle)

            report = rerank_device_sweep(self.blueprint, evidence_dir=tmp, devices=["coupler"])

        self.assertTrue(report["rerankedFromExistingEvidence"])
        self.assertEqual(report["champion"]["candidateId"], "coupler_reliable")
        self.assertEqual(report["perDeviceChampions"]["coupler"]["candidateId"], "coupler_reliable")


    def _write_json(self, path: Path, payload: dict):
        path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
