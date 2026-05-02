"""Experimental heralded-primitive demonstration audits for OQP-HRM."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path
from typing import Any

from .blueprint import Blueprint


SCHEMA_PREFIX = "open-quantum"


def ingest_primitive_demo_dataset(
    blueprint: Blueprint,
    *,
    dataset_path: str | Path,
    measurement_out: str | Path = "reports/node-alpha/qc-path/primitive-demo-measurement.json",
    dataset_manifest_out: str | Path = "reports/node-alpha/qc-path/primitive-demo-dataset.json",
    primitive: str = "two_qubit_heralded_fusion",
    experimental_status: str = "measured",
) -> dict[str, Any]:
    dataset = Path(dataset_path)
    events, invalid_count = _read_event_records(dataset)
    stats = _event_stats(events)
    dataset_hash = _sha256(dataset)
    manifest = {
        "schemaVersion": f"{SCHEMA_PREFIX}.primitive-demo-dataset.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "path": str(dataset),
        "sha256": dataset_hash,
        "recordCount": len(events),
        "invalidRecordCount": invalid_count,
        "format": "json" if dataset.suffix == ".json" else "jsonl",
    }
    measurement = {
        "schemaVersion": f"{SCHEMA_PREFIX}.primitive-demo-measurement.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "primitive": primitive,
        "experimentalStatus": experimental_status,
        "datasetPath": str(dataset),
        "shotCount": stats["shotCount"],
        "heraldedEventCount": stats["heraldedEventCount"],
        "measuredHeraldingSuccessProbability": stats["heraldingSuccessProbability"],
        "measuredProcessFidelity": stats["processFidelityLowerBound"],
        "processFidelityMean": stats["processFidelityMean"],
        "processFidelityUncertainty": stats["processFidelityUncertainty"],
        "measuredFeedForwardLatencyNs": stats["feedForwardLatencyMaxNs"],
        "feedForwardLatencyMeanNs": stats["feedForwardLatencyMeanNs"],
        "feedForwardLatencyP95Ns": stats["feedForwardLatencyP95Ns"],
        "invalidRecordCount": invalid_count,
        "fieldCoverage": stats["fieldCoverage"],
    }
    _write_json(Path(measurement_out), measurement)
    _write_json(Path(dataset_manifest_out), manifest)
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.primitive-demo-ingest.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "artifactRefs": {
            "measurementReport": str(measurement_out),
            "datasetManifest": str(dataset_manifest_out),
            "dataset": str(dataset),
        },
        "datasetManifest": manifest,
        "measurement": measurement,
        "summary": {
            "recordCount": len(events),
            "invalidRecordCount": invalid_count,
            "shotCount": stats["shotCount"],
            "heraldedEventCount": stats["heraldedEventCount"],
            "heraldingSuccessProbability": stats["heraldingSuccessProbability"],
            "processFidelityLowerBound": stats["processFidelityLowerBound"],
            "feedForwardLatencyMaxNs": stats["feedForwardLatencyMaxNs"],
        },
        "blockers": _ingest_blockers(events, invalid_count, stats),
    }


def generate_primitive_demo_audit(
    blueprint: Blueprint,
    *,
    measurement_report_path: str | Path | None = "reports/node-alpha/qc-path/primitive-demo-measurement.json",
    dataset_manifest_path: str | Path | None = "reports/node-alpha/qc-path/primitive-demo-dataset.json",
    hardware_audit_path: str | Path | None = "reports/node-alpha/qc-path/hardware-audit.json",
    fusion_report_path: str | Path | None = "reports/node-alpha/qc-path/fusion-primitive.json",
    min_shots: int = 1000,
    min_heralded_events: int = 10,
    min_heralding_success_probability: float = 0.01,
    min_process_fidelity: float = 0.99,
    max_feed_forward_latency_ns: float = 10.0,
) -> dict[str, Any]:
    measurement = _read_json(measurement_report_path)
    dataset = _dataset_report(_read_json(dataset_manifest_path))
    hardware = _read_json(hardware_audit_path)
    fusion = _read_json(fusion_report_path)
    metrics = _measurement_metrics(measurement)
    hardware_ready = bool(hardware and hardware.get("readinessFlags", {}).get("hardware_ready"))
    modeled_ready = bool(fusion and fusion.get("readinessFlags", {}).get("primitiveReady"))
    blockers = _blockers(
        measurement=measurement,
        metrics=metrics,
        dataset=dataset,
        hardware_ready=hardware_ready,
        modeled_ready=modeled_ready,
        min_shots=min_shots,
        min_heralded_events=min_heralded_events,
        min_heralding_success_probability=min_heralding_success_probability,
        min_process_fidelity=min_process_fidelity,
        max_feed_forward_latency_ns=max_feed_forward_latency_ns,
    )
    flags = {
        "measurement_report_present": bool(measurement),
        "dataset_verified": dataset["verified"],
        "hardware_ready": hardware_ready,
        "modeled_primitive_ready": modeled_ready,
        "shot_count_sufficient": metrics["shotCount"] >= min_shots,
        "heralded_event_count_sufficient": metrics["heraldedEventCount"] >= min_heralded_events,
        "heralding_success_pass": metrics["measuredHeraldingSuccessProbability"] >= min_heralding_success_probability,
        "process_fidelity_pass": metrics["measuredProcessFidelity"] >= min_process_fidelity,
        "feed_forward_latency_pass": metrics["measuredFeedForwardLatencyNs"] <= max_feed_forward_latency_ns,
        "primitive_demonstrated": not blockers,
    }
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.primitive-demo-audit.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "artifactInputs": {
            "measurementReport": str(measurement_report_path) if measurement_report_path else None,
            "datasetManifest": str(dataset_manifest_path) if dataset_manifest_path else None,
            "hardwareAudit": str(hardware_audit_path) if hardware_audit_path else None,
            "fusionPrimitive": str(fusion_report_path) if fusion_report_path else None,
        },
        "targets": {
            "minShots": min_shots,
            "minHeraldedEvents": min_heralded_events,
            "minHeraldingSuccessProbability": min_heralding_success_probability,
            "minProcessFidelity": min_process_fidelity,
            "maxFeedForwardLatencyNs": max_feed_forward_latency_ns,
        },
        "readinessFlags": flags,
        "measurement": {
            "present": bool(measurement),
            "primitive": measurement.get("primitive") if measurement else None,
            "experimentalStatus": measurement.get("experimentalStatus") if measurement else None,
            "metrics": metrics,
        },
        "dataset": dataset,
        "hardwareEvidence": {
            "present": bool(hardware),
            "hardwareReady": hardware_ready,
        },
        "modelEvidence": {
            "present": bool(fusion),
            "primitiveReady": modeled_ready,
            "status": fusion.get("status") if fusion else None,
        },
        "blockers": blockers,
        "nextArtifacts": [
            "reports/node-alpha/qc-path/primitive-demo-measurement.json",
            "reports/node-alpha/qc-path/primitive-demo-dataset.json",
            "reports/node-alpha/qc-path/primitive-demo-audit.json",
        ],
    }


def _read_json(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    target = Path(path)
    if not target.is_file():
        return {}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _read_event_records(path: Path) -> tuple[list[dict[str, Any]], int]:
    if not path.is_file():
        raise FileNotFoundError(f"Primitive demo dataset does not exist: {path}")
    invalid = 0
    records: list[dict[str, Any]] = []
    if path.suffix == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("events", [])
        else:
            items = []
        for item in items:
            if isinstance(item, dict):
                records.append(item)
            else:
                invalid += 1
        return records, invalid
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                item = json.loads(text)
            except json.JSONDecodeError:
                invalid += 1
                continue
            if isinstance(item, dict):
                records.append(item)
            else:
                invalid += 1
    return records, invalid


def _event_stats(events: list[dict[str, Any]]) -> dict[str, Any]:
    shot_ids = {_shot_id(event, index) for index, event in enumerate(events)}
    shot_count = len(shot_ids)
    heralded = [event for event in events if _is_heralded(event)]
    fidelity_values = [_float_value(event, ("processFidelity", "fidelity", "measuredProcessFidelity")) for event in heralded]
    fidelity_values = [value for value in fidelity_values if value is not None]
    latency_values = [_float_value(event, ("feedForwardLatencyNs", "latencyNs", "measuredFeedForwardLatencyNs")) for event in events]
    latency_values = [value for value in latency_values if value is not None]
    fidelity_mean = sum(fidelity_values) / len(fidelity_values) if fidelity_values else 0.0
    fidelity_uncertainty = _standard_error(fidelity_values) if fidelity_values else 1.0
    fidelity_lower_bound = max(0.0, fidelity_mean - 2.0 * fidelity_uncertainty)
    return {
        "shotCount": shot_count,
        "heraldedEventCount": len(heralded),
        "heraldingSuccessProbability": len(heralded) / shot_count if shot_count else 0.0,
        "processFidelityMean": fidelity_mean,
        "processFidelityUncertainty": fidelity_uncertainty,
        "processFidelityLowerBound": fidelity_lower_bound,
        "feedForwardLatencyMeanNs": sum(latency_values) / len(latency_values) if latency_values else 1e18,
        "feedForwardLatencyP95Ns": _percentile(latency_values, 0.95) if latency_values else 1e18,
        "feedForwardLatencyMaxNs": max(latency_values) if latency_values else 1e18,
        "fieldCoverage": {
            "processFidelityRecords": len(fidelity_values),
            "feedForwardLatencyRecords": len(latency_values),
        },
    }


def _shot_id(event: dict[str, Any], index: int) -> str:
    for key in ("shot", "shotId", "shot_id", "trial", "trialId"):
        if key in event:
            return str(event[key])
    return str(index)


def _is_heralded(event: dict[str, Any]) -> bool:
    if "heralded" in event:
        return bool(event["heralded"])
    if "heraldedEvent" in event:
        return bool(event["heraldedEvent"])
    outcome = str(event.get("outcome") or event.get("status") or "").strip().lower()
    return outcome in {"heralded", "success", "accepted", "detected"}


def _float_value(event: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key not in event:
            continue
        try:
            return float(event[key])
        except (TypeError, ValueError):
            return None
    return None


def _standard_error(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0 if values else 1.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return sqrt(variance) / sqrt(len(values))


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 1e18
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, max(0, int(round((len(sorted_values) - 1) * quantile))))
    return sorted_values[index]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ingest_blockers(events: list[dict[str, Any]], invalid_count: int, stats: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if not events:
        blockers.append("primitive_demo_ingest: dataset contains no valid event records.")
    if invalid_count:
        blockers.append(f"primitive_demo_ingest: {invalid_count} invalid records were skipped.")
    if stats["fieldCoverage"]["processFidelityRecords"] == 0:
        blockers.append("primitive_demo_ingest: no heralded records include process fidelity.")
    if stats["fieldCoverage"]["feedForwardLatencyRecords"] == 0:
        blockers.append("primitive_demo_ingest: no records include feed-forward latency.")
    return blockers


def _measurement_metrics(measurement: dict[str, Any]) -> dict[str, float | int]:
    if not measurement:
        return {
            "shotCount": 0,
            "heraldedEventCount": 0,
            "measuredHeraldingSuccessProbability": 0.0,
            "measuredProcessFidelity": 0.0,
            "processFidelityUncertainty": 1.0,
            "measuredFeedForwardLatencyNs": 1e18,
        }
    shot_count = int(measurement.get("shotCount", 0))
    event_count = int(measurement.get("heraldedEventCount", 0))
    success = float(
        measurement.get(
            "measuredHeraldingSuccessProbability",
            event_count / shot_count if shot_count > 0 else 0.0,
        )
    )
    return {
        "shotCount": shot_count,
        "heraldedEventCount": event_count,
        "measuredHeraldingSuccessProbability": success,
        "measuredProcessFidelity": float(measurement.get("measuredProcessFidelity", 0.0)),
        "processFidelityUncertainty": float(measurement.get("processFidelityUncertainty", 1.0)),
        "measuredFeedForwardLatencyNs": float(measurement.get("measuredFeedForwardLatencyNs", 1e18)),
    }


def _dataset_report(dataset: dict[str, Any]) -> dict[str, Any]:
    path = dataset.get("path") if dataset else None
    expected_hash = dataset.get("sha256") if dataset else None
    exists = bool(path and Path(path).is_file())
    actual_hash = _sha256(path) if exists else None
    verified = bool(exists and expected_hash and actual_hash == expected_hash)
    return {
        "present": bool(dataset),
        "path": str(path) if path else None,
        "sha256": expected_hash,
        "actualSha256": actual_hash,
        "verified": verified,
        "recordCount": dataset.get("recordCount") if dataset else None,
    }


def _sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _blockers(
    *,
    measurement: dict[str, Any],
    metrics: dict[str, float | int],
    dataset: dict[str, Any],
    hardware_ready: bool,
    modeled_ready: bool,
    min_shots: int,
    min_heralded_events: int,
    min_heralding_success_probability: float,
    min_process_fidelity: float,
    max_feed_forward_latency_ns: float,
) -> list[str]:
    blockers: list[str] = []
    if not measurement:
        blockers.append("primitive_demo: no measured primitive report is attached.")
    elif str(measurement.get("experimentalStatus", "")).lower() not in {"measured", "validated", "demonstrated"}:
        blockers.append("primitive_demo: experimentalStatus is not measured/validated/demonstrated.")
    if not dataset["verified"]:
        blockers.append("primitive_demo: dataset manifest is missing or SHA-256 verification failed.")
    if not hardware_ready:
        blockers.append("primitive_demo: hardware-audit is not hardware_ready.")
    if not modeled_ready:
        blockers.append("primitive_demo: modeled fusion primitive is not primitiveReady.")
    if metrics["shotCount"] < min_shots:
        blockers.append(f"primitive_demo: shot count {metrics['shotCount']} below {min_shots}.")
    if metrics["heraldedEventCount"] < min_heralded_events:
        blockers.append(f"primitive_demo: heralded event count {metrics['heraldedEventCount']} below {min_heralded_events}.")
    if metrics["measuredHeraldingSuccessProbability"] < min_heralding_success_probability:
        blockers.append(
            "primitive_demo: measured heralding success "
            f"{metrics['measuredHeraldingSuccessProbability']:.6g} below {min_heralding_success_probability}."
        )
    if metrics["measuredProcessFidelity"] < min_process_fidelity:
        blockers.append(
            f"primitive_demo: measured process fidelity {metrics['measuredProcessFidelity']:.6g} below {min_process_fidelity}."
        )
    if metrics["measuredFeedForwardLatencyNs"] > max_feed_forward_latency_ns:
        blockers.append(
            "primitive_demo: measured feed-forward latency "
            f"{metrics['measuredFeedForwardLatencyNs']:.6g} ns above {max_feed_forward_latency_ns} ns."
        )
    return blockers
