"""Small reproducible MEEP device sweeps for OQP-HRM primitive cells."""

from __future__ import annotations

from itertools import product
import json
import math
from pathlib import Path
from typing import Any

from .blueprint import Blueprint
from .eigenmode_device import MIN_OUTPUT_PORT_NORMALIZATION_FLUX, run_eigenmode_device
from .report import write_json_report


def score_device(report: dict[str, Any]) -> float:
    return _score_terms(report)["score"]


def _score_terms(report: dict[str, Any]) -> dict[str, float]:
    metrics = report["fdtdMetrics"]
    useful = metrics.get("usefulTransmission", metrics.get("throughRatio", 0.0) + metrics.get("crossRatio", 0.0))
    bounded_useful = min(max(float(useful), 0.0), 1.0)
    balance_penalty = abs(float(metrics.get("throughRatio", 0.0)) - float(metrics.get("crossRatio", 0.0)))
    crosstalk = float(metrics.get("crosstalkRatio", metrics.get("imbalanceRatio", 0.0)))
    reflection = float(metrics.get("reflectionRatio", 0.0))
    insertion = float(metrics.get("insertionLossDb", 0.0))
    normalization_penalty = _normalization_penalty(metrics)
    crosstalk_penalty = 100.0 * max(0.0, crosstalk - 0.05)
    score = (
        (100.0 * bounded_useful)
        - (50.0 * reflection)
        - insertion
        - (10.0 * balance_penalty)
        - crosstalk_penalty
        - normalization_penalty
    )
    return {
        "score": score,
        "boundedUsefulTransmission": bounded_useful,
        "normalizationPenalty": normalization_penalty,
        "reflectionPenalty": 50.0 * reflection,
        "insertionLossPenalty": insertion,
        "balancePenalty": 10.0 * balance_penalty,
        "crosstalkPenalty": crosstalk_penalty,
    }


