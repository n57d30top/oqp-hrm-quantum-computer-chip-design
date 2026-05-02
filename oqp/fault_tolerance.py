"""Fault-tolerance and decoder-validation audits for OQP-HRM."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path
from typing import Any

from .blueprint import Blueprint


SCHEMA_PREFIX = "open-quantum"
IMPLEMENTED_DECODER_STATUSES = {"implemented", "validated", "benchmarked", "hardware_validated"}


def ingest_fault_tolerance_dataset(
    blueprint: Blueprint,
    *,
    dataset_path: str | Path,
    decoder_report_out: str | Path = "reports/node-alpha/qc-path/decoder-report.json",
    noise_dataset_manifest_out: str | Path = "reports/node-alpha/qc-path/syndrome-noise-dataset.json",
    decoder: str = "analytical_erasure_matching",
    implementation_status: str = "benchmarked",
) -> dict[str, Any]:
    dataset = Path(dataset_path)
    events, invalid_count = _read_event_records(dataset)
    stats = _syndrome_stats(events)
    dataset_hash = _sha256(dataset)
    manifest = {
        "schemaVersion": f"{SCHEMA_PREFIX}.syndrome-noise-dataset.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "path": str(dataset),
        "sha256": dataset_hash,
        "recordCount": len(events),
        "invalidRecordCount": invalid_count,
        "format": "json" if dataset.suffix == ".json" else "jsonl",
        "logicalErrorCount": stats["logicalErrorCount"],
        "defectEventCount": stats["defectEventCount"],
    }
    decoder_report = {
        "schemaVersion": f"{SCHEMA_PREFIX}.decoder-report.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "decoder": decoder,
        "implementationStatus": implementation_status,
        "sampledSyndromeEvents": len(events),
        "validatedLogicalErrorRate": stats["logicalErrorRate"],
        "logicalErrorCount": stats["logicalErrorCount"],
        "measuredLatencyNs": stats["decoderLatencyMaxNs"],
        "decoderLatencyMeanNs": stats["decoderLatencyMeanNs"],
        "decoderLatencyP95Ns": stats["decoderLatencyP95Ns"],
        "decoderLatencyUncertaintyNs": stats["decoderLatencyUncertaintyNs"],
        "fieldCoverage": stats["fieldCoverage"],
    }
    _write_json(Path(noise_dataset_manifest_out), manifest)
    _write_json(Path(decoder_report_out), decoder_report)
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.fault-tolerance-ingest.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "artifactRefs": {
            "decoderReport": str(decoder_report_out),
            "noiseDatasetManifest": str(noise_dataset_manifest_out),
            "dataset": str(dataset),
        },
        "noiseDatasetManifest": manifest,
        "decoderReport": decoder_report,
        "summary": {
            "recordCount": len(events),
            "invalidRecordCount": invalid_count,
            "logicalErrorCount": stats["logicalErrorCount"],
            "validatedLogicalErrorRate": stats["logicalErrorRate"],
            "decoderLatencyMaxNs": stats["decoderLatencyMaxNs"],
        },
        "blockers": _ingest_blockers(events, invalid_count, stats),
    }


def generate_fault_tolerance_audit(
    blueprint: Blueprint,
    *,
    threshold_report_path: str | Path | None = "reports/node-alpha/qc-path/threshold-sweep.json",
    decoder_report_path: str | Path | None = "reports/node-alpha/qc-path/decoder-report.json",
    noise_dataset_manifest_path: str | Path | None = "reports/node-alpha/qc-path/syndrome-noise-dataset.json",
    hardware_audit_path: str | Path | None = "reports/node-alpha/qc-path/hardware-audit.json",
    target_logical_error_rate: float = 1e-6,
    max_decoder_latency_ns: float = 1000.0,
    min_sampled_syndrome_events: int = 10000,
) -> dict[str, Any]:
    threshold = _read_json(threshold_report_path)
    decoder = _read_json(decoder_report_path)
    dataset = _dataset_report(_read_json(noise_dataset_manifest_path))
    hardware = _read_json(hardware_audit_path)
    threshold_report = _threshold_report(threshold, target_logical_error_rate)
    decoder_report = _decoder_report(decoder, max_decoder_latency_ns, target_logical_error_rate)
    hardware_ready = bool(hardware and hardware.get("readinessFlags", {}).get("hardware_ready"))
    flags = {
        "below_threshold_evidence": threshold_report["belowThresholdEvidence"],
        "logical_error_target_met": threshold_report["logicalErrorTargetMet"] and decoder_report["logicalErrorTargetMet"],
        "decoder_implemented": decoder_report["implemented"],
        "decoder_latency_pass": decoder_report["latencyPass"],
        "noise_dataset_verified": dataset["verified"],
        "sampled_syndrome_count_sufficient": dataset["recordCount"] >= min_sampled_syndrome_events,
        "hardware_calibrated_noise_available": hardware_ready,
    }
    flags["fault_tolerance_ready"] = all(flags.values())
    blockers = _blockers(
        flags=flags,
        threshold=threshold_report,
        decoder=decoder_report,
        dataset=dataset,
        min_sampled_syndrome_events=min_sampled_syndrome_events,
    )
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.fault-tolerance-audit.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "artifactInputs": {
            "thresholdReport": str(threshold_report_path) if threshold_report_path else None,
            "decoderReport": str(decoder_report_path) if decoder_report_path else None,
            "noiseDatasetManifest": str(noise_dataset_manifest_path) if noise_dataset_manifest_path else None,
            "hardwareAudit": str(hardware_audit_path) if hardware_audit_path else None,
        },
        "targets": {
            "targetLogicalErrorRate": target_logical_error_rate,
            "maxDecoderLatencyNs": max_decoder_latency_ns,
            "minSampledSyndromeEvents": min_sampled_syndrome_events,
        },
        "readinessFlags": flags,
        "thresholdEvidence": threshold_report,
        "decoderEvidence": decoder_report,
        "noiseDataset": dataset,
        "hardwareEvidence": {
            "present": bool(hardware),
            "hardwareReady": hardware_ready,
        },
        "blockers": blockers,
        "nextArtifacts": [
            "reports/node-alpha/qc-path/threshold-sweep.json",
            "reports/node-alpha/qc-path/decoder-report.json",
            "reports/node-alpha/qc-path/syndrome-noise-dataset.json",
            "reports/node-alpha/qc-path/fault-tolerance-audit.json",
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
        raise FileNotFoundError(f"Syndrome-noise dataset does not exist: {path}")
    invalid = 0
    records: list[dict[str, Any]] = []
    if path.suffix == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("events", raw.get("syndromeEvents", []))
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


def _syndrome_stats(events: list[dict[str, Any]]) -> dict[str, Any]:
    logical_errors = [event for event in events if _logical_error(event)]
    latency_values = [_float_value(event, ("decoderLatencyNs", "latencyNs", "measuredLatencyNs")) for event in events]
    latency_values = [value for value in latency_values if value is not None]
    return {
        "logicalErrorCount": len(logical_errors),
        "logicalErrorRate": len(logical_errors) / len(events) if events else 1.0,
        "defectEventCount": sum(_defect_count(event) for event in events),
        "decoderLatencyMeanNs": sum(latency_values) / len(latency_values) if latency_values else 1e18,
        "decoderLatencyP95Ns": _percentile(latency_values, 0.95) if latency_values else 1e18,
        "decoderLatencyMaxNs": max(latency_values) if latency_values else 1e18,
        "decoderLatencyUncertaintyNs": _standard_error(latency_values) if latency_values else 1e18,
        "fieldCoverage": {
            "logicalErrorRecords": sum(1 for event in events if _has_any(event, ("logicalError", "logical_error", "decodedLogicalError", "failure"))),
            "decoderLatencyRecords": len(latency_values),
            "defectRecords": sum(1 for event in events if "defects" in event or "syndrome" in event),
        },
    }


def _logical_error(event: dict[str, Any]) -> bool:
    for key in ("logicalError", "logical_error", "decodedLogicalError", "failure"):
        if key in event:
            return bool(event[key])
    status = str(event.get("decoderStatus") or event.get("status") or "").strip().lower()
    return status in {"logical_error", "failed", "failure"}


def _defect_count(event: dict[str, Any]) -> int:
    for key in ("defects", "syndrome"):
        value = event.get(key)
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            return len(value)
    return 0


def _float_value(event: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key not in event:
            continue
        try:
            return float(event[key])
        except (TypeError, ValueError):
            return None
    return None


def _has_any(event: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(key in event for key in keys)


def _standard_error(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0 if values else 1e18
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
        blockers.append("fault_tolerance_ingest: dataset contains no valid syndrome records.")
    if invalid_count:
        blockers.append(f"fault_tolerance_ingest: {invalid_count} invalid records were skipped.")
    if stats["fieldCoverage"]["logicalErrorRecords"] == 0:
        blockers.append("fault_tolerance_ingest: no records include logical-error labels.")
    if stats["fieldCoverage"]["decoderLatencyRecords"] == 0:
        blockers.append("fault_tolerance_ingest: no records include decoder latency.")
    return blockers


def _threshold_report(raw: dict[str, Any], target_logical_error_rate: float) -> dict[str, Any]:
    champion = raw.get("champion") if raw else None
    accepted = raw.get("acceptedCandidates", []) if raw else []
    logical_error = float(champion.get("estimatedLogicalErrorRatePerCycle", 1.0)) if isinstance(champion, dict) else 1.0
    below_threshold = bool(raw and raw.get("status") == "below_threshold_candidate_found" and accepted)
    return {
        "present": bool(raw),
        "status": raw.get("status") if raw else "missing",
        "belowThresholdEvidence": below_threshold,
        "acceptedCandidateCount": len(accepted) if isinstance(accepted, list) else 0,
        "championLogicalErrorRate": logical_error,
        "logicalErrorTargetMet": logical_error <= target_logical_error_rate,
        "decoderInterfaceStatus": raw.get("decoderInterface", {}).get("status") if raw else None,
    }


def _decoder_report(raw: dict[str, Any], max_latency_ns: float, target_logical_error_rate: float) -> dict[str, Any]:
    status = str(raw.get("implementationStatus") or raw.get("status") or "").strip().lower()
    latency = float(raw.get("measuredLatencyNs", 1e18)) if raw else 1e18
    logical_error = float(raw.get("validatedLogicalErrorRate", 1.0)) if raw else 1.0
    sampled_events = int(raw.get("sampledSyndromeEvents", 0)) if raw else 0
    implemented = status in IMPLEMENTED_DECODER_STATUSES
    return {
        "present": bool(raw),
        "decoder": raw.get("decoder") or raw.get("name") if raw else None,
        "implementationStatus": status or "missing",
        "implemented": implemented,
        "sampledSyndromeEvents": sampled_events,
        "validatedLogicalErrorRate": logical_error,
        "logicalErrorTargetMet": logical_error <= target_logical_error_rate,
        "measuredLatencyNs": latency if raw else None,
        "latencyPass": latency <= max_latency_ns,
    }


def _dataset_report(dataset: dict[str, Any]) -> dict[str, Any]:
    path = dataset.get("path") if dataset else None
    expected_hash = dataset.get("sha256") if dataset else None
    exists = bool(path and Path(path).is_file())
    actual_hash = _sha256(path) if exists else None
    record_count = int(dataset.get("recordCount", 0)) if dataset else 0
    return {
        "present": bool(dataset),
        "path": str(path) if path else None,
        "sha256": expected_hash,
        "actualSha256": actual_hash,
        "recordCount": record_count,
        "verified": bool(exists and expected_hash and actual_hash == expected_hash),
    }


def _sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _blockers(
    *,
    flags: dict[str, bool],
    threshold: dict[str, Any],
    decoder: dict[str, Any],
    dataset: dict[str, Any],
    min_sampled_syndrome_events: int,
) -> list[str]:
    blockers: list[str] = []
    if not flags["below_threshold_evidence"]:
        blockers.append("fault_tolerance: no below-threshold threshold-sweep evidence is attached.")
    if not flags["logical_error_target_met"]:
        blockers.append("fault_tolerance: validated/champion logical error rate does not meet target.")
    if not flags["decoder_implemented"]:
        blockers.append(f"fault_tolerance: decoder implementation status is {decoder['implementationStatus']}.")
    if not flags["decoder_latency_pass"]:
        blockers.append(f"fault_tolerance: decoder latency {decoder['measuredLatencyNs']} ns exceeds target.")
    if not flags["noise_dataset_verified"]:
        blockers.append("fault_tolerance: sampled syndrome-noise dataset is missing or SHA-256 verification failed.")
    if not flags["sampled_syndrome_count_sufficient"]:
        blockers.append(
            f"fault_tolerance: syndrome sample count {dataset['recordCount']} below {min_sampled_syndrome_events}."
        )
    if not flags["hardware_calibrated_noise_available"]:
        blockers.append("fault_tolerance: hardware-audit is not hardware_ready, so calibrated noise distributions are missing.")
    return blockers
