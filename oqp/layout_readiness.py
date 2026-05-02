"""PDK-aware GDS/tapeout readiness reporting."""

from __future__ import annotations

from typing import Any

from .blueprint import Blueprint
from .layout_plan import generate_layout_plan


GENERIC_SI_PHOTONICS_PDK = {
    "name": "generic-si-photonics",
    "waveguideLayer": "WG",
    "metalLayer": "M1",
    "minWaveguideWidthUm": 0.45,
    "minBendRadiusUm": 10.0,
    "minGapUm": 0.18,
    "requiresDrcDeck": True,
    "requiresFoundryPdk": True,
}


def generate_layout_readiness(blueprint: Blueprint, *, pdk: str = "generic-si-photonics") -> dict[str, Any]:
    plan = generate_layout_plan(blueprint)
    blockers = list(plan["gdsBlockers"])
    blockers.extend([
        "No LVS/DRC rule deck installed.",
        "No grating/edge coupler cell selected.",
        "No thermal/electro-optic phase-shifter stack selected.",
        "No detector/source integration stack selected.",
        "No package fiber-array constraints declared.",
    ])
    return {
        "schemaVersion": "open-quantum.layout-readiness.v1",
        "sourcePath": blueprint.source_path,
        "pdk": GENERIC_SI_PHOTONICS_PDK if pdk == "generic-si-photonics" else {"name": pdk},
        "layoutPlanSchema": plan["schemaVersion"],
        "gdsReady": False,
        "tapeoutReady": False,
        "componentLibraryStatus": {
            "waveguide": "abstract",
            "directionalCoupler": "abstract",
            "mzi": "abstract",
            "phaseShifter": "missing",
            "singlePhotonSource": "missing",
            "detector": "missing",
            "metalRouting": "missing",
        },
        "blockers": blockers,
        "nextArtifacts": [
            "pdk/component-library.json",
            "layout/cells/mzi_truth_switch.json",
            "layout/design-rule-check-report.json",
            "layout/package-io-plan.json",
        ],
    }
