"""Tapeout-level readiness reporting for OQP-HRM."""

from __future__ import annotations

from typing import Any

from .blueprint import Blueprint
from .layout_readiness import generate_layout_readiness
from .readiness import generate_control_readiness, generate_lab_readiness


def generate_tapeout_readiness(
    blueprint: Blueprint,
    *,
    pdk: str = "generic-si-photonics",
    feed_forward_latency_ns: float = 5.0,
    detector_type: str = "SNSPD",
) -> dict[str, Any]:
    layout = generate_layout_readiness(blueprint, pdk=pdk)
    control = generate_control_readiness(blueprint, feed_forward_latency_ns=feed_forward_latency_ns)
    lab = generate_lab_readiness(blueprint, detector_type=detector_type)
    blockers = []
    blockers.extend(layout["blockers"])
    blockers.extend(control["blockers"])
    blockers.extend(lab["blockers"])
    blockers.extend(
        [
            "No foundry-specific PDK install and version lock.",
            "No generated GDS cell library for MZI/coupler/phase-shifter/truth-switch.",
            "No DRC/LVS clean report.",
            "No packaging/fiber-I/O drawing tied to pad and optical-port coordinates.",
            "No hardware-in-the-loop shot scheduler verified against real detector timestamps.",
        ]
    )
    component_library = {
        "waveguide": "abstract_cell",
        "directionalCoupler": "abstract_cell_needs_s_parameter_fit",
        "mzi": "fdtd_cell_not_gds_promoted",
        "phaseShifter": "requirements_only",
        "truthSwitch": "fdtd_cell_not_gds_promoted",
        "singlePhotonSource": "external_or_missing",
        "pnrDetector": "external_or_missing",
        "fiberCoupler": "missing",
        "metalRouting": "missing",
    }
    return {
        "schemaVersion": "open-quantum.tapeout-readiness.v1",
        "sourcePath": blueprint.source_path,
        "pdk": layout["pdk"],
        "layoutReady": layout["gdsReady"],
        "gdsReady": False,
        "tapeoutReady": False,
        "controlReady": control["controlReady"],
        "labReady": lab["labReady"],
        "readinessFlags": {
            "simulated": True,
            "fdtdValidated": False,
            "layoutReady": layout["gdsReady"],
            "gdsReady": False,
            "drcClean": False,
            "lvsClean": False,
            "controlReady": control["controlReady"],
            "labReady": lab["labReady"],
            "tapeoutReady": False,
        },
        "componentLibrary": component_library,
        "gdsCellLibrary": {
            "libraryName": "oqp_hrm_cells",
            "format": "GDSII",
            "cells": {
                "waveguide": {"status": component_library["waveguide"], "source": "abstract_layout_plan"},
                "directionalCoupler": {"status": component_library["directionalCoupler"], "source": "eigenmode_fdtd_gap_report"},
                "mzi": {"status": component_library["mzi"], "source": "eigenmode_fdtd_gap_report"},
                "phaseShifter": {"status": component_library["phaseShifter"], "source": "requirements_only"},
                "truthSwitch": {"status": component_library["truthSwitch"], "source": "eigenmode_fdtd_gap_report"},
                "fiberCoupler": {"status": component_library["fiberCoupler"], "source": "missing"},
                "metalRouting": {"status": component_library["metalRouting"], "source": "missing"},
            },
        },
        "drcLvsStatus": {
            "drcDeckInstalled": False,
            "lvsDeckInstalled": False,
            "lastDrcRun": None,
            "lastLvsRun": None,
            "knownBlockers": [
                "no foundry rule deck",
                "no generated GDS",
                "no optical-port and electrical-pad layer map",
            ],
        },
        "foundryRequirements": {
            "selectedFoundryPdk": pdk,
            "pdkInstall": "required",
            "drcDeck": "required",
            "lvsDeck": "required",
            "layerMap": "required",
            "processCornerModels": "required",
            "waiverPolicy": "required",
        },
        "packagingAndIo": {
            "fiberArrayOrEdgeCouplers": "required",
            "fiberPitchUm": 127,
            "opticalPortCount": blueprint.spatial_model.waveguide_count,
            "electricalPads": "required",
            "thermalControl": "required",
            "cryoDetectorInterface": "required" if detector_type.upper() in {"SNSPD", "TES"} else "optional",
            "packageDrawingStatus": "missing",
        },
        "controlStack": control["hardwareRequirements"],
        "labStack": lab["measurementStack"],
        "blockers": sorted(set(blockers)),
        "nextArtifacts": [
            "pdk/component-library.json",
            "layout/gds/oqp_hrm_cells.gds",
            "layout/drc-report.json",
            "layout/lvs-report.json",
            "layout/package-io-plan.json",
            "control/hil-shot-scheduler-report.json",
        ],
    }
