"""MEEP/FDTD availability probe for future OQP physical validation."""

from __future__ import annotations

import time
from typing import Any


def run_meep_probe() -> dict[str, Any]:
    started = time.time()
    import meep as mp

    cell = mp.Vector3(1, 1, 0)
    simulation = mp.Simulation(
        cell_size=cell,
        boundary_layers=[mp.PML(0.1)],
        resolution=10,
    )
    simulation.init_sim()
    return {
        "schemaVersion": "open-quantum.fdtd-probe.v1",
        "backend": "meep",
        "meepVersion": getattr(mp, "__version__", "unknown"),
        "cell": {"x": 1, "y": 1, "z": 0},
        "resolution": 10,
        "durationSeconds": round(time.time() - started, 6),
        "ok": True,
    }
