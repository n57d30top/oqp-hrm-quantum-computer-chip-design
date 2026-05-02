"""Candidate sweep and optimizer helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Iterable

from .blueprint import Blueprint, write_blueprint
from .report import write_json_report


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    blueprint: Blueprint


def generate_grid_candidates(
    base: Blueprint,
    *,
    waveguides: Iterable[int],
    interferometers: Iterable[int],
    strides: Iterable[int],
) -> list[Candidate]:
    candidates: list[Candidate] = []
    for waveguide_count, interferometer_count, stride in product(waveguides, interferometers, strides):
        candidate_id = f"m{waveguide_count}_d{interferometer_count}_s{stride}"
        candidates.append(
            Candidate(
                candidate_id=candidate_id,
                blueprint=base.mutate(
                    waveguide_count=waveguide_count,
                    interferometer_count=interferometer_count,
                    pairing_stride=stride,
                ),
            )
        )
    return candidates


def generate_optimizer_candidates(base: Blueprint, budget: int) -> list[Candidate]:
    if budget <= 0:
        raise ValueError("budget must be positive")

    base_modes = base.spatial_model.waveguide_count
    base_depth = base.spatial_model.interferometer_count
    waveguides = [base_modes]
    if base_modes < 144:
        waveguides.append(base_modes * 2)

    depths = sorted(
        {
            max(1, base_depth // 2),
            base_depth,
            base_depth + max(1, base_depth // 2),
            base_depth * 2,
        }
    )
    strides = [1, 2, 3, 4, 5]
    candidates = generate_grid_candidates(
        base,
        waveguides=waveguides,
        interferometers=depths,
        strides=strides,
    )
    return candidates[:budget]


def run_candidates(candidates: list[Candidate], output_dir: str | Path) -> list[dict]:
    from .simulator_sf import simulate_blueprint

    root = Path(output_dir)
    results: list[dict] = []
    for candidate in candidates:
        candidate_dir = root / candidate.candidate_id
        blueprint_path = candidate_dir / "blueprint.yaml"
        report_path = candidate_dir / "validation.json"
        write_blueprint(candidate.blueprint, blueprint_path)
        report = simulate_blueprint(candidate.blueprint)
        report["candidateId"] = candidate.candidate_id
        report["artifactRefs"] = {
            "blueprint": str(blueprint_path),
            "validationReport": str(report_path),
        }
        write_json_report(report, report_path)
        results.append(report)

    ranked = sorted(
        results,
        key=lambda item: item["observedMetrics"]["architectureScore"],
        reverse=True,
    )
    write_json_report({"schemaVersion": "open-quantum.photonic-sweep.v1", "results": ranked}, root / "index.json")
    if ranked:
        write_json_report(ranked[0], root / "champion.json")
        write_json_report(
            {
                "schemaVersion": "open-quantum.champion-registry.v1",
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "selectionPolicy": "max observedMetrics.architectureScore",
                "resultCount": len(ranked),
                "champions": [ranked[0]],
            },
            root / "champion-registry.json",
        )
    return ranked
