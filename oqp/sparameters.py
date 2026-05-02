"""S-parameter and compact-model audits for OQP-HRM core devices."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .blueprint import Blueprint


SCHEMA_PREFIX = "open-quantum"
REQUIRED_CORE_DEVICES = ("coupler", "mzi", "phase-shifter", "truth-switch")
CALIBRATED_STATUSES = {"foundry_calibrated", "wafer_calibrated", "measured", "validated"}


def generate_sparameter_audit(
    blueprint: Blueprint,
    *,
    model_manifest_path: str | Path | None = "reports/node-alpha/qc-path/sparameter-models.json",
    min_wavelength_nm: float = 1520.0,
    max_wavelength_nm: float = 1580.0,
    max_insertion_loss_db: float = 1.0,
    max_reflection_ratio: float = 0.05,
    max_crosstalk_ratio: float = 0.05,
    max_passivity_singular_value: float = 1.0001,
    max_reciprocity_error: float = 1e-3,
    max_energy_balance_error: float = 0.05,
) -> dict[str, Any]:
    manifest = _read_json(model_manifest_path)
    models = _models(manifest)
    device_rows = [
        _device_row(
            device,
            models.get(device, {}),
            min_wavelength_nm=min_wavelength_nm,
            max_wavelength_nm=max_wavelength_nm,
            max_insertion_loss_db=max_insertion_loss_db,
            max_reflection_ratio=max_reflection_ratio,
            max_crosstalk_ratio=max_crosstalk_ratio,
            max_passivity_singular_value=max_passivity_singular_value,
            max_reciprocity_error=max_reciprocity_error,
            max_energy_balance_error=max_energy_balance_error,
        )
        for device in REQUIRED_CORE_DEVICES
    ]
    accepted = [row for row in device_rows if row["accepted"]]
    missing = [row["device"] for row in device_rows if row["status"] == "missing_model"]
    hash_failures = [row["device"] for row in device_rows if row["hashVerified"] is False]
    flags = {
        "all_core_sparameters_present": not missing,
        "all_hashes_verified": not hash_failures and not missing,
        "all_core_sparameters_accepted": len(accepted) == len(REQUIRED_CORE_DEVICES),
        "foundry_calibrated_sparameters": len(accepted) == len(REQUIRED_CORE_DEVICES),
        "sparameter_models_ready": len(accepted) == len(REQUIRED_CORE_DEVICES),
    }
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.sparameter-audit.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "modelManifest": str(model_manifest_path) if model_manifest_path else None,
        "targets": {
            "requiredDevices": list(REQUIRED_CORE_DEVICES),
            "wavelengthWindowNm": [min_wavelength_nm, max_wavelength_nm],
            "maxInsertionLossDb": max_insertion_loss_db,
            "maxReflectionRatio": max_reflection_ratio,
            "maxCrosstalkRatio": max_crosstalk_ratio,
            "maxPassivitySingularValue": max_passivity_singular_value,
            "maxReciprocityError": max_reciprocity_error,
            "maxEnergyBalanceError": max_energy_balance_error,
        },
        "readinessFlags": flags,
        "devices": device_rows,
        "summary": {
            "requiredDeviceCount": len(REQUIRED_CORE_DEVICES),
            "acceptedDeviceCount": len(accepted),
            "missingDeviceCount": len(missing),
            "hashFailureCount": len(hash_failures),
        },
        "blockers": [blocker for row in device_rows for blocker in row["blockers"]],
        "nextArtifacts": [
            "reports/node-alpha/qc-path/sparameter-models.json",
            "reports/node-alpha/qc-path/sparameters/coupler.sparam",
            "reports/node-alpha/qc-path/sparameters/mzi.sparam",
            "reports/node-alpha/qc-path/sparameters/phase-shifter.sparam",
            "reports/node-alpha/qc-path/sparameters/truth-switch.sparam",
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


def _models(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = manifest.get("models") or manifest.get("compactModels") or {}
    if not isinstance(raw, dict):
        return {}
    return {_normalize_device(device): model for device, model in raw.items() if isinstance(model, dict)}


def _device_row(
    device: str,
    model: dict[str, Any],
    *,
    min_wavelength_nm: float,
    max_wavelength_nm: float,
    max_insertion_loss_db: float,
    max_reflection_ratio: float,
    max_crosstalk_ratio: float,
    max_passivity_singular_value: float,
    max_reciprocity_error: float,
    max_energy_balance_error: float,
) -> dict[str, Any]:
    if not model:
        return {
            "device": device,
            "status": "missing_model",
            "accepted": False,
            "path": None,
            "hashVerified": False,
            "metrics": {},
            "blockers": [f"{device}: missing foundry-calibrated S-parameter compact model."],
        }
    metrics = model.get("metrics", {})
    path = model.get("path")
    hash_verified = _hash_verified(path, model.get("sha256"))
    wavelength = _wavelength_range(model)
    corners = model.get("processCorners", [])
    calibration_status = str(model.get("calibrationStatus") or model.get("status") or "").strip().lower()
    validation_level = str(model.get("validationLevel") or "").strip().lower()
    insertion = float(metrics.get("insertionLossDb", 1e18))
    reflection = float(metrics.get("reflectionRatio", 1e18))
    crosstalk = float(metrics.get("crosstalkRatio", 1e18))
    passivity = float(metrics.get("passivityMaxSingularValue", 1e18))
    reciprocity = float(metrics.get("reciprocityError", 1e18))
    energy = float(metrics.get("energyBalanceError", 1e18))
    blockers = []
    if not hash_verified:
        blockers.append(f"{device}: model file is missing or SHA-256 verification failed.")
    if not _covers_wavelength(wavelength, min_wavelength_nm, max_wavelength_nm):
        blockers.append(f"{device}: wavelength range {wavelength} does not cover {min_wavelength_nm}-{max_wavelength_nm} nm.")
    if calibration_status not in CALIBRATED_STATUSES:
        blockers.append(f"{device}: calibration status {calibration_status or 'missing'} is not foundry/wafer calibrated.")
    if "sparameter" not in validation_level and "mpb" not in validation_level and "3d" not in validation_level:
        blockers.append(f"{device}: validation level {validation_level or 'missing'} lacks S-parameter/MPB/3D evidence.")
    if not isinstance(corners, list) or not corners:
        blockers.append(f"{device}: no process corners are attached.")
    if insertion > max_insertion_loss_db:
        blockers.append(f"{device}: insertion loss {insertion:.6g} dB exceeds {max_insertion_loss_db} dB.")
    if reflection > max_reflection_ratio:
        blockers.append(f"{device}: reflection ratio {reflection:.6g} exceeds {max_reflection_ratio}.")
    if crosstalk > max_crosstalk_ratio:
        blockers.append(f"{device}: crosstalk ratio {crosstalk:.6g} exceeds {max_crosstalk_ratio}.")
    if passivity > max_passivity_singular_value:
        blockers.append(f"{device}: passivity singular value {passivity:.6g} exceeds {max_passivity_singular_value}.")
    if reciprocity > max_reciprocity_error:
        blockers.append(f"{device}: reciprocity error {reciprocity:.6g} exceeds {max_reciprocity_error}.")
    if energy > max_energy_balance_error:
        blockers.append(f"{device}: energy balance error {energy:.6g} exceeds {max_energy_balance_error}.")
    return {
        "device": device,
        "status": "accepted_sparameter_model" if not blockers else "sparameter_gap",
        "accepted": not blockers,
        "path": str(path) if path else None,
        "sha256": model.get("sha256"),
        "hashVerified": hash_verified,
        "calibrationStatus": calibration_status or None,
        "validationLevel": validation_level or None,
        "processCorners": corners if isinstance(corners, list) else [],
        "wavelengthRangeNm": wavelength,
        "portCount": model.get("portCount"),
        "metrics": {
            "insertionLossDb": insertion,
            "reflectionRatio": reflection,
            "crosstalkRatio": crosstalk,
            "passivityMaxSingularValue": passivity,
            "reciprocityError": reciprocity,
            "energyBalanceError": energy,
        },
        "blockers": blockers,
    }


def _hash_verified(path: str | Path | None, expected_hash: str | None) -> bool:
    if not path or not expected_hash:
        return False
    target = Path(path)
    if not target.is_file():
        return False
    digest = sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected_hash


def _wavelength_range(model: dict[str, Any]) -> list[float]:
    value = model.get("wavelengthRangeNm") or model.get("wavelengthNm")
    if isinstance(value, list) and len(value) >= 2:
        return [float(value[0]), float(value[1])]
    if isinstance(value, (int, float)):
        return [float(value), float(value)]
    return []


def _covers_wavelength(value: list[float], low: float, high: float) -> bool:
    return len(value) == 2 and value[0] <= low and value[1] >= high


def _normalize_device(device: str) -> str:
    lowered = device.strip().lower().replace("_", "-")
    if lowered in {"directional-coupler", "dc"}:
        return "coupler"
    if lowered in {"phase", "phase-shifter"}:
        return "phase-shifter"
    if lowered in {"truth-switch", "truthswitch"}:
        return "truth-switch"
    return lowered