def run_device_sweep(
    blueprint: Blueprint,
    *,
    devices: list[str],
    coupling_gaps_um: list[float],
    coupling_lengths_um: list[float],
    phase_shifts_rad: list[float],
    waveguide_widths_um: list[float],
    resolution: int = 10,
    until: float = 20.0,
    max_runs: int = 12,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    run_count = 0
    for gap, length, phase, width, device in product(coupling_gaps_um, coupling_lengths_um, phase_shifts_rad, waveguide_widths_um, devices):
        if run_count >= max_runs:
            break
        report = run_eigenmode_device(
            blueprint,
            device=device,
            resolution=resolution,
            until=until,
            coupling_gap_um=gap,
            coupling_length_um=length,
            phase_shift_rad=phase,
            waveguide_width_um=width,
        )
        report["candidateId"] = f"{device}_gap{gap:g}_len{length:g}_phi{phase:g}_w{width:g}".replace(".", "p")
        report["score"] = score_device(report)
        report["scoreTerms"] = _score_terms(report)
        candidates.append(report)
        if out_dir:
            write_json_report(report, Path(out_dir) / f"{report['candidateId']}.json")
        run_count += 1

    summary = _build_sweep_summary(
        blueprint,
        candidates,
        devices=devices,
        resolution=resolution,
        until=until,
    )
    champion = summary["champion"]
    if out_dir:
        write_json_report(summary, Path(out_dir) / "device-sweep.json")
        if champion:
            write_json_report(champion, Path(out_dir) / "champion.json")
    return summary


def rerank_device_sweep(
    blueprint: Blueprint,
    *,
    evidence_dir: str | Path,
    devices: list[str],
    out: str | Path | None = None,
) -> dict[str, Any]:
    """Re-score existing per-candidate device reports without re-running MEEP."""

    base = Path(evidence_dir)
    candidates = _load_existing_candidates(base)
    if devices:
        requested = {_normalize_device(device) for device in devices}
        candidates = [candidate for candidate in candidates if _normalize_device(candidate["device"]) in requested]
    resolution = max((int(candidate.get("fdtdMetrics", {}).get("timing", {}).get("resolution", 0)) for candidate in candidates), default=0)
    until = max((float(candidate.get("fdtdMetrics", {}).get("timing", {}).get("until", 0.0)) for candidate in candidates), default=0.0)
    summary = _build_sweep_summary(
        blueprint,
        candidates,
        devices=devices,
        resolution=resolution,
        until=until,
        source_artifact=str(base),
        reranked=True,
    )
    if out:
        write_json_report(summary, out)
    return summary


def _build_sweep_summary(
    blueprint: Blueprint,
    candidates: list[dict[str, Any]],
    *,
    devices: list[str],
    resolution: int,
    until: float,
    source_artifact: str | None = None,
    reranked: bool = False,
) -> dict[str, Any]:
    for candidate in candidates:
        candidate["score"] = score_device(candidate)
        candidate["scoreTerms"] = _score_terms(candidate)
    ranked = sorted(candidates, key=_candidate_rank, reverse=True)
    champion = ranked[0] if ranked else None
    per_device_champions = _per_device_champions(devices, ranked)
    accepted = _all_requested_devices_accepted(devices, per_device_champions)
    validation_tier = _validation_tier(resolution, until)
    status = "all_requested_devices_accepted" if accepted else "no_accepted_candidate"
    if not accepted and validation_tier == "high_resolution_gap_probe":
        status = "high_resolution_gap_quantified"
    summary = {
        "schemaVersion": "open-quantum.device-sweep.v1",
        "sourcePath": blueprint.source_path,
        "sourceArtifact": source_artifact,
        "rerankedFromExistingEvidence": reranked,
        "runCount": len(ranked),
        "resolution": resolution,
        "until": until,
        "validationTier": validation_tier,
        "deviceCoverage": _device_coverage(devices, ranked),
        "champion": champion,
        "alternatives": ranked[1:10],
        "acceptance": {
            "maxInsertionLossDb": 1.0,
            "maxReflectionRatio": 0.05,
            "maxCrosstalkRatio": 0.05,
            "minOutputPortNormalizationFlux": MIN_OUTPUT_PORT_NORMALIZATION_FLUX,
            "minUsefulTransmission": 0.5,
        },
        "status": status,
        "championGapToAcceptance": _gap_to_acceptance(champion),
        "perDeviceChampions": per_device_champions,
        "perDeviceGapToAcceptance": {
            device: _gap_to_acceptance(per_device_champions.get(device)) for device in devices
        },
        "gapSummary": _gap_summary(champion, validation_tier, devices, per_device_champions),
        "nextSteps": [
            "Promote accepted cells to 3D/MPB mode analysis before GDS cell promotion.",
            "Sweep bend/coupler geometry at higher resolution and larger parameter ranges.",
            "Add 3D/MPB mode analysis before GDS cell promotion.",
        ],
    }
    return summary


def _load_existing_candidates(base: Path) -> list[dict[str, Any]]:
    direct: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(base.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if raw.get("device") and isinstance(raw.get("fdtdMetrics"), dict):
            candidate = dict(raw)
            candidate.setdefault("candidateId", path.stem)
            key = str(candidate.get("candidateId") or path)
            if key not in seen:
                seen.add(key)
                direct.append(candidate)
        else:
            summaries.append(raw)
    if direct:
        return direct
    for raw in summaries:
        for candidate in _expand_summary_candidates(raw):
            key = str(candidate.get("candidateId") or f"{candidate.get('device')}:{len(direct)}")
            if key not in seen:
                seen.add(key)
                direct.append(candidate)
    return direct


def _expand_summary_candidates(raw: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if isinstance(raw.get("champion"), dict):
        candidates.append(dict(raw["champion"]))
    if isinstance(raw.get("alternatives"), list):
        candidates.extend(dict(item) for item in raw["alternatives"] if isinstance(item, dict))
    if isinstance(raw.get("perDeviceChampions"), dict):
        candidates.extend(dict(item) for item in raw["perDeviceChampions"].values() if isinstance(item, dict))
    return [candidate for candidate in candidates if candidate.get("device") and isinstance(candidate.get("fdtdMetrics"), dict)]


def _normalization_penalty(metrics: dict[str, Any]) -> float:
    if metrics.get("normalizationReliable") is not False:
        return 0.0
    output_flux = float(metrics.get("outputPortNormalizationFlux") or 0.0)
    if output_flux <= 0.0:
        return 500.0
    shortfall = MIN_OUTPUT_PORT_NORMALIZATION_FLUX / output_flux
    return 100.0 * max(0.0, math.log10(shortfall))


def _candidate_rank(candidate: dict[str, Any]) -> tuple[int, int, float]:
    metrics = candidate.get("fdtdMetrics", {})
    norm_flag = metrics.get("normalizationReliable")
    norm_rank = 2 if norm_flag is True else 1 if norm_flag is None else 0
    return (1 if _accepted(candidate) else 0, norm_rank, float(candidate.get("score", score_device(candidate))))


def _per_device_champions(devices: list[str], ranked: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    champions: dict[str, dict[str, Any]] = {}
    requested = {_normalize_device(device) for device in devices}
    for candidate in ranked:
        device = _normalize_device(candidate["device"])
        if device in requested and device not in champions:
            champions[device] = candidate
    return champions


def _all_requested_devices_accepted(devices: list[str], per_device_champions: dict[str, dict[str, Any]]) -> bool:
    return bool(devices) and all(_accepted(per_device_champions.get(_normalize_device(device))) for device in devices)


def _accepted(champion: dict[str, Any] | None) -> bool:
    if not champion:
        return False
    metrics = champion["fdtdMetrics"]
    return (
        metrics["insertionLossDb"] <= 1.0
        and metrics["reflectionRatio"] <= 0.05
        and metrics["throughRatio"] + metrics["crossRatio"] >= 0.5
        and metrics.get("crosstalkRatio", metrics.get("imbalanceRatio", 0.0)) <= 0.05
        and metrics.get("normalizationReliable") is not False
    )


def _validation_tier(resolution: int, until: float) -> str:
    if resolution >= 16 and until >= 40:
        return "high_resolution_gap_probe"
    if resolution >= 12 and until >= 30:
        return "medium_resolution_gap_probe"
    return "first_pass_gap_probe"


def _device_coverage(requested_devices: list[str], ranked: list[dict[str, Any]]) -> dict[str, Any]:
    observed = {candidate["device"] for candidate in ranked}
    return {
        "requestedDevices": requested_devices,
        "observedDevices": sorted(observed),
        "missingDevices": [device for device in requested_devices if device not in observed],
        "complete": all(device in observed for device in requested_devices),
    }


def _normalize_device(device: str) -> str:
    lowered = device.strip().lower().replace("_", "-")
    if lowered in {"directional-coupler", "dc"}:
        return "coupler"
    if lowered in {"phase", "phase-shifter"}:
        return "phase-shifter"
    if lowered in {"truth-switch", "truthswitch"}:
        return "truth-switch"
    return lowered


def _gap_to_acceptance(champion: dict[str, Any] | None) -> dict[str, Any] | None:
    if not champion:
        return None
    metrics = champion["fdtdMetrics"]
    useful = metrics.get("usefulTransmission", metrics["throughRatio"] + metrics["crossRatio"])
    gap = {
        "candidateId": champion["candidateId"],
        "device": champion["device"],
        "usefulTransmission": useful,
        "usefulTransmissionTarget": 0.5,
        "usefulTransmissionFactorBelowTarget": 0.5 / max(useful, 1e-18),
        "insertionLossDb": metrics["insertionLossDb"],
        "insertionLossDbTarget": 1.0,
        "insertionLossDbExcess": max(0.0, metrics["insertionLossDb"] - 1.0),
        "reflectionRatio": metrics["reflectionRatio"],
        "reflectionRatioTarget": 0.05,
        "reflectionRatioExcess": max(0.0, metrics["reflectionRatio"] - 0.05),
        "crosstalkRatio": metrics.get("crosstalkRatio", metrics.get("imbalanceRatio", 0.0)),
        "crosstalkRatioTarget": 0.05,
        "crosstalkRatioExcess": max(0.0, metrics.get("crosstalkRatio", metrics.get("imbalanceRatio", 0.0)) - 0.05),
        "normalizationReliable": metrics.get("normalizationReliable") is not False,
        "outputPortNormalizationFlux": metrics.get("outputPortNormalizationFlux"),
        "outputPortNormalizationFluxTarget": MIN_OUTPUT_PORT_NORMALIZATION_FLUX,
    }
    if champion["device"] in {"mzi", "phase-shifter"}:
        gap["operatingPoint"] = "through_state_low_leakage"
        gap["imbalanceRatio"] = metrics.get("imbalanceRatio")
        gap["imbalanceRatioNote"] = (
            "Not an acceptance blocker for through-state MZI/phase-shifter operation; "
            "balanced splitting must be swept as a separate operating point."
        )
    return gap


def _gap_summary(
    champion: dict[str, Any] | None,
    validation_tier: str,
    devices: list[str] | None = None,
    per_device_champions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    per_device_gaps = {
        device: _gap_to_acceptance((per_device_champions or {}).get(_normalize_device(device)))
        for device in (devices or [])
    }
    blocking_metric = _first_blocking_metric(per_device_gaps.values()) if per_device_gaps else None
    gap = _gap_to_acceptance(champion)
    if not gap:
        return {
            "status": "no_candidates",
            "validationTier": validation_tier,
            "blockingMetric": "no_device_run",
        }
    if blocking_metric:
        pass
    elif gap.get("normalizationReliable") is False:
        blocking_metric = "normalization_reliability"
    elif gap["usefulTransmission"] < 0.5:
        blocking_metric = "useful_transmission"
    elif gap["insertionLossDb"] > 1.0:
        blocking_metric = "insertion_loss"
    elif gap["reflectionRatio"] > 0.05:
        blocking_metric = "reflection"
    elif gap["crosstalkRatio"] > 0.05:
        blocking_metric = "crosstalk"
    else:
        blocking_metric = "acceptance_metadata"
    return {
        "status": "accepted" if not _first_blocking_metric(per_device_gaps.values()) and _accepted(champion) else "gap_quantified",
        "validationTier": validation_tier,
        "blockingMetric": blocking_metric,
        "perDeviceBlockingMetrics": {
            device: _first_blocking_metric([gap]) if gap else "no_device_run"
            for device, gap in per_device_gaps.items()
        },
        "interpretation": (
            "High-resolution evidence is sufficient to treat this as a quantified geometry/source-monitor gap."
            if validation_tier == "high_resolution_gap_probe"
            else "First-pass or medium-resolution evidence; rerun at resolution >= 16 and until >= 40 before closing the physics gap."
        ),
    }


def _first_blocking_metric(gaps: Any) -> str | None:
    for gap in gaps:
        if not gap:
            return "no_device_run"
        if gap.get("normalizationReliable") is False:
            return "normalization_reliability"
        if gap["usefulTransmission"] < 0.5:
            return "useful_transmission"
        if gap["insertionLossDb"] > 1.0:
            return "insertion_loss"
        if gap["reflectionRatio"] > 0.05:
            return "reflection"
        if gap["crosstalkRatio"] > 0.05:
            return "crosstalk"
    return None
