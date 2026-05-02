"""Strawberry Fields simulator for OQP-HRM blueprints."""

from __future__ import annotations

import time
import warnings
from typing import Any

import numpy as np

from .blueprint import Blueprint
from .compat import patch_strawberryfields_imports
from .metrics import architecture_score, loss_fraction_to_db, per_stage_loss, transmission_to_db
from .topology import connected_component_count, mzi_pairs


def simulate_blueprint(blueprint: Blueprint) -> dict[str, Any]:
    patch_strawberryfields_imports()

    import strawberryfields as sf
    from strawberryfields.ops import BSgate, LossChannel, Sgate

    started = time.time()
    spatial = blueprint.spatial_model
    metrics = blueprint.metrics
    pairs = mzi_pairs(
        spatial.waveguide_count,
        spatial.interferometer_count,
        spatial.pairing_stride,
    )
    component_count = connected_component_count(spatial.waveguide_count, pairs)

    eng = sf.Engine("gaussian")
    prog = sf.Program(spatial.waveguide_count)

    captured_warnings: list[str] = []
    with prog.context as q:
        for i in range(spatial.waveguide_count):
            Sgate(1.0) | q[i]

        for m1, m2 in pairs:
            BSgate(np.pi / 4, np.pi / 2) | (q[m1], q[m2])

        for i in range(spatial.waveguide_count):
            LossChannel(metrics.heralding_yield) | q[i]

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        result = eng.run(prog)
        captured_warnings.extend(str(item.message) for item in recorded)

    state = result.state
    cov = state.cov()
    trace_yield = float(np.real(np.trace(cov)) / (spatial.waveguide_count * 2))

    total_loss_score_db = loss_fraction_to_db(metrics.attenuation_loss_score)
    total_loss_yield_db = transmission_to_db(metrics.heralding_yield)
    stage_loss_db, stage_loss_fraction = per_stage_loss(
        total_loss_score_db,
        metrics.effective_component_stage_count,
    )
    score = architecture_score(
        heralding_yield=metrics.heralding_yield,
        total_loss_db=total_loss_score_db,
        connected_components=component_count,
        crosstalk_risk_score=metrics.crosstalk_risk_score,
        hop_latency_score=metrics.hop_latency_score,
    )

    return {
        "schemaVersion": "open-quantum.photonic-validation.v1",
        "topologyClass": blueprint.topology_class,
        "solverTarget": blueprint.solver_target,
        "sourcePath": blueprint.source_path,
        "backend": eng.backend_name,
        "durationSeconds": round(time.time() - started, 6),
        "spatialModel": {
            "networkStyle": spatial.network_style,
            "laneMode": spatial.lane_mode,
            "waveguideCount": spatial.waveguide_count,
            "interferometerCount": spatial.interferometer_count,
            "laserWavelengthNm": spatial.laser_wavelength_nm,
            "pairingStride": spatial.pairing_stride,
            "modeGraphConnectedComponents": component_count,
            "mziPairCount": len(pairs),
        },
        "observedMetrics": {
            "sfCovarianceTracePurity": trace_yield,
            "heraldingYield": metrics.heralding_yield,
            "reconstructedAverageHeraldingYieldPercent": metrics.heralding_yield * 100,
            "attenuationLossScore": metrics.attenuation_loss_score,
            "totalMeshPathLossFromAttenuationScoreDb": total_loss_score_db,
            "totalMeshPathLossFromHeraldingYieldDb": total_loss_yield_db,
            "effectiveStageCount": metrics.effective_component_stage_count,
            "effectivePerStageComponentLossDb": stage_loss_db,
            "effectivePerStageComponentLossPercent": stage_loss_fraction * 100,
            "crosstalkRiskScore": metrics.crosstalk_risk_score,
            "hopLatencyScore": metrics.hop_latency_score,
            "architectureScore": score,
        },
        "warnings": captured_warnings,
    }
