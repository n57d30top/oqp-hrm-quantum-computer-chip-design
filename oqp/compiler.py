"""OQP-HRM compiler and runtime trace generation."""

from __future__ import annotations

from typing import Any

from .blueprint import Blueprint
from .topology import connected_component_count, mzi_pairs


def compile_blueprint(
    blueprint: Blueprint,
    *,
    shots: int = 1000,
    encoding: str = "dual_rail",
    reset_condition: str = "herald_detected",
) -> dict[str, Any]:
    spatial = blueprint.spatial_model
    pairs = mzi_pairs(spatial.waveguide_count, spatial.interferometer_count, spatial.pairing_stride)
    instructions: list[dict[str, Any]] = []
    for mode in range(spatial.waveguide_count):
        instructions.append({"op": "PREPARE", "mode": mode, "state": "vacuum"})
    for index, (mode_a, mode_b) in enumerate(pairs):
        instructions.append({"op": "ROUTE", "index": index, "modes": [mode_a, mode_b], "target": f"mzi_{index}"})
        instructions.append({"op": "MZI", "index": index, "modeA": mode_a, "modeB": mode_b, "theta": "pi/4", "phi": "pi/2"})
        instructions.append({"op": "PHASE", "index": index, "mode": mode_a, "angle": 0.0})
    for mode in range(spatial.waveguide_count):
        instructions.append({"op": "MEASURE", "mode": mode, "basis": "number", "target": f"c{mode}"})
        instructions.append({"op": "HERALD_WAIT", "detector": mode, "condition": reset_condition, "target": f"h{mode}"})
        instructions.append({"op": "RESET", "mode": mode, "targetState": "computational_basis", "when": f"h{mode}"})
    logical_qubits = spatial.waveguide_count // (2 if encoding == "dual_rail" else 1)
    instructions.append({
        "op": "RESULT_DECODE",
        "encoding": encoding,
        "method": "dual_rail_occupancy" if encoding == "dual_rail" else "cv_gkp_syndrome_placeholder",
        "logicalQubitCount": logical_qubits,
        "classicalInputs": [f"c{mode}" for mode in range(spatial.waveguide_count)],
    })

    return {
        "schemaVersion": "open-quantum.compiler-trace.v1",
        "topologyClass": blueprint.topology_class,
        "sourcePath": blueprint.source_path,
        "encoding": encoding,
        "shots": shots,
        "instructionCount": len(instructions),
        "connectedComponents": connected_component_count(spatial.waveguide_count, pairs),
        "resultDecoding": {
            "encoding": encoding,
            "method": "dual_rail_occupancy" if encoding == "dual_rail" else "cv_gkp_syndrome_placeholder",
            "logicalQubitCount": logical_qubits,
        },
        "instructions": instructions,
    }


def runtime_trace(compiled: dict[str, Any], *, feed_forward_latency_ns: float = 5.0) -> dict[str, Any]:
    instructions = compiled["instructions"]
    timing: list[dict[str, Any]] = []
    time_ns = 0.0
    for index, instruction in enumerate(instructions):
        op = instruction["op"]
        duration = {
            "PREPARE": 1.0,
            "MZI": 0.5,
            "PHASE": 0.5,
            "MEASURE": 2.0,
            "HERALD_WAIT": feed_forward_latency_ns,
            "RESET": 1.0,
            "ROUTE": 1.0,
            "RESULT_DECODE": 0.2,
        }.get(op, 1.0)
        timing.append({"step": index, "op": op, "startNs": time_ns, "durationNs": duration, "endNs": time_ns + duration})
        time_ns += duration

    return {
        "schemaVersion": "open-quantum.runtime-trace.v1",
        "compilerTraceSchema": compiled["schemaVersion"],
        "shots": compiled["shots"],
        "feedForwardLatencyNs": feed_forward_latency_ns,
        "totalProgramTimeNsPerShot": time_ns,
        "estimatedBatchTimeMs": (time_ns * compiled["shots"]) / 1_000_000,
        "timing": timing,
    }
