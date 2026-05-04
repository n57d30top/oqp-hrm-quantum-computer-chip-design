"""Generic SiPh GDS generation for OQP-HRM pre-tapeout milestones."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import struct
from typing import Any, Iterable

from .blueprint import Blueprint
from .topology import connected_component_count, mzi_pairs


SCHEMA_PREFIX = "open-quantum"
DEFAULT_EVIDENCE_DIR = Path("reports/node-alpha/qc-path")
DEFAULT_GDS_OUT_DIR = Path("reports/node-alpha/gds-path")
TOP_CELL_NAME = "OQP_HRM_TOP"
LIBRARY_NAME = "OQP_HRM_GENERIC_SIPH"


@dataclass(frozen=True)
class LayerSpec:
    name: str
    layer: int
    datatype: int
    purpose: str
    description: str


@dataclass(frozen=True)
class CellPort:
    name: str
    kind: str
    x_um: float
    y_um: float
    direction: str
    layer: str


@dataclass(frozen=True)
class CellTemplate:
    name: str
    component_type: str
    status: str
    width_um: float
    height_um: float
    bbox_um: tuple[float, float, float, float]
    ports: tuple[CellPort, ...]
    polygons: tuple[dict[str, Any], ...]
    evidence_refs: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass
class GdsDesign:
    manifest: dict[str, Any]
    cells: list[dict[str, Any]]


GENERIC_SIPH_LAYER_MAP: tuple[LayerSpec, ...] = (
    LayerSpec("WG", 1, 0, "waveguide", "Generic silicon waveguide core."),
    LayerSpec("ETCH", 2, 0, "etch", "Generic partial/full etch placeholder."),
    LayerSpec("SLAB", 3, 0, "slab", "Generic slab/implant keep geometry."),
    LayerSpec("DEVICE", 10, 0, "device", "Device marker and placeholder body."),
    LayerSpec("HEATER", 20, 0, "metal", "Thermal/electro-optic heater placeholder."),
    LayerSpec("METAL", 21, 0, "metal", "Generic electrical routing metal."),
    LayerSpec("VIA", 22, 0, "via", "Generic via/contact placeholder."),
    LayerSpec("PAD", 30, 0, "pad", "Electrical pad opening/landing metal."),
    LayerSpec("PORT", 40, 0, "port", "Optical and electrical port markers."),
    LayerSpec("LABEL", 50, 0, "label", "Human-readable text labels."),
    LayerSpec("KEEPOUT", 60, 0, "keepout", "Chip, fiber-array, and routing keepouts."),
    LayerSpec("PACKAGE", 70, 0, "package", "Package/fiber-array planning markers."),
)


def generate_gds_plan(
    blueprint: Blueprint,
    *,
    pdk: str = "generic-si-photonics",
    evidence_dir: str | Path | None = DEFAULT_EVIDENCE_DIR,
    device_reports: list[str | Path] | None = None,
    lane_pitch_um: float = 18.0,
    mzi_pitch_um: float = 160.0,
    fiber_pitch_um: float = 127.0,
) -> dict[str, Any]:
    design = build_gds_design(
        blueprint,
        pdk=pdk,
        evidence_dir=evidence_dir,
        device_reports=device_reports,
        lane_pitch_um=lane_pitch_um,
        mzi_pitch_um=mzi_pitch_um,
        fiber_pitch_um=fiber_pitch_um,
    )
    manifest = design.manifest
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.gds-plan.v1",
        "generatedAt": manifest["generatedAt"],
        "sourcePath": blueprint.source_path,
        "pdk": manifest["pdk"],
        "units": manifest["units"],
        "layoutComputable": True,
        "gdsGenerated": False,
        "topCell": manifest["topCell"],
        "layerMap": manifest["layerMap"],
        "topLevelLayout": manifest["topLevelLayout"],
        "fiberIoPlan": manifest["fiberIoPlan"],
        "componentLibrary": manifest["componentLibrary"],
        "cellRegistry": manifest["cellRegistry"],
        "routingStats": manifest["routingStats"],
        "layerUsage": manifest["layerUsage"],
        "deviceEvidence": manifest["deviceEvidence"],
        "layoutCompletion": _layout_completion_report(manifest),
        "readinessFlags": {
            **manifest["readinessFlags"],
            "gds_generated": False,
        },
        "blockers": manifest["blockers"],
        "nextSteps": manifest["nextSteps"],
    }


def generate_gds_manifest(
    blueprint: Blueprint,
    *,
    pdk: str = "generic-si-photonics",
    evidence_dir: str | Path | None = DEFAULT_EVIDENCE_DIR,
    device_reports: list[str | Path] | None = None,
    lane_pitch_um: float = 18.0,
    mzi_pitch_um: float = 160.0,
    fiber_pitch_um: float = 127.0,
) -> dict[str, Any]:
    return build_gds_design(
        blueprint,
        pdk=pdk,
        evidence_dir=evidence_dir,
        device_reports=device_reports,
        lane_pitch_um=lane_pitch_um,
        mzi_pitch_um=mzi_pitch_um,
        fiber_pitch_um=fiber_pitch_um,
    ).manifest


def generate_gds_artifacts(
    blueprint: Blueprint,
    *,
    out_dir: str | Path = DEFAULT_GDS_OUT_DIR,
    gds_out: str | Path | None = None,
    pdk: str = "generic-si-photonics",
    evidence_dir: str | Path | None = DEFAULT_EVIDENCE_DIR,
    device_reports: list[str | Path] | None = None,
    lane_pitch_um: float = 18.0,
    mzi_pitch_um: float = 160.0,
    fiber_pitch_um: float = 127.0,
    include_preview: bool = True,
) -> dict[str, Any]:
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    gds_path = Path(gds_out) if gds_out else target_dir / "oqp-hrm-generic-siph.gds"

    design = build_gds_design(
        blueprint,
        pdk=pdk,
        evidence_dir=evidence_dir,
        device_reports=device_reports,
        lane_pitch_um=lane_pitch_um,
        mzi_pitch_um=mzi_pitch_um,
        fiber_pitch_um=fiber_pitch_um,
    )
    write_gds_library(design.cells, gds_path)
    gds_bytes = gds_path.read_bytes()

    manifest = design.manifest
    artifact_refs = {
        "gdsFile": str(gds_path),
        "planReport": str(target_dir / "gds-plan.json"),
        "manifest": str(target_dir / "gds-manifest.json"),
        "audit": str(target_dir / "gds-audit.json"),
        "cellRegistry": str(target_dir / "cell-registry.json"),
        "layerMap": str(target_dir / "layer-map.json"),
        "ports": str(target_dir / "ports.json"),
        "pads": str(target_dir / "pads.json"),
        "finalGapAudit": str(target_dir / "final-gap-audit.md"),
    }
    if include_preview:
        artifact_refs["previewSvg"] = str(target_dir / "gds-preview.svg")

    manifest["artifactRefs"] = artifact_refs
    manifest["gdsFile"] = {
        "path": str(gds_path),
        "sha256": sha256(gds_bytes).hexdigest(),
        "byteSize": len(gds_bytes),
    }
    manifest["readinessFlags"]["gds_generated"] = True
    manifest["layoutCompletion"] = _layout_completion_report(manifest)

    plan = generate_gds_plan(
        blueprint,
        pdk=pdk,
        evidence_dir=evidence_dir,
        device_reports=device_reports,
        lane_pitch_um=lane_pitch_um,
        mzi_pitch_um=mzi_pitch_um,
        fiber_pitch_um=fiber_pitch_um,
    )
    plan["artifactRefs"] = artifact_refs
    plan["gdsGenerated"] = True
    plan["readinessFlags"]["gds_generated"] = True

    audit = generate_gds_audit(manifest=manifest)
    _write_json(plan, artifact_refs["planReport"])
    _write_json(manifest, artifact_refs["manifest"])
    _write_json(audit, artifact_refs["audit"])
    _write_json(manifest["cellRegistry"], artifact_refs["cellRegistry"])
    _write_json(manifest["layerMap"], artifact_refs["layerMap"])
    _write_json(manifest["ports"], artifact_refs["ports"])
    _write_json(manifest["pads"], artifact_refs["pads"])
    Path(artifact_refs["finalGapAudit"]).write_text(_final_gap_audit_markdown(audit, manifest), encoding="utf-8")
    if include_preview:
        write_gds_preview(manifest, artifact_refs["previewSvg"])

    report = {
        "schemaVersion": f"{SCHEMA_PREFIX}.gds-generate.v1",
        "generatedAt": manifest["generatedAt"],
        "sourcePath": blueprint.source_path,
        "pdk": manifest["pdk"],
        "topCell": TOP_CELL_NAME,
        "gdsGenerated": True,
        "layoutComputable": True,
        "artifactRefs": artifact_refs,
        "gdsFile": manifest["gdsFile"],
        "manifestSummary": _manifest_summary(manifest),
        "auditSummary": _audit_summary(audit),
        "layoutCompletion": manifest["layoutCompletion"],
        "readinessFlags": manifest["readinessFlags"],
        "blockers": manifest["blockers"],
        "nextSteps": manifest["nextSteps"],
    }
    _write_json(report, target_dir / "gds-generate.json")
    return report


def generate_gds_audit(
    blueprint: Blueprint | None = None,
    *,
    manifest: dict[str, Any] | None = None,
    pdk: str = "generic-si-photonics",
    evidence_dir: str | Path | None = DEFAULT_EVIDENCE_DIR,
    device_reports: list[str | Path] | None = None,
) -> dict[str, Any]:
    if manifest is None:
        if blueprint is None:
            raise ValueError("blueprint or manifest is required")
        manifest = generate_gds_manifest(
            blueprint,
            pdk=pdk,
            evidence_dir=evidence_dir,
            device_reports=device_reports,
        )
    flags = dict(manifest["readinessFlags"])
    blockers = list(manifest.get("blockers", []))
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.gds-audit.v1",
        "generatedAt": _now_iso(),
        "sourcePath": manifest.get("sourcePath"),
        "pdk": manifest.get("pdk"),
        "topCell": manifest.get("topCell"),
        "auditFlags": {
            "gds_generated": bool(flags.get("gds_generated")),
            "layout_computable": bool(flags.get("layout_computable")),
            "fdtd_gap_backed_placeholder": bool(flags.get("fdtd_gap_backed_placeholder")),
            "drc_not_run": True,
            "lvs_not_run": True,
            "foundry_pdk_missing": bool(flags.get("foundry_pdk_missing")),
            "not_tapeout_ready": True,
        },
        "counts": {
            "cells": len(manifest.get("cellRegistry", [])),
            "instances": len(manifest.get("instances", [])),
            "ports": len(manifest.get("ports", [])),
            "pads": len(manifest.get("pads", [])),
            "deviceInstances": len([item for item in manifest.get("instances", []) if item.get("role") == "core_device"]),
        },
        "chipSizeUm": manifest.get("topLevelLayout", {}).get("chipSizeUm"),
        "layerUsage": manifest.get("layerUsage", {}),
        "deviceEvidence": manifest.get("deviceEvidence", {}),
        "blockers": blockers,
        "finalGapAudit": {
            "drc": "No foundry DRC deck has been run against this GDS.",
            "lvs": "No optical/electrical LVS deck or extracted netlist comparison has been run.",
            "foundryPdk": "The design uses a generic SiPh layer map, not a locked foundry PDK and process stack.",
            "devicePhysics": _device_physics_gap_text(flags, manifest.get("deviceEvidence", {})),
            "sParameters": "No foundry-calibrated S-parameter compact models are attached to MZI/coupler/phase-shifter/truth-switch cells.",
            "packaging": "Fiber pitch adaptation, edge/grating coupler selection, probe card, thermal stack, and package drawing remain placeholders.",
            "controls": "Phase-driver, truth-switch, source, and detector interfaces need real driver, TDC, and calibration closure.",
            "tapeout": "The milestone is a reproducible pre-tapeout GDS, not a foundry-clean or tapeout-ready database.",
        },
        "layoutCompletion": _layout_completion_report(manifest),
        "nextSteps": manifest.get("nextSteps", []),
    }


def build_gds_design(
    blueprint: Blueprint,
    *,
    pdk: str = "generic-si-photonics",
    evidence_dir: str | Path | None = DEFAULT_EVIDENCE_DIR,
    device_reports: list[str | Path] | None = None,
    lane_pitch_um: float = 18.0,
    mzi_pitch_um: float = 160.0,
    fiber_pitch_um: float = 127.0,
) -> GdsDesign:
    layer_map = _layer_map_report()
    evidence = collect_device_evidence(evidence_dir=evidence_dir, device_reports=device_reports)
    component_templates = _component_templates(evidence)
    spatial = blueprint.spatial_model
    pairs = mzi_pairs(spatial.waveguide_count, spatial.interferometer_count, spatial.pairing_stride)

    margin_x = 180.0
    margin_y = 220.0
    x_lane_in = margin_x + 120.0
    x_stage0 = x_lane_in + 160.0
    x_lane_out = x_stage0 + max(1, spatial.interferometer_count) * mzi_pitch_um + 160.0
    chip_width = x_lane_out + margin_x + 140.0
    lane_ys = [margin_y + (mode * lane_pitch_um) for mode in range(spatial.waveguide_count)]
    device_area_height = (spatial.waveguide_count - 1) * lane_pitch_um if spatial.waveguide_count else 0.0
    chip_height = max(margin_y * 2.0 + device_area_height + 260.0, 980.0)

    top_polygons: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = [
        {"text": "OQP-HRM generic-SiPh pre-tapeout GDS", "xUm": 80.0, "yUm": chip_height - 40.0, "layer": "LABEL"}
    ]
    instances: list[dict[str, Any]] = []
    ports: list[dict[str, Any]] = []
    pads: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []

    top_polygons.append(_rect_poly("KEEPOUT", 20.0, 20.0, chip_width - 20.0, chip_height - 20.0, net="chip_keepout"))

    for mode, y_um in enumerate(lane_ys):
        lane_route = _rect_poly("WG", x_lane_in, y_um - 0.225, x_lane_out, y_um + 0.225, net=f"optical_lane_{mode}")
        top_polygons.append(lane_route)
        routes.append(
            {
                "routeId": f"optical_lane_{mode}",
                "kind": "optical_waveguide",
                "mode": mode,
                "from": f"opt_in_{mode}",
                "to": f"opt_out_{mode}",
                "layer": "WG",
                "lengthUm": round(x_lane_out - x_lane_in, 3),
                "bboxUm": _bbox_from_points(lane_route["pointsUm"]),
            }
        )
        _add_instance(
            instances,
            ports,
            component_templates["optical_io"],
            f"opt_in_{mode}",
            "optical_io",
            "optical_io",
            90.0,
            y_um,
            "west_edge_io",
        )
        _add_instance(
            instances,
            ports,
            component_templates["source_interface"],
            f"source_if_{mode}",
            "source_interface",
            "source_interface",
            x_lane_in - 60.0,
            y_um,
            "source_interface",
        )
        _add_instance(
            instances,
            ports,
            component_templates["detector_interface"],
            f"detector_if_{mode}",
            "detector_interface",
            "detector_interface",
            x_lane_out + 60.0,
            y_um,
            "detector_interface",
        )
        _add_instance(
            instances,
            ports,
            component_templates["optical_io"],
            f"opt_out_{mode}",
            "optical_io",
            "optical_io",
            x_lane_out + 140.0,
            y_um,
            "east_edge_io",
        )
        ports.append(
            {
                "portId": f"fiber_input_{mode}",
                "instanceId": f"opt_in_{mode}",
                "name": "fiber",
                "kind": "optical",
                "direction": "west",
                "xUm": 70.0,
                "yUm": round(y_um, 3),
                "layer": "PORT",
                "role": "fiber_input",
            }
        )
        ports.append(
            {
                "portId": f"fiber_output_{mode}",
                "instanceId": f"opt_out_{mode}",
                "name": "fiber",
                "kind": "optical",
                "direction": "east",
                "xUm": round(x_lane_out + 160.0, 3),
                "yUm": round(y_um, 3),
                "layer": "PORT",
                "role": "fiber_output",
            }
        )

    for index, (mode_a, mode_b) in enumerate(pairs):
        x_um = x_stage0 + (index + 0.5) * mzi_pitch_um
        y_um = (lane_ys[mode_a] + lane_ys[mode_b]) / 2.0
        core_type = "truth_switch" if index % 2 == 0 else "mzi"
        core_template = component_templates[core_type]
        _add_instance(instances, ports, core_template, f"{core_type}_{index}", core_type, "core_device", x_um, y_um, "core_device")
        _add_instance(instances, ports, component_templates["directional_coupler"], f"dc_{index}_a", "directional_coupler", "core_device", x_um - 54.0, y_um, "coupler")
        _add_instance(instances, ports, component_templates["directional_coupler"], f"dc_{index}_b", "directional_coupler", "core_device", x_um + 54.0, y_um, "coupler")
        _add_instance(instances, ports, component_templates["phase_shifter"], f"phase_{index}", "phase_shifter", "core_device", x_um, y_um + 11.0, "phase_control")

        labels.append({"text": f"TS{index}" if core_type == "truth_switch" else f"MZI{index}", "xUm": x_um - 20.0, "yUm": y_um + 24.0, "layer": "LABEL"})
        for pad_role, pad_y, route_suffix in (
            ("phase_driver", chip_height - 92.0, "phase"),
            ("truth_switch_driver", chip_height - 178.0, "switch"),
        ):
            pad_id = f"pad_{route_suffix}_{index}"
            _add_instance(
                instances,
                ports,
                component_templates["electrical_pad"],
                pad_id,
                "electrical_pad",
                "electrical_pad",
                x_um,
                pad_y,
                pad_role,
            )
            pads.append(
                {
                    "padId": pad_id,
                    "role": pad_role,
                    "instanceId": pad_id,
                    "xUm": round(x_um, 3),
                    "yUm": round(pad_y, 3),
                    "widthUm": 72.0,
                    "heightUm": 72.0,
                    "layer": "PAD",
                    "connectsTo": f"{core_type}_{index}" if route_suffix == "switch" else f"phase_{index}",
                }
            )
            route = _rect_poly(
                "METAL",
                x_um - 2.0,
                min(pad_y - 36.0, y_um + 20.0),
                x_um + 2.0,
                max(pad_y - 36.0, y_um + 20.0),
                net=f"{pad_id}_to_{route_suffix}_{index}",
            )
            top_polygons.append(route)
            routes.append(
                {
                    "routeId": f"{pad_id}_to_{route_suffix}_{index}",
                    "kind": "electrical_metal",
                    "from": pad_id,
                    "to": f"{core_type}_{index}" if route_suffix == "switch" else f"phase_{index}",
                    "layer": "METAL",
                    "lengthUm": round(abs((pad_y - 36.0) - (y_um + 20.0)), 3),
                    "bboxUm": _bbox_from_points(route["pointsUm"]),
                }
            )

    package_markers = _fiber_io_markers(
        waveguide_count=spatial.waveguide_count,
        fiber_pitch_um=fiber_pitch_um,
        lane_pitch_um=lane_pitch_um,
        chip_width=chip_width,
        lane_ys=lane_ys,
    )
    top_polygons.extend(package_markers)

    cells = _gds_cells(component_templates, top_polygons, labels, instances)
    layer_usage = _layer_usage(component_templates, top_polygons, instances)
    bbox = [0.0, 0.0, round(chip_width, 3), round(chip_height, 3)]
    fdtd_gap = any(template.status == "fdtd_gap_backed_placeholder" for template in component_templates.values())
    layer_names = {spec.name for spec in GENERIC_SIPH_LAYER_MAP}
    manifest = {
        "schemaVersion": f"{SCHEMA_PREFIX}.gds-manifest.v1",
        "generatedAt": _now_iso(),
        "sourcePath": blueprint.source_path,
        "topologyClass": blueprint.topology_class,
        "pdk": _pdk_report(pdk),
        "units": {"layout": "um", "gdsUserUnitMeters": 1e-6, "gdsDatabaseUnitMeters": 1e-9},
        "topCell": TOP_CELL_NAME,
        "libraryName": LIBRARY_NAME,
        "topLevelLayout": {
            "chipSizeUm": {"width": round(chip_width, 3), "height": round(chip_height, 3)},
            "bboxUm": bbox,
            "modeCount": spatial.waveguide_count,
            "interferometerCount": spatial.interferometer_count,
            "pairingStride": spatial.pairing_stride,
            "connectedComponents": connected_component_count(spatial.waveguide_count, pairs),
            "lanePitchUm": lane_pitch_um,
            "mziPitchUm": mzi_pitch_um,
            "coreXRangeUm": [round(x_stage0, 3), round(x_lane_out - 160.0, 3)],
        },
        "layerMap": layer_map,
        "componentLibrary": _component_library_report(component_templates),
        "cellRegistry": _cell_registry(component_templates, TOP_CELL_NAME, bbox),
        "instances": instances,
        "ports": _dedupe_ports(ports),
        "pads": pads,
        "routes": routes,
        "fiberIoPlan": {
            "scheme": "dual_edge_placeholder_with_pitch_adapter",
            "opticalInputs": spatial.waveguide_count,
            "opticalOutputs": spatial.waveguide_count,
            "fiberPitchUm": fiber_pitch_um,
            "edgeCouplerPitchUm": lane_pitch_um,
            "pitchAdapterRequired": not math.isclose(fiber_pitch_um, lane_pitch_um),
            "westEdge": {"xUm": 70.0, "ports": [f"fiber_input_{mode}" for mode in range(spatial.waveguide_count)]},
            "eastEdge": {"xUm": round(x_lane_out + 160.0, 3), "ports": [f"fiber_output_{mode}" for mode in range(spatial.waveguide_count)]},
        },
        "routingStats": {
            "opticalRouteCount": len([route for route in routes if route["kind"] == "optical_waveguide"]),
            "electricalRouteCount": len([route for route in routes if route["kind"] == "electrical_metal"]),
            "totalOpticalLengthUm": round(sum(route["lengthUm"] for route in routes if route["kind"] == "optical_waveguide"), 3),
            "totalElectricalLengthUm": round(sum(route["lengthUm"] for route in routes if route["kind"] == "electrical_metal"), 3),
            "layers": sorted({route["layer"] for route in routes if route["layer"] in layer_names}),
        },
        "layerUsage": layer_usage,
        "deviceEvidence": evidence,
        "readinessFlags": {
            "gds_generated": False,
            "layout_computable": True,
            "fdtd_gap_backed_placeholder": fdtd_gap,
            "drc_not_run": True,
            "lvs_not_run": True,
            "foundry_pdk_missing": pdk == "generic-si-photonics",
            "not_tapeout_ready": True,
        },
        "blockers": _gds_blockers(
            foundry_pdk_missing=pdk == "generic-si-photonics",
            fdtd_gap_backed_placeholder=fdtd_gap,
        ),
        "nextSteps": [
            "Select and version-lock a real SiPh foundry PDK and replace the generic layer map.",
            "Promote MZI, coupler, phase-shifter, and truth-switch cells using accepted 3D/MPB/FDTD and S-parameter evidence.",
            "Run DRC and LVS with foundry decks and record waiver policy.",
            "Close fiber/edge-coupler pitch adapter, probe-card, detector/source, and thermal packaging drawings.",
            "Tie control electronics, phase calibration, detector timing, and source indistinguishability data to the layout manifest.",
        ],
    }
    manifest["layoutCompletion"] = _layout_completion_report(manifest)
    return GdsDesign(manifest=manifest, cells=cells)


def _gds_blockers(*, foundry_pdk_missing: bool, fdtd_gap_backed_placeholder: bool) -> list[str]:
    blockers = []
    if foundry_pdk_missing:
        blockers.append("foundry_pdk_missing: generic SiPh layers are not a foundry-locked layer map.")
    blockers.extend(
        [
            "drc_not_run: no foundry DRC deck has been executed.",
            "lvs_not_run: no optical/electrical LVS deck has been executed.",
        ]
    )
    if fdtd_gap_backed_placeholder:
        blockers.append(
            "fdtd_gap_backed_placeholder: core device cells are computable but not accepted by current FDTD evidence."
        )
    blockers.append("not_tapeout_ready: package, calibration, compact-model, and signoff flows remain open.")
    return blockers


def _layout_completion_report(manifest: dict[str, Any]) -> dict[str, Any]:
    flags = manifest.get("readinessFlags", {})
    generated = bool(flags.get("gds_generated"))
    computable = bool(flags.get("layout_computable"))
    tapeout_ready = not bool(flags.get("not_tapeout_ready", True))
    foundry_locked = not bool(flags.get("foundry_pdk_missing", True))
    signoff_clean = not bool(flags.get("drc_not_run", True)) and not bool(flags.get("lvs_not_run", True))
    no_device_placeholders = not bool(flags.get("fdtd_gap_backed_placeholder", True))
    quantum_layout_complete = generated and computable and tapeout_ready and foundry_locked and signoff_clean and no_device_placeholders
    return {
        "status": "gds_package_generated" if generated else "layout_model_computable",
        "layoutModelComputable": computable,
        "reproducibleGdsPackageComplete": generated and computable,
        "quantumComputerLayoutComplete": quantum_layout_complete,
        "tapeoutReady": tapeout_ready,
        "claimBoundary": (
            "A complete GDS package here means a reproducible generic-SiPh layout artifact was produced. "
            "It is not a finished quantum-computer layout unless foundry PDK, DRC/LVS, compact-model, "
            "package, control, and hardware-evidence gates are also closed."
        ),
        "missingForFinishedQuantumComputerLayout": _finished_layout_missing_requirements(flags),
    }


def _finished_layout_missing_requirements(flags: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not flags.get("gds_generated"):
        missing.append("generated GDS file")
    if not flags.get("layout_computable"):
        missing.append("computable top-level layout")
    if flags.get("foundry_pdk_missing"):
        missing.append("version-locked foundry PDK and layer map")
    if flags.get("drc_not_run"):
        missing.append("clean DRC report or documented waivers")
    if flags.get("lvs_not_run"):
        missing.append("clean optical/electrical LVS report or documented waivers")
    if flags.get("fdtd_gap_backed_placeholder"):
        missing.append("accepted core-device geometry evidence without placeholder cells")
    if flags.get("not_tapeout_ready", True):
        missing.append("closed package, calibration, compact-model, control, and signoff flow")
    return missing


def _device_physics_gap_text(flags: dict[str, Any], evidence: dict[str, Any]) -> str:
    required = ("coupler", "mzi", "phase-shifter", "truth-switch")
    by_device = evidence.get("byDevice", {}) if isinstance(evidence, dict) else {}
    accepted = [
        device
        for device in required
        if isinstance(by_device.get(device), dict) and by_device[device].get("accepted")
    ]
    missing = [device for device in required if device not in by_device]
    if flags.get("fdtd_gap_backed_placeholder"):
        return (
            "One or more core device cells are computable placeholders because current FDTD/eigenmode evidence "
            "is missing or not accepted for that device family."
        )
    if len(accepted) == len(required):
        return (
            "Core device cells have accepted first-pass local simulation/eigenmode candidates attached. "
            "That is still not foundry- or wafer-calibrated device physics and does not promote the GDS to tapeout."
        )
    if missing:
        return (
            "Core device evidence is incomplete for "
            + ", ".join(missing)
            + "; those cells remain generic until accepted device evidence is attached."
        )
    return (
        "Core device cells have local simulation evidence attached, but the evidence is not sufficient for "
        "foundry, wafer, or tapeout readiness."
    )


def collect_device_evidence(
    *,
    evidence_dir: str | Path | None = DEFAULT_EVIDENCE_DIR,
    device_reports: list[str | Path] | None = None,
) -> dict[str, Any]:
    paths: list[Path] = []
    if evidence_dir:
        base = Path(evidence_dir)
        paths.extend(
            base / name
            for name in (
                "coupler-eigenmode-fdtd.json",
                "mzi-eigenmode-fdtd.json",
                "phase-shifter-eigenmode-fdtd.json",
                "truth-switch-eigenmode-fdtd.json",
                "device-sweep-champion.json",
                "device-sweep.json",
                "fusion-device-evidence.json",
            )
        )
        paths.extend(sorted(base.glob("*.json")))
    if device_reports:
        paths.extend(Path(path) for path in device_reports)

    by_device: dict[str, dict[str, Any]] = {}
    reports: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    for path in paths:
        if path in seen_paths:
            continue
        seen_paths.add(path)
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for report in _expand_evidence_report(raw):
            device = str(report.get("device", "")).strip()
            if not device:
                continue
            normalized = _normalize_device(device)
            evidence_item = {
                "evidenceId": f"{normalized}:{path.name}",
                "device": normalized,
                "sourcePath": str(path),
                "schemaVersion": report.get("schemaVersion"),
                "physicalValidationLevel": report.get("physicalValidationLevel"),
                "validationTier": report.get("validationTier"),
                "simulationModelVersion": report.get("simulationModelVersion"),
                "sourceModel": report.get("sourceModel"),
                "acceptanceStatus": report.get("acceptanceStatus", _acceptance_status(report)),
                "accepted": _accepted_device(report),
                "fdtdMetrics": report.get("fdtdMetrics", {}),
                "gapToAcceptance": report.get("gapToAcceptance"),
            }
            reports.append(evidence_item)
            current = by_device.get(normalized)
            if current is None or _evidence_rank(evidence_item) > _evidence_rank(current):
                by_device[normalized] = evidence_item
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.gds-device-evidence.v1",
        "evidenceDir": str(evidence_dir) if evidence_dir else None,
        "reportCount": len(reports),
        "byDevice": by_device,
        "reports": reports,
        "missingDevices": [
            device
            for device in ("coupler", "mzi", "phase-shifter", "truth-switch")
            if device not in by_device
        ],
    }


def write_gds_library(cells: list[dict[str, Any]], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    now = _gds_date()
    chunks: list[bytes] = [
        _record(0x00, 0x02, _int2([600])),
        _record(0x01, 0x02, _int2(now + now)),
        _record(0x02, 0x06, _ascii(LIBRARY_NAME)),
        _record(0x03, 0x05, _real8(0.001) + _real8(1e-9)),
    ]
    for cell in cells:
        chunks.extend(_write_cell(cell, now))
    chunks.append(_record(0x04, 0x00))
    target.write_bytes(b"".join(chunks))


def write_gds_preview(manifest: dict[str, Any], path: str | Path) -> dict[str, Any]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    width = float(manifest["topLevelLayout"]["chipSizeUm"]["width"])
    height = float(manifest["topLevelLayout"]["chipSizeUm"]["height"])
    scale = 0.18
    svg_width = max(640.0, width * scale)
    svg_height = max(360.0, height * scale)
    layer_colors = {
        "WG": "#0f766e",
        "DEVICE": "#7c3aed",
        "HEATER": "#c2410c",
        "METAL": "#334155",
        "PAD": "#f59e0b",
        "PORT": "#2563eb",
        "KEEPOUT": "#94a3b8",
        "PACKAGE": "#64748b",
    }
    elements = [
        f'<rect x="0" y="0" width="{svg_width:.1f}" height="{svg_height:.1f}" fill="#f8fafc"/>',
        f'<rect x="{20*scale:.1f}" y="{20*scale:.1f}" width="{(width-40)*scale:.1f}" height="{(height-40)*scale:.1f}" fill="none" stroke="#64748b" stroke-width="1"/>',
    ]
    for instance in manifest.get("instances", []):
        bbox = instance["bboxUm"]
        layer = "PAD" if instance["componentType"] == "electrical_pad" else "DEVICE"
        fill = layer_colors.get(layer, "#475569")
        x = bbox[0] * scale
        y = (height - bbox[3]) * scale
        w = (bbox[2] - bbox[0]) * scale
        h = (bbox[3] - bbox[1]) * scale
        opacity = "0.85" if instance.get("role") == "core_device" else "0.45"
        elements.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(w, 0.7):.2f}" height="{max(h, 0.7):.2f}" fill="{fill}" opacity="{opacity}"/>')
    for route in manifest.get("routes", []):
        bbox = route["bboxUm"]
        fill = layer_colors.get(route["layer"], "#111827")
        x = bbox[0] * scale
        y = (height - bbox[3]) * scale
        w = (bbox[2] - bbox[0]) * scale
        h = (bbox[3] - bbox[1]) * scale
        elements.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(w, 0.5):.2f}" height="{max(h, 0.5):.2f}" fill="{fill}" opacity="0.65"/>')
    elements.append(f'<text x="18" y="28" font-family="monospace" font-size="16" fill="#0f172a">{manifest["topCell"]}</text>')
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width:.1f}" height="{svg_height:.1f}" viewBox="0 0 {svg_width:.1f} {svg_height:.1f}">\n' + "\n".join(elements) + "\n</svg>\n"
    target.write_text(svg, encoding="utf-8")
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.gds-preview.v1",
        "generatedAt": _now_iso(),
        "previewSvg": str(target),
        "topCell": manifest["topCell"],
        "chipSizeUm": manifest["topLevelLayout"]["chipSizeUm"],
    }


def _component_templates(evidence: dict[str, Any]) -> dict[str, CellTemplate]:
    by_device = evidence["byDevice"]

    def status_for(device: str | None, fallback: str) -> tuple[str, tuple[str, ...]]:
        if not device:
            return fallback, ()
        item = by_device.get(device)
        if not item:
            return "layout_placeholder_no_fdtd", ()
        return ("fdtd_accepted_candidate" if item["accepted"] else "fdtd_gap_backed_placeholder"), (item["evidenceId"],)

    waveguide_status, waveguide_refs = status_for(None, "generic_siph_layout_computable")
    coupler_status, coupler_refs = status_for("coupler", "layout_placeholder_no_fdtd")
    mzi_status, mzi_refs = status_for("mzi", "layout_placeholder_no_fdtd")
    phase_status, phase_refs = status_for("phase-shifter", "layout_placeholder_no_fdtd")
    truth_status, truth_refs = status_for("truth-switch", "layout_placeholder_no_fdtd")
    interface_limitations = (
        "Generic interface placeholder; no source/detector foundry stack or package model is locked.",
    )
    return {
        "waveguide": _template(
            "OQP_WAVEGUIDE",
            "waveguide",
            waveguide_status,
            100.0,
            6.0,
            (
                CellPort("in", "optical", -50.0, 0.0, "west", "PORT"),
                CellPort("out", "optical", 50.0, 0.0, "east", "PORT"),
            ),
            (
                _rect_poly("WG", -50.0, -0.225, 50.0, 0.225),
                _rect_poly("PORT", -50.8, -1.2, -49.2, 1.2),
                _rect_poly("PORT", 49.2, -1.2, 50.8, 1.2),
            ),
            waveguide_refs,
            ("Generic straight waveguide; no bend, sidewall, CMP, or corner models attached.",),
        ),
        "directional_coupler": _template(
            "OQP_DIRECTIONAL_COUPLER",
            "directional_coupler",
            coupler_status,
            42.0,
            9.0,
            (
                CellPort("in_a", "optical", -21.0, -2.2, "west", "PORT"),
                CellPort("in_b", "optical", -21.0, 2.2, "west", "PORT"),
                CellPort("out_a", "optical", 21.0, -2.2, "east", "PORT"),
                CellPort("out_b", "optical", 21.0, 2.2, "east", "PORT"),
            ),
            (
                _rect_poly("WG", -21.0, -2.425, 21.0, -1.975),
                _rect_poly("WG", -21.0, 1.975, 21.0, 2.425),
                _rect_poly("DEVICE", -17.0, -4.2, 17.0, 4.2),
            ),
            coupler_refs,
            ("Directional coupler geometry is a placeholder until accepted S-parameter evidence exists.",),
        ),
        "phase_shifter": _template(
            "OQP_PHASE_SHIFTER",
            "phase_shifter",
            phase_status,
            64.0,
            14.0,
            (
                CellPort("opt_in", "optical", -32.0, 0.0, "west", "PORT"),
                CellPort("opt_out", "optical", 32.0, 0.0, "east", "PORT"),
                CellPort("drive", "electrical", 0.0, 7.0, "north", "PORT"),
            ),
            (
                _rect_poly("WG", -32.0, -0.225, 32.0, 0.225),
                _rect_poly("HEATER", -25.0, 2.5, 25.0, 5.0),
                _rect_poly("METAL", -2.0, 5.0, 2.0, 7.0),
                _rect_poly("DEVICE", -30.0, -6.0, 30.0, 6.0),
            ),
            phase_refs,
            ("Heater/electro-optic stack is generic; no thermal crosstalk or driver model is locked.",),
        ),
        "mzi": _template(
            "OQP_MZI",
            "mzi",
            mzi_status,
            112.0,
            26.0,
            (
                CellPort("in_a", "optical", -56.0, -5.0, "west", "PORT"),
                CellPort("in_b", "optical", -56.0, 5.0, "west", "PORT"),
                CellPort("out_a", "optical", 56.0, -5.0, "east", "PORT"),
                CellPort("out_b", "optical", 56.0, 5.0, "east", "PORT"),
                CellPort("phase", "electrical", 0.0, 13.0, "north", "PORT"),
            ),
            (
                _rect_poly("WG", -56.0, -5.225, 56.0, -4.775),
                _rect_poly("WG", -56.0, 4.775, 56.0, 5.225),
                _rect_poly("DEVICE", -52.0, -11.0, 52.0, 11.0),
                _rect_poly("HEATER", -18.0, 8.0, 18.0, 11.0),
                _rect_poly("METAL", -2.0, 11.0, 2.0, 13.0),
            ),
            mzi_refs,
            ("MZI is GDS-computable but not FDTD-accepted for tapeout promotion.",),
        ),
        "truth_switch": _template(
            "OQP_TRUTH_SWITCH",
            "truth_switch",
            truth_status,
            124.0,
            34.0,
            (
                CellPort("in_a", "optical", -62.0, -5.0, "west", "PORT"),
                CellPort("in_b", "optical", -62.0, 5.0, "west", "PORT"),
                CellPort("out_a", "optical", 62.0, -5.0, "east", "PORT"),
                CellPort("out_b", "optical", 62.0, 5.0, "east", "PORT"),
                CellPort("switch_drive", "electrical", 0.0, 17.0, "north", "PORT"),
            ),
            (
                _rect_poly("WG", -62.0, -5.225, 62.0, -4.775),
                _rect_poly("WG", -62.0, 4.775, 62.0, 5.225),
                _rect_poly("DEVICE", -58.0, -14.0, 58.0, 14.0),
                _rect_poly("HEATER", -25.0, 10.0, 25.0, 13.5),
                _rect_poly("METAL", -3.0, 13.5, 3.0, 17.0),
                _rect_poly("PORT", -5.0, -17.0, 5.0, -14.0),
            ),
            truth_refs,
            ("Truth-switch actuation is represented by generic geometry pending material and driver closure.",),
        ),
        "optical_io": _template(
            "OQP_OPTICAL_IO",
            "optical_io",
            "generic_siph_placeholder",
            30.0,
            18.0,
            (
                CellPort("fiber", "optical", -15.0, 0.0, "west", "PORT"),
                CellPort("chip", "optical", 15.0, 0.0, "east", "PORT"),
            ),
            (
                _rect_poly("PACKAGE", -15.0, -8.0, 6.0, 8.0),
                _rect_poly("WG", 0.0, -0.225, 15.0, 0.225),
                _rect_poly("PORT", -16.0, -2.0, -14.0, 2.0),
            ),
            (),
            ("Grating/edge coupler is a placeholder; pitch adapter and foundry cell selection remain open.",),
        ),
        "detector_interface": _template(
            "OQP_DETECTOR_INTERFACE",
            "detector_interface",
            "generic_siph_placeholder",
            44.0,
            18.0,
            (
                CellPort("opt_in", "optical", -22.0, 0.0, "west", "PORT"),
                CellPort("readout", "electrical", 18.0, 7.0, "north", "PORT"),
            ),
            (
                _rect_poly("WG", -22.0, -0.225, 12.0, 0.225),
                _rect_poly("DEVICE", 6.0, -6.0, 22.0, 6.0),
                _rect_poly("METAL", 16.0, 6.0, 20.0, 9.0),
            ),
            (),
            interface_limitations,
        ),
        "source_interface": _template(
            "OQP_SOURCE_INTERFACE",
            "source_interface",
            "generic_siph_placeholder",
            44.0,
            18.0,
            (
                CellPort("source_bias", "electrical", -18.0, 7.0, "north", "PORT"),
                CellPort("opt_out", "optical", 22.0, 0.0, "east", "PORT"),
            ),
            (
                _rect_poly("DEVICE", -22.0, -6.0, -6.0, 6.0),
                _rect_poly("WG", -12.0, -0.225, 22.0, 0.225),
                _rect_poly("METAL", -20.0, 6.0, -16.0, 9.0),
            ),
            (),
            interface_limitations,
        ),
        "electrical_pad": _template(
            "OQP_ELECTRICAL_PAD",
            "electrical_pad",
            "generic_siph_layout_computable",
            72.0,
            72.0,
            (CellPort("pad", "electrical", 0.0, 0.0, "pad", "PORT"),),
            (
                _rect_poly("PAD", -36.0, -36.0, 36.0, 36.0),
                _rect_poly("METAL", -30.0, -30.0, 30.0, 30.0),
                _rect_poly("PORT", -4.0, -4.0, 4.0, 4.0),
            ),
            (),
            ("Pad dimensions are generic and need probe-card/package rule closure.",),
        ),
    }


def _template(
    name: str,
    component_type: str,
    status: str,
    width_um: float,
    height_um: float,
    ports: tuple[CellPort, ...],
    polygons: tuple[dict[str, Any], ...],
    evidence_refs: tuple[str, ...],
    limitations: tuple[str, ...],
) -> CellTemplate:
    return CellTemplate(
        name=name,
        component_type=component_type,
        status=status,
        width_um=width_um,
        height_um=height_um,
        bbox_um=(-width_um / 2.0, -height_um / 2.0, width_um / 2.0, height_um / 2.0),
        ports=ports,
        polygons=polygons,
        evidence_refs=evidence_refs,
        limitations=limitations,
    )


def _add_instance(
    instances: list[dict[str, Any]],
    ports: list[dict[str, Any]],
    template: CellTemplate,
    instance_id: str,
    component_type: str,
    role: str,
    x_um: float,
    y_um: float,
    placement_group: str,
) -> None:
    bbox = [
        round(template.bbox_um[0] + x_um, 3),
        round(template.bbox_um[1] + y_um, 3),
        round(template.bbox_um[2] + x_um, 3),
        round(template.bbox_um[3] + y_um, 3),
    ]
    instances.append(
        {
            "instanceId": instance_id,
            "cell": template.name,
            "componentType": component_type,
            "role": role,
            "status": template.status,
            "originUm": {"x": round(x_um, 3), "y": round(y_um, 3)},
            "bboxUm": bbox,
            "placementGroup": placement_group,
            "evidenceRefs": list(template.evidence_refs),
        }
    )
    for port in template.ports:
        ports.append(
            {
                "portId": f"{instance_id}.{port.name}",
                "instanceId": instance_id,
                "name": port.name,
                "kind": port.kind,
                "direction": port.direction,
                "xUm": round(x_um + port.x_um, 3),
                "yUm": round(y_um + port.y_um, 3),
                "layer": port.layer,
                "role": role,
            }
        )


def _component_library_report(templates: dict[str, CellTemplate]) -> dict[str, Any]:
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.gds-component-library.v1",
        "libraryName": "oqp_hrm_generic_siph_cells",
        "cells": {
            key: {
                "cellName": template.name,
                "componentType": template.component_type,
                "status": template.status,
                "bboxUm": list(template.bbox_um),
                "ports": [
                    {
                        "name": port.name,
                        "kind": port.kind,
                        "xUm": port.x_um,
                        "yUm": port.y_um,
                        "direction": port.direction,
                        "layer": port.layer,
                    }
                    for port in template.ports
                ],
                "evidenceRefs": list(template.evidence_refs),
                "limitations": list(template.limitations),
            }
            for key, template in templates.items()
        },
    }


def _cell_registry(templates: dict[str, CellTemplate], top_name: str, top_bbox: list[float]) -> list[dict[str, Any]]:
    registry = [
        {
            "cellName": top_name,
            "componentType": "top_level_chip",
            "bboxUm": top_bbox,
            "status": "layout_computable",
            "referenceCount": 0,
        }
    ]
    registry.extend(
        {
            "cellName": template.name,
            "componentType": template.component_type,
            "bboxUm": list(template.bbox_um),
            "status": template.status,
            "referenceCount": None,
            "evidenceRefs": list(template.evidence_refs),
        }
        for template in sorted(templates.values(), key=lambda item: item.name)
    )
    return registry


def _gds_cells(
    templates: dict[str, CellTemplate],
    top_polygons: list[dict[str, Any]],
    labels: list[dict[str, Any]],
    instances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cells = [
        {
            "name": template.name,
            "polygons": [dict(poly) for poly in template.polygons],
            "refs": [],
            "labels": [{"text": template.component_type, "xUm": template.bbox_um[0], "yUm": template.bbox_um[3] + 4.0, "layer": "LABEL"}],
        }
        for template in sorted(templates.values(), key=lambda item: item.name)
    ]
    top_refs = [
        {
            "cell": instance["cell"],
            "xUm": instance["originUm"]["x"],
            "yUm": instance["originUm"]["y"],
        }
        for instance in instances
    ]
    cells.append({"name": TOP_CELL_NAME, "polygons": top_polygons, "refs": top_refs, "labels": labels})
    return cells


def _layer_usage(
    templates: dict[str, CellTemplate],
    top_polygons: list[dict[str, Any]],
    instances: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    usage = {spec.name: {"layer": spec.layer, "datatype": spec.datatype, "polygonCount": 0, "areaUm2": 0.0} for spec in GENERIC_SIPH_LAYER_MAP}
    templates_by_name = {template.name: template for template in templates.values()}
    for poly in top_polygons:
        _add_layer_usage(usage, poly)
    for instance in instances:
        template = templates_by_name[instance["cell"]]
        for poly in template.polygons:
            _add_layer_usage(usage, poly)
    return {key: {**value, "areaUm2": round(value["areaUm2"], 3)} for key, value in usage.items() if value["polygonCount"] > 0}


def _add_layer_usage(usage: dict[str, dict[str, Any]], poly: dict[str, Any]) -> None:
    layer = poly["layer"]
    if layer not in usage:
        return
    usage[layer]["polygonCount"] += 1
    usage[layer]["areaUm2"] += _polygon_area(poly["pointsUm"])


def _rect_poly(layer: str, x0: float, y0: float, x1: float, y1: float, *, net: str | None = None) -> dict[str, Any]:
    left, right = sorted((float(x0), float(x1)))
    bottom, top = sorted((float(y0), float(y1)))
    poly = {
        "layer": layer,
        "pointsUm": [
            [round(left, 6), round(bottom, 6)],
            [round(right, 6), round(bottom, 6)],
            [round(right, 6), round(top, 6)],
            [round(left, 6), round(top, 6)],
            [round(left, 6), round(bottom, 6)],
        ],
    }
    if net:
        poly["net"] = net
    return poly


def _fiber_io_markers(
    *,
    waveguide_count: int,
    fiber_pitch_um: float,
    lane_pitch_um: float,
    chip_width: float,
    lane_ys: list[float],
) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    if not lane_ys:
        return markers
    active_height = (waveguide_count - 1) * lane_pitch_um
    fiber_height = (waveguide_count - 1) * fiber_pitch_um
    markers.append(_rect_poly("PACKAGE", 36.0, lane_ys[0] - 12.0, 54.0, lane_ys[-1] + 12.0, net="west_edge_coupler_line"))
    markers.append(_rect_poly("PACKAGE", chip_width - 54.0, lane_ys[0] - 12.0, chip_width - 36.0, lane_ys[-1] + 12.0, net="east_edge_coupler_line"))
    if not math.isclose(active_height, fiber_height):
        markers.append(_rect_poly("KEEPOUT", 56.0, lane_ys[0] - 24.0, 120.0, lane_ys[-1] + 24.0, net="west_pitch_adapter_keepout"))
        markers.append(_rect_poly("KEEPOUT", chip_width - 120.0, lane_ys[0] - 24.0, chip_width - 56.0, lane_ys[-1] + 24.0, net="east_pitch_adapter_keepout"))
    return markers


def _write_cell(cell: dict[str, Any], now: list[int]) -> list[bytes]:
    chunks = [
        _record(0x05, 0x02, _int2(now + now)),
        _record(0x06, 0x06, _ascii(cell["name"])),
    ]
    for poly in cell.get("polygons", []):
        layer = _layer(poly["layer"])
        chunks.extend(
            [
                _record(0x08, 0x00),
                _record(0x0D, 0x02, _int2([layer.layer])),
                _record(0x0E, 0x02, _int2([layer.datatype])),
                _record(0x10, 0x03, _xy(poly["pointsUm"])),
                _record(0x11, 0x00),
            ]
        )
    for ref in cell.get("refs", []):
        chunks.extend(
            [
                _record(0x0A, 0x00),
                _record(0x12, 0x06, _ascii(ref["cell"])),
                _record(0x10, 0x03, _xy([[ref["xUm"], ref["yUm"]]])),
                _record(0x11, 0x00),
            ]
        )
    for label in cell.get("labels", []):
        layer = _layer(label.get("layer", "LABEL"))
        chunks.extend(
            [
                _record(0x0C, 0x00),
                _record(0x0D, 0x02, _int2([layer.layer])),
                _record(0x16, 0x02, _int2([layer.datatype])),
                _record(0x10, 0x03, _xy([[label["xUm"], label["yUm"]]])),
                _record(0x19, 0x06, _ascii(label["text"][:128])),
                _record(0x11, 0x00),
            ]
        )
    chunks.append(_record(0x07, 0x00))
    return chunks


def _record(record_type: int, data_type: int, payload: bytes = b"") -> bytes:
    size = len(payload) + 4
    if size % 2:
        payload += b"\0"
        size += 1
    return struct.pack(">HBB", size, record_type, data_type) + payload


def _int2(values: Iterable[int]) -> bytes:
    return b"".join(struct.pack(">h", int(value)) for value in values)


def _int4(values: Iterable[int]) -> bytes:
    return b"".join(struct.pack(">i", int(value)) for value in values)


def _xy(points_um: list[list[float]]) -> bytes:
    values: list[int] = []
    for x_um, y_um in points_um:
        values.extend([round(x_um * 1000.0), round(y_um * 1000.0)])
    return _int4(values)


def _ascii(value: str) -> bytes:
    return value.encode("ascii", "replace")


def _real8(value: float) -> bytes:
    if value == 0:
        return b"\0" * 8
    sign = 0x80 if value < 0 else 0
    number = abs(float(value))
    exponent = 64
    while number < 0.0625:
        number *= 16.0
        exponent -= 1
    while number >= 1.0:
        number /= 16.0
        exponent += 1
    mantissa = int(number * (1 << 56) + 0.5)
    if mantissa >= (1 << 56):
        mantissa >>= 4
        exponent += 1
    return bytes([sign | exponent]) + mantissa.to_bytes(7, "big")


def _gds_date() -> list[int]:
    now = datetime.now(timezone.utc)
    return [now.year, now.month, now.day, now.hour, now.minute, now.second]


def _layer(name: str) -> LayerSpec:
    for spec in GENERIC_SIPH_LAYER_MAP:
        if spec.name == name:
            return spec
    raise KeyError(f"unknown GDS layer: {name}")


def _layer_map_report() -> dict[str, Any]:
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.generic-siph-layer-map.v1",
        "name": "generic-si-photonics",
        "layers": [
            {
                "name": spec.name,
                "layer": spec.layer,
                "datatype": spec.datatype,
                "purpose": spec.purpose,
                "description": spec.description,
            }
            for spec in GENERIC_SIPH_LAYER_MAP
        ],
    }


def _pdk_report(pdk: str) -> dict[str, Any]:
    return {
        "name": pdk,
        "compatibility": "generic_siph" if pdk == "generic-si-photonics" else "pdk_named_not_verified",
        "foundryPdkLocked": False,
        "layerMap": "generic-si-photonics",
        "minWaveguideWidthUm": 0.45,
        "minBendRadiusUm": 10.0,
        "minGapUm": 0.18,
        "requiresDrcDeck": True,
        "requiresLvsDeck": True,
    }


def _expand_evidence_report(raw: dict[str, Any]) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    if isinstance(raw.get("champion"), dict):
        reports.append(raw["champion"])
    if isinstance(raw.get("alternatives"), list):
        reports.extend(item for item in raw["alternatives"] if isinstance(item, dict))
    if raw.get("device"):
        reports.append(raw)
    return reports


def _normalize_device(device: str) -> str:
    lowered = device.strip().lower().replace("_", "-")
    if lowered in {"directional-coupler", "dc"}:
        return "coupler"
    if lowered in {"phase", "phase-shifter"}:
        return "phase-shifter"
    if lowered in {"truth-switch", "truthswitch"}:
        return "truth-switch"
    return lowered


def _accepted_device(report: dict[str, Any]) -> bool:
    metrics = report.get("fdtdMetrics", {})
    useful = float(metrics.get("usefulTransmission", metrics.get("throughRatio", 0.0) + metrics.get("crossRatio", 0.0)))
    insertion = float(metrics.get("insertionLossDb", math.inf))
    reflection = float(metrics.get("reflectionRatio", math.inf))
    crosstalk = float(metrics.get("crosstalkRatio", metrics.get("imbalanceRatio", math.inf)))
    normalization_reliable = metrics.get("normalizationReliable")
    return (
        useful >= 0.5
        and insertion <= 1.0
        and reflection <= 0.05
        and crosstalk <= 0.05
        and normalization_reliable is not False
    )


def _acceptance_status(report: dict[str, Any]) -> str:
    return "accepted_first_pass" if _accepted_device(report) else "not_accepted_first_pass"


def _evidence_rank(item: dict[str, Any]) -> tuple[int, int, int, int, float, float, float, float, float]:
    metrics = item.get("fdtdMetrics", {})
    tier = str(item.get("physicalValidationLevel") or "")
    validation_tier = str(item.get("validationTier") or "")
    norm_flag = metrics.get("normalizationReliable")
    norm_rank = 2 if norm_flag is True else 1 if norm_flag is None else 0
    output_flux = float(metrics.get("outputPortNormalizationFlux") or 0.0)
    useful = float(metrics.get("usefulTransmission", metrics.get("throughRatio", 0.0) + metrics.get("crossRatio", 0.0)))
    crosstalk = float(metrics.get("crosstalkRatio", metrics.get("imbalanceRatio", math.inf)))
    reflection = float(metrics.get("reflectionRatio", math.inf))
    insertion = float(metrics.get("insertionLossDb", math.inf))
    gap_score = (
        max(0.0, 0.5 - useful)
        + max(0.0, insertion - 1.0)
        + max(0.0, reflection - 0.05)
        + max(0.0, crosstalk - 0.05)
    )
    return (
        1 if item.get("accepted") else 0,
        norm_rank,
        3 if "high_resolution" in validation_tier else 2 if "medium_resolution" in validation_tier else 1 if validation_tier else 0,
        2 if "eigenmode" in tier else 1 if tier else 0,
        -gap_score,
        min(output_flux / 1e-8, 10.0),
        min(max(useful, 0.0), 1.0),
        -crosstalk,
        -reflection,
        -insertion,
    )


def _bbox_from_points(points: list[list[float]]) -> list[float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return [round(min(xs), 3), round(min(ys), 3), round(max(xs), 3), round(max(ys), 3)]


def _polygon_area(points: list[list[float]]) -> float:
    if len(points) < 4:
        return 0.0
    area = 0.0
    for left, right in zip(points, points[1:]):
        area += left[0] * right[1] - right[0] * left[1]
    return abs(area) / 2.0


def _dedupe_ports(ports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for port in ports:
        port_id = port["portId"]
        if port_id in seen:
            continue
        seen.add(port_id)
        result.append(port)
    return result


def _manifest_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "topCell": manifest["topCell"],
        "gdsFile": manifest.get("gdsFile"),
        "chipSizeUm": manifest["topLevelLayout"]["chipSizeUm"],
        "cellCount": len(manifest["cellRegistry"]),
        "instanceCount": len(manifest["instances"]),
        "portCount": len(manifest["ports"]),
        "padCount": len(manifest["pads"]),
        "routingStats": manifest["routingStats"],
        "layerUsage": manifest["layerUsage"],
        "layoutCompletion": manifest.get("layoutCompletion", _layout_completion_report(manifest)),
    }


def _audit_summary(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "auditFlags": audit["auditFlags"],
        "counts": audit["counts"],
        "chipSizeUm": audit["chipSizeUm"],
        "blockers": audit["blockers"],
        "layoutCompletion": audit.get("layoutCompletion"),
    }


def _final_gap_audit_markdown(audit: dict[str, Any], manifest: dict[str, Any]) -> str:
    flags = audit["auditFlags"]
    counts = audit["counts"]
    chip = audit["chipSizeUm"]
    gaps = audit["finalGapAudit"]
    lines = [
        "# OQP-HRM GDS Final Gap Audit",
        "",
        f"Generated: {audit['generatedAt']}",
        f"Top cell: {audit['topCell']}",
        f"Chip size: {chip['width']} x {chip['height']} um",
        f"Cells: {counts['cells']}",
        f"Instances: {counts['instances']}",
        f"Ports: {counts['ports']}",
        f"Pads: {counts['pads']}",
        "",
        "## Readiness Flags",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in flags.items())
    completion = audit.get("layoutCompletion")
    if isinstance(completion, dict):
        lines.extend(["", "## Layout Completion", ""])
        for key in (
            "status",
            "layoutModelComputable",
            "reproducibleGdsPackageComplete",
            "quantumComputerLayoutComplete",
            "tapeoutReady",
        ):
            lines.append(f"- {key}: {completion.get(key)}")
        missing = completion.get("missingForFinishedQuantumComputerLayout") or []
        if missing:
            lines.append("- missingForFinishedQuantumComputerLayout:")
            lines.extend(f"  - {item}" for item in missing)
        lines.append(f"- claimBoundary: {completion.get('claimBoundary')}")
    lines.extend(["", "## Remaining Tapeout Gaps", ""])
    lines.extend(f"- {key}: {value}" for key, value in gaps.items())
    lines.extend(["", "## Generated Artifacts", ""])
    refs = manifest.get("artifactRefs", {})
    if isinstance(refs, dict):
        lines.extend(f"- {key}: {value}" for key, value in sorted(refs.items()))
    lines.append("")
    return "\n".join(lines)


def _write_json(report: dict[str, Any] | list[dict[str, Any]], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
