"""Metric calculations for OQP-HRM validation reports."""

from __future__ import annotations

import math


def loss_fraction_to_db(loss_fraction: float) -> float:
    if not 0 <= loss_fraction < 1:
        raise ValueError("loss_fraction must be in the range [0, 1)")
    return -10 * math.log10(1 - loss_fraction)


def transmission_to_db(transmission: float) -> float:
    if not 0 < transmission <= 1:
        raise ValueError("transmission must be in the range (0, 1]")
    return -10 * math.log10(transmission)


def per_stage_loss(total_db_loss: float, stage_count: int) -> tuple[float, float]:
    if stage_count <= 0:
        raise ValueError("stage_count must be positive")
    stage_db = total_db_loss / stage_count
    stage_fraction = 1 - 10 ** (-stage_db / 10)
    return stage_db, stage_fraction


def architecture_score(
    *,
    heralding_yield: float,
    total_loss_db: float,
    connected_components: int,
    crosstalk_risk_score: float,
    hop_latency_score: float,
) -> float:
    connectivity_penalty = max(0, connected_components - 1) * 0.025
    return (
        heralding_yield * 100
        - total_loss_db * 6
        - crosstalk_risk_score * 12
        - (1 - hop_latency_score) * 5
        - connectivity_penalty * 100
    )
