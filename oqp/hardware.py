"""Hardware, calibration, and feed-forward audits for OQP-HRM."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .blueprint import Blueprint


SCHEMA_PREFIX = "open-quantum"
REQUIRED_CALIBRATIONS = (
    "phase",
    "loss",
    "crosstalk",
    "detector_timing",
    "source_indistinguishability",
    "switch_latency",
)


def ingest_hardware_dataset(
    blueprint: Blueprint,
    *,
    dataset_path: str | Path,
    source_out: str | Path = "reports/node-alpha/qc-path/source-hardware.json",
    detector_out: str | Path = "reports/node-alpha/qc-path/detector-hardware.json",
    packaging_out: str | Path = "reports/node-alpha/qc-path/packaging-plan.json",
    control_out: str | Path = "reports/node-alpha/qc-path/control-hardware.json",
    calibration_out: str | Path = "reports/node-alpha/qc-path/calibration-report.json",
    feed_forward_out: str | Path = "reports/node-alpha/qc-path/feed-forward-report.json",
) -> dict[str, Any]:
    dataset = Path(dataset_path)
    records, invalid_count = _read_event_records(dataset)
    groups = _group_hardware_records(records)
    dataset_evidence = {
        "path": str(dataset),
        "sha256": _sha256(dataset),
        "recordCount": len(records),
        "invalidRecordCount": invalid_count,
        "format": "json" if dataset.suffix == ".json" else "jsonl",
        "categoryRecordCount": {key: len(value) for key, value in groups.items()},
    }
    source = _source_ingest_report(blueprint, groups["source"], dataset_evidence)
    detector = _detector_ingest_report(blueprint, groups["detector"], dataset_evidence)
    packaging = _packaging_ingest_report(blueprint, groups["packaging"], dataset_evidence)
    control = _control_ingest_report(blueprint, groups["control"], dataset_evidence)
    calibration = _calibration_ingest_report(groups["calibration"], dataset_evidence)
    feed_forward = _feed_forward_ingest_report(groups["feed_forward"], dataset_evidence)
    outputs = {
        "sourceHardware": source_out,
        "detectorHardware": detector_out,
        "packagingPlan": packaging_out,
        "controlHardware": control_out,
        "calibrationReport": calibration_out,
        "feedForwardReport": feed_forward_out,
    }
    for path, report in [
        (source_out, source),
        (detector_out, detector),
        (packaging_out, packaging),
        (control_out, control),
        (calibration_out, calibration),
        (feed_forward_out, feed_forward),
    ]:
        _write_json(Path(path), report)
    blockers = _hardware_ingest_blockers(records, invalid_count, groups)
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.hardware-ingest.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "dataset": dataset_evidence,
        "artifactRefs": {key: str(value) for key, value in outputs.items()} | {"dataset": str(dataset)},
        "summary": {
            "recordCount": len(records),
            "invalidRecordCount": invalid_count,
            "sourceRecordCount": len(groups["source"]),
            "detectorRecordCount": len(groups["detector"]),
            "packagingRecordCount": len(groups["packaging"]),
            "controlRecordCount": len(groups["control"]),
            "calibrationRecordCount": len(groups["calibration"]),
            "feedForwardRecordCount": len(groups["feed_forward"]),
            "completedCalibrationCount": len(calibration["completedCalibrations"]),
            "hardwareInLoopShots": feed_forward["hardwareInLoopShots"],
        },
        "reports": {
            "sourceHardware": source,
            "detectorHardware": detector,
            "packaging": packaging,
            "controlHardware": control,
            "calibration": calibration,
            "feedForward": feed_forward,
        },
        "blockers": blockers,
        "nextCommand": "oqp hardware-audit <blueprint> --out reports/node-alpha/qc-path/hardware-audit.json",
    }


def generate_hardware_audit(
    blueprint: Blueprint,
    *,
    source_report_path: str | Path | None = "reports/node-alpha/qc-path/source-hardware.json",
    detector_report_path: str | Path | None = "reports/node-alpha/qc-path/detector-hardware.json",
    packaging_report_path: str | Path | None = "reports/node-alpha/qc-path/packaging-plan.json",
    control_report_path: str | Path | None = "reports/node-alpha/qc-path/control-hardware.json",
    calibration_report_path: str | Path | None = "reports/node-alpha/qc-path/calibration-report.json",
    feed_forward_report_path: str | Path | None = "reports/node-alpha/qc-path/feed-forward-report.json",
) -> dict[str, Any]:
    source = _source_report(blueprint, _read_json(source_report_path))
    detector = _detector_report(blueprint, _read_json(detector_report_path))
    packaging = _packaging_report(blueprint, _read_json(packaging_report_path))
    control = _control_report(blueprint, _read_json(control_report_path))
    calibration = _calibration_report(_read_json(calibration_report_path))
    feed_forward = _feed_forward_report(_read_json(feed_forward_report_path))
    flags = {
        "source_hardware_ready": source["ready"],
        "detector_hardware_ready": detector["ready"],
        "packaging_ready": packaging["ready"],
        "control_hardware_ready": control["ready"],
        "automatic_calibration_ready": calibration["ready"],
        "feed_forward_verified": feed_forward["ready"],
    }
    flags["hardware_ready"] = all(flags.values())
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.hardware-audit.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "artifactInputs": {
            "sourceHardware": str(source_report_path) if source_report_path else None,
            "detectorHardware": str(detector_report_path) if detector_report_path else None,
            "packagingPlan": str(packaging_report_path) if packaging_report_path else None,
            "controlHardware": str(control_report_path) if control_report_path else None,
            "calibrationReport": str(calibration_report_path) if calibration_report_path else None,
            "feedForwardReport": str(feed_forward_report_path) if feed_forward_report_path else None,
        },
        "readinessFlags": flags,
        "sourceHardware": source,
        "detectorHardware": detector,
        "packaging": packaging,
        "controlHardware": control,
        "calibration": calibration,
        "feedForward": feed_forward,
        "blockers": source["blockers"]
        + detector["blockers"]
        + packaging["blockers"]
        + control["blockers"]
        + calibration["blockers"]
        + feed_forward["blockers"],
        "nextArtifacts": [
            "reports/node-alpha/qc-path/source-hardware.json",
            "reports/node-alpha/qc-path/detector-hardware.json",
            "reports/node-alpha/qc-path/packaging-plan.json",
            "reports/node-alpha/qc-path/control-hardware.json",
            "reports/node-alpha/qc-path/calibration-report.json",
            "reports/node-alpha/qc-path/feed-forward-report.json",
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
        raise FileNotFoundError(f"Hardware evidence dataset does not exist: {path}")
    invalid = 0
    records: list[dict[str, Any]] = []
    if path.suffix == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("events", raw.get("hardwareEvents", []))
            if not items and _looks_like_hardware_record(raw):
                items = [raw]
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


def _group_hardware_records(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = {
        "source": [],
        "detector": [],
        "packaging": [],
        "control": [],
        "calibration": [],
        "feed_forward": [],
    }
    for record in records:
        category = _hardware_category(record)
        if category in groups:
            groups[category].append(record)
    return groups


def _hardware_category(record: dict[str, Any]) -> str | None:
    raw = next(
        (record.get(key) for key in ("category", "kind", "type", "artifact", "recordType", "component") if key in record),
        None,
    )
    category = _normalize_name(raw)
    aliases = {
        "source": "source",
        "source_hardware": "source",
        "single_photon_source": "source",
        "photon_source": "source",
        "detector": "detector",
        "detector_hardware": "detector",
        "photon_detector": "detector",
        "packaging": "packaging",
        "package": "packaging",
        "packaging_plan": "packaging",
        "control": "control",
        "control_hardware": "control",
        "electronics": "control",
        "calibration": "calibration",
        "calibration_report": "calibration",
        "automatic_calibration": "calibration",
        "auto_calibration": "calibration",
        "feed_forward": "feed_forward",
        "feedforward": "feed_forward",
        "feed_forward_report": "feed_forward",
        "feed_forward_operation": "feed_forward",
    }
    if category in aliases:
        return aliases[category]
    if _has_any(record, ("sourceCount", "brightness", "indistinguishability", "multiphotonProbability")):
        return "source"
    if _has_any(record, ("detectorCount", "efficiency", "darkCountHz", "timingJitterPs", "photonNumberResolving")):
        return "detector"
    if _has_any(record, ("fiberPlanLocked", "edgeCouplerPlanLocked", "probeCardLocked", "packageDrawingReleased")):
        return "packaging"
    if _has_any(record, ("timingFabric", "tdcChannels", "phaseDriverChannels", "dacResolutionBits", "clockJitterPs")):
        return "control"
    if _has_any(record, ("completedCalibrations", "calibrationType", "calibration")):
        return "calibration"
    if _has_any(record, ("measuredLatencyNs", "feedForwardLatencyNs", "hardwareInLoopShots", "hardwareInLoopShot")):
        return "feed_forward"
    return None


def _looks_like_hardware_record(record: dict[str, Any]) -> bool:
    return _hardware_category(record) is not None


def _source_ingest_report(blueprint: Blueprint, records: list[dict[str, Any]], evidence: dict[str, Any]) -> dict[str, Any]:
    required = max(1, blueprint.spatial_model.waveguide_count)
    count = _count_value(records, ("sourceCount", "count"), ("sourceId", "id", "channel"))
    brightness = _metric_value(records, ("brightness", "singlePhotonBrightness"), default=0.0, mode="min")
    indistinguishability = _metric_value(records, ("indistinguishability", "hongOuMandelVisibility"), default=0.0, mode="min")
    multiphoton = _metric_value(records, ("multiphotonProbability", "g2", "g2Zero"), default=1.0, mode="max")
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.source-hardware.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "status": _records_status(records, "measured"),
        "sourceCount": count,
        "requiredSourceCount": required,
        "brightness": brightness,
        "indistinguishability": indistinguishability,
        "multiphotonProbability": multiphoton,
        "datasetEvidence": evidence,
    }


def _detector_ingest_report(blueprint: Blueprint, records: list[dict[str, Any]], evidence: dict[str, Any]) -> dict[str, Any]:
    required = blueprint.spatial_model.waveguide_count
    count = _count_value(records, ("detectorCount", "count"), ("detectorId", "id", "channel"))
    efficiency = _metric_value(records, ("efficiency", "detectionEfficiency"), default=0.0, mode="min")
    dark_count = _metric_value(records, ("darkCountHz", "darkRateHz"), default=1e18, mode="max")
    jitter = _metric_value(records, ("timingJitterPs", "jitterPs"), default=1e18, mode="max")
    pnr = _all_bool(records, "photonNumberResolving")
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.detector-hardware.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "status": _records_status(records, "measured"),
        "detectorCount": count,
        "requiredDetectorCount": required,
        "efficiency": efficiency,
        "darkCountHz": dark_count,
        "timingJitterPs": jitter,
        "photonNumberResolving": pnr,
        "datasetEvidence": evidence,
    }


def _packaging_ingest_report(blueprint: Blueprint, records: list[dict[str, Any]], evidence: dict[str, Any]) -> dict[str, Any]:
    required_ports = blueprint.spatial_model.waveguide_count * 2
    required_pads = max(blueprint.spatial_model.interferometer_count, 1)
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.packaging-plan.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "status": _records_status(records, "locked"),
        "fiberPlanLocked": _all_bool(records, "fiberPlanLocked"),
        "edgeCouplerPlanLocked": _all_bool(records, "edgeCouplerPlanLocked"),
        "probeCardLocked": _all_bool(records, "probeCardLocked"),
        "thermalPlanLocked": _all_bool(records, "thermalPlanLocked"),
        "packageDrawingReleased": _all_bool(records, "packageDrawingReleased"),
        "opticalPortCount": _count_value(records, ("opticalPortCount",), ("opticalPortId", "portId")),
        "requiredOpticalPortCount": required_ports,
        "electricalPadCount": _count_value(records, ("electricalPadCount",), ("electricalPadId", "padId")),
        "requiredElectricalPadCount": required_pads,
        "datasetEvidence": evidence,
    }


def _control_ingest_report(blueprint: Blueprint, records: list[dict[str, Any]], evidence: dict[str, Any]) -> dict[str, Any]:
    spatial = blueprint.spatial_model
    fabric = next((str(record.get("timingFabric")) for record in records if record.get("timingFabric")), "missing")
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.control-hardware.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "status": _records_status(records, "measured"),
        "timingFabric": fabric,
        "tdcChannels": _count_value(records, ("tdcChannels",), ("tdcChannelId",)),
        "requiredTdcChannels": spatial.waveguide_count,
        "detectorReadoutChannels": _count_value(records, ("detectorReadoutChannels",), ("detectorReadoutChannelId",)),
        "requiredDetectorReadoutChannels": spatial.waveguide_count,
        "phaseDriverChannels": _count_value(records, ("phaseDriverChannels",), ("phaseDriverChannelId",)),
        "requiredPhaseDriverChannels": spatial.interferometer_count,
        "switchDriverChannels": _count_value(records, ("switchDriverChannels",), ("switchDriverChannelId",)),
        "requiredSwitchDriverChannels": max(1, spatial.interferometer_count // 2),
        "dacResolutionBits": int(_metric_value(records, ("dacResolutionBits", "dacBits"), default=0.0, mode="min")),
        "clockJitterPs": _metric_value(records, ("clockJitterPs",), default=1e18, mode="max"),
        "datasetEvidence": evidence,
    }


def _calibration_ingest_report(records: list[dict[str, Any]], evidence: dict[str, Any]) -> dict[str, Any]:
    completed = _completed_calibrations(records)
    completed_map = {name: name in completed for name in REQUIRED_CALIBRATIONS}
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.calibration-report.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": _records_status(records, "complete"),
        "completedCalibrations": completed_map,
        "completedCalibrationNames": sorted(completed),
        "requiredCalibrations": list(REQUIRED_CALIBRATIONS),
        "datasetEvidence": evidence,
    }


def _feed_forward_ingest_report(records: list[dict[str, Any]], evidence: dict[str, Any]) -> dict[str, Any]:
    latency = _metric_value(records, ("measuredLatencyNs", "feedForwardLatencyNs", "latencyNs"), default=1e18, mode="max")
    jitter = _metric_value(records, ("measuredJitterPs", "jitterPs"), default=1e18, mode="max")
    explicit_shots = _count_value(records, ("hardwareInLoopShots", "hilShots"), ("shotId", "shot"))
    inferred_shots = sum(1 for record in records if record.get("hardwareInLoopShot") is True)
    shots = max(explicit_shots, inferred_shots)
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.feed-forward-report.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "verified" if records else "ingest_missing",
        "measuredLatencyNs": latency,
        "measuredJitterPs": jitter,
        "hardwareInLoopShots": shots,
        "datasetEvidence": evidence,
    }


def _source_report(blueprint: Blueprint, raw: dict[str, Any]) -> dict[str, Any]:
    required_count = max(1, blueprint.spatial_model.waveguide_count)
    count = int(raw.get("sourceCount", raw.get("count", 0))) if raw else 0
    brightness = float(raw.get("brightness", 0.0)) if raw else 0.0
    indistinguishability = float(raw.get("indistinguishability", 0.0)) if raw else 0.0
    multiphoton = float(raw.get("multiphotonProbability", 1.0)) if raw else 1.0
    status_ok = _status_ok(raw, {"integrated", "validated", "measured"})
    blockers = []
    if count < required_count:
        blockers.append(f"source_hardware: {count} sources available, {required_count} required.")
    if brightness < 0.8:
        blockers.append(f"source_hardware: brightness {brightness:.6g} below 0.8 target.")
    if indistinguishability < 0.99:
        blockers.append(f"source_hardware: indistinguishability {indistinguishability:.6g} below 0.99 target.")
    if multiphoton > 0.001:
        blockers.append(f"source_hardware: multiphoton probability {multiphoton:.6g} above 0.001 target.")
    if not status_ok:
        blockers.append("source_hardware: no integrated/measured source hardware report.")
    return {
        "present": bool(raw),
        "ready": not blockers,
        "requiredSourceCount": required_count,
        "sourceCount": count,
        "brightness": brightness,
        "indistinguishability": indistinguishability,
        "multiphotonProbability": multiphoton,
        "status": raw.get("status") if raw else "missing",
        "blockers": blockers,
    }


def _detector_report(blueprint: Blueprint, raw: dict[str, Any]) -> dict[str, Any]:
    required_count = blueprint.spatial_model.waveguide_count
    count = int(raw.get("detectorCount", raw.get("count", 0))) if raw else 0
    efficiency = float(raw.get("efficiency", 0.0)) if raw else 0.0
    dark_count = float(raw.get("darkCountHz", 1e18)) if raw else 1e18
    jitter = float(raw.get("timingJitterPs", 1e18)) if raw else 1e18
    pnr = bool(raw.get("photonNumberResolving", False)) if raw else False
    status_ok = _status_ok(raw, {"integrated", "validated", "measured"})
    blockers = []
    if count < required_count:
        blockers.append(f"detector_hardware: {count} detectors available, {required_count} required.")
    if efficiency < 0.95:
        blockers.append(f"detector_hardware: efficiency {efficiency:.6g} below 0.95 target.")
    if dark_count > 10:
        blockers.append(f"detector_hardware: dark count {dark_count:.6g} Hz above 10 Hz target.")
    if jitter > 50:
        blockers.append(f"detector_hardware: timing jitter {jitter:.6g} ps above 50 ps target.")
    if not pnr:
        blockers.append("detector_hardware: photon-number resolving detector path is not verified.")
    if not status_ok:
        blockers.append("detector_hardware: no integrated/measured detector hardware report.")
    return {
        "present": bool(raw),
        "ready": not blockers,
        "requiredDetectorCount": required_count,
        "detectorCount": count,
        "efficiency": efficiency,
        "darkCountHz": dark_count,
        "timingJitterPs": jitter,
        "photonNumberResolving": pnr,
        "status": raw.get("status") if raw else "missing",
        "blockers": blockers,
    }


def _packaging_report(blueprint: Blueprint, raw: dict[str, Any]) -> dict[str, Any]:
    required_ports = blueprint.spatial_model.waveguide_count * 2
    optical_ports = int(raw.get("opticalPortCount", 0)) if raw else 0
    electrical_pads = int(raw.get("electricalPadCount", 0)) if raw else 0
    required_pads = max(blueprint.spatial_model.interferometer_count, 1)
    blockers = []
    for key in ("fiberPlanLocked", "edgeCouplerPlanLocked", "probeCardLocked", "thermalPlanLocked", "packageDrawingReleased"):
        if raw.get(key) is not True:
            blockers.append(f"packaging: {key} is not true.")
    if optical_ports < required_ports:
        blockers.append(f"packaging: {optical_ports} optical ports mapped, {required_ports} required.")
    if electrical_pads < required_pads:
        blockers.append(f"packaging: {electrical_pads} electrical pads mapped, at least {required_pads} required.")
    return {
        "present": bool(raw),
        "ready": not blockers,
        "requiredOpticalPortCount": required_ports,
        "opticalPortCount": optical_ports,
        "requiredElectricalPadCount": required_pads,
        "electricalPadCount": electrical_pads,
        "status": raw.get("status") if raw else "missing",
        "blockers": blockers,
    }


def _control_report(blueprint: Blueprint, raw: dict[str, Any]) -> dict[str, Any]:
    spatial = blueprint.spatial_model
    tdc = int(raw.get("tdcChannels", 0)) if raw else 0
    detector_readout = int(raw.get("detectorReadoutChannels", 0)) if raw else 0
    phase_drivers = int(raw.get("phaseDriverChannels", 0)) if raw else 0
    switch_drivers = int(raw.get("switchDriverChannels", 0)) if raw else 0
    dac_bits = int(raw.get("dacResolutionBits", 0)) if raw else 0
    jitter = float(raw.get("clockJitterPs", 1e18)) if raw else 1e18
    blockers = []
    if str(raw.get("timingFabric", "")).lower() not in {"fpga", "asic"}:
        blockers.append("control_hardware: FPGA/ASIC timing fabric is not selected.")
    if tdc < spatial.waveguide_count:
        blockers.append(f"control_hardware: {tdc} TDC channels, {spatial.waveguide_count} required.")
    if detector_readout < spatial.waveguide_count:
        blockers.append(f"control_hardware: {detector_readout} detector readout channels, {spatial.waveguide_count} required.")
    if phase_drivers < spatial.interferometer_count:
        blockers.append(f"control_hardware: {phase_drivers} phase drivers, {spatial.interferometer_count} required.")
    if switch_drivers < max(1, spatial.interferometer_count // 2):
        blockers.append("control_hardware: switch driver channel count is insufficient.")
    if dac_bits < 14:
        blockers.append(f"control_hardware: DAC resolution {dac_bits} bits below 14-bit target.")
    if jitter > 10:
        blockers.append(f"control_hardware: clock jitter {jitter:.6g} ps above 10 ps target.")
    return {
        "present": bool(raw),
        "ready": not blockers,
        "tdcChannels": tdc,
        "detectorReadoutChannels": detector_readout,
        "phaseDriverChannels": phase_drivers,
        "switchDriverChannels": switch_drivers,
        "dacResolutionBits": dac_bits,
        "clockJitterPs": jitter,
        "status": raw.get("status") if raw else "missing",
        "blockers": blockers,
    }


def _calibration_report(raw: dict[str, Any]) -> dict[str, Any]:
    completed = raw.get("completedCalibrations", []) if raw else []
    if isinstance(completed, dict):
        completed_set = {key for key, value in completed.items() if value is True}
    else:
        completed_set = {str(item) for item in completed if item}
    missing = [name for name in REQUIRED_CALIBRATIONS if name not in completed_set]
    blockers = [f"calibration: missing {name} calibration." for name in missing]
    if not _status_ok(raw, {"complete", "validated", "measured"}):
        blockers.append("calibration: no complete automatic calibration report.")
    return {
        "present": bool(raw),
        "ready": not blockers,
        "requiredCalibrations": list(REQUIRED_CALIBRATIONS),
        "completedCalibrations": sorted(completed_set),
        "missingCalibrations": missing,
        "status": raw.get("status") if raw else "missing",
        "blockers": blockers,
    }


def _feed_forward_report(raw: dict[str, Any]) -> dict[str, Any]:
    latency = float(raw.get("measuredLatencyNs", 1e18)) if raw else 1e18
    jitter = float(raw.get("measuredJitterPs", 1e18)) if raw else 1e18
    hil_shots = int(raw.get("hardwareInLoopShots", 0)) if raw else 0
    blockers = []
    if latency > 10:
        blockers.append(f"feed_forward: measured latency {latency:.6g} ns above 10 ns target.")
    if jitter > 10:
        blockers.append(f"feed_forward: measured jitter {jitter:.6g} ps above 10 ps target.")
    if hil_shots <= 0:
        blockers.append("feed_forward: no hardware-in-the-loop shots recorded.")
    if not _status_ok(raw, {"verified", "validated", "measured"}):
        blockers.append("feed_forward: scheduler/feed-forward operation is not verified.")
    return {
        "present": bool(raw),
        "ready": not blockers,
        "measuredLatencyNs": latency if raw else None,
        "measuredJitterPs": jitter if raw else None,
        "hardwareInLoopShots": hil_shots,
        "status": raw.get("status") if raw else "missing",
        "blockers": blockers,
    }


def _status_ok(raw: dict[str, Any], accepted: set[str]) -> bool:
    if not raw:
        return False
    return str(raw.get("status") or raw.get("integrationStatus") or "").strip().lower().replace("-", "_") in accepted


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _normalize_name(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _has_any(record: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(key in record for key in keys)


def _count_value(records: list[dict[str, Any]], count_keys: tuple[str, ...], id_keys: tuple[str, ...]) -> int:
    explicit: list[int] = []
    ids: set[str] = set()
    for record in records:
        for key in count_keys:
            value = record.get(key)
            try:
                if value is not None:
                    explicit.append(int(value))
                    break
            except (TypeError, ValueError):
                continue
        for key in id_keys:
            value = record.get(key)
            if value is not None:
                ids.add(str(value))
                break
    if explicit:
        return max(explicit)
    if ids:
        return len(ids)
    return len(records)


def _metric_value(records: list[dict[str, Any]], keys: tuple[str, ...], *, default: float, mode: str) -> float:
    values: list[float] = []
    for record in records:
        for key in keys:
            if key not in record:
                continue
            try:
                values.append(float(record[key]))
                break
            except (TypeError, ValueError):
                continue
    if not values:
        return default
    if mode == "min":
        return min(values)
    if mode == "mean":
        return sum(values) / len(values)
    return max(values)


def _all_bool(records: list[dict[str, Any]], key: str) -> bool:
    values = [record[key] for record in records if key in record]
    if not values:
        return False
    return all(bool(value) for value in values)


def _records_status(records: list[dict[str, Any]], default: str) -> str:
    if not records:
        return "ingest_missing"
    statuses = [_normalize_name(record.get("status") or record.get("integrationStatus")) for record in records]
    statuses = [status for status in statuses if status]
    if not statuses:
        return default
    blocking = [status for status in statuses if status not in {"measured", "validated", "verified", "complete", "locked", "integrated"}]
    return blocking[0] if blocking else default


def _completed_calibrations(records: list[dict[str, Any]]) -> set[str]:
    completed: set[str] = set()
    for record in records:
        raw = record.get("completedCalibrations")
        if isinstance(raw, dict):
            completed.update(_normalize_calibration_name(key) for key, value in raw.items() if value is True)
        elif isinstance(raw, list):
            completed.update(_normalize_calibration_name(item) for item in raw if item)
        name = _normalize_calibration_name(
            record.get("calibrationType") or record.get("calibration") or record.get("name")
        )
        if name and _calibration_record_passed(record):
            completed.add(name)
    return {name for name in completed if name in REQUIRED_CALIBRATIONS}


def _normalize_calibration_name(value: Any) -> str:
    name = _normalize_name(value)
    aliases = {
        "detector_timing_calibration": "detector_timing",
        "source_indistinguishability_calibration": "source_indistinguishability",
        "switch_latency_calibration": "switch_latency",
        "feed_forward_latency": "switch_latency",
    }
    return aliases.get(name, name)


def _calibration_record_passed(record: dict[str, Any]) -> bool:
    if "passed" in record:
        return bool(record["passed"])
    if "complete" in record:
        return bool(record["complete"])
    return _normalize_name(record.get("status")) in {"complete", "validated", "measured", "passed"}


def _hardware_ingest_blockers(
    records: list[dict[str, Any]],
    invalid_count: int,
    groups: dict[str, list[dict[str, Any]]],
) -> list[str]:
    blockers: list[str] = []
    if not records:
        blockers.append("hardware_ingest: dataset contains no valid hardware records.")
    if invalid_count:
        blockers.append(f"hardware_ingest: {invalid_count} invalid records were skipped.")
    labels = {
        "source": "source hardware",
        "detector": "detector hardware",
        "packaging": "packaging plan",
        "control": "control hardware",
        "calibration": "automatic calibration",
        "feed_forward": "feed-forward operation",
    }
    for key, label in labels.items():
        if not groups[key]:
            blockers.append(f"hardware_ingest: no {label} records found.")
    return blockers
