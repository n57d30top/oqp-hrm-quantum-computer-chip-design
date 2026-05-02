"""Foundry PDK and signoff-input audits for OQP-HRM."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .blueprint import Blueprint


SCHEMA_PREFIX = "open-quantum"
REQUIRED_LAYER_PURPOSES = ("waveguide", "etch", "metal", "pad", "port", "label", "keepout")
REQUIRED_CORE_MODELS = ("coupler", "mzi", "phase-shifter", "truth-switch")


def generate_pdk_audit(
    blueprint: Blueprint,
    *,
    pdk: str = "generic-si-photonics",
    pdk_manifest: str | Path | None = None,
    gds_audit_path: str | Path | None = "reports/node-alpha/gds-path/gds-audit.json",
) -> dict[str, Any]:
    manifest = _read_json(pdk_manifest)
    gds_audit = _read_json(gds_audit_path)
    layer_map = _layer_map_report(manifest)
    rule_decks = _rule_deck_report(manifest)
    process_corners = _process_corner_report(manifest)
    compact_models = _compact_model_report(manifest)
    package_rules = _package_rule_report(manifest)
    pcell_library = _artifact_report(manifest, "pcellLibrary")
    foundry_locked = bool(manifest and manifest.get("foundryPdkLocked") is True and manifest.get("foundry"))
    selected_pdk = str(manifest.get("pdkName") or pdk) if manifest else pdk
    gds_ready = bool(gds_audit and gds_audit.get("auditFlags", {}).get("gds_generated"))

    flags = {
        "foundry_pdk_locked": foundry_locked,
        "generic_siph_only": selected_pdk == "generic-si-photonics" or not foundry_locked,
        "layer_map_locked": layer_map["complete"],
        "drc_deck_present": rule_decks["drc"]["present"],
        "lvs_deck_present": rule_decks["lvs"]["present"],
        "process_corners_present": process_corners["complete"],
        "pcell_library_present": pcell_library["present"],
        "compact_models_present": compact_models["complete"],
        "package_rules_present": package_rules["complete"],
        "gds_available_for_signoff": gds_ready,
    }
    flags["pdk_ready"] = all(
        flags[key]
        for key in (
            "foundry_pdk_locked",
            "layer_map_locked",
            "drc_deck_present",
            "lvs_deck_present",
            "process_corners_present",
            "pcell_library_present",
            "compact_models_present",
            "package_rules_present",
        )
    )
    flags["drc_lvs_runnable"] = flags["pdk_ready"] and flags["gds_available_for_signoff"]

    blockers = _blockers(flags, layer_map, rule_decks, process_corners, compact_models, package_rules, pcell_library)
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.pdk-audit.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "requestedPdk": pdk,
        "pdkManifest": str(pdk_manifest) if pdk_manifest else None,
        "selectedPdk": selected_pdk,
        "foundry": manifest.get("foundry") if manifest else None,
        "process": manifest.get("process") if manifest else None,
        "readinessFlags": flags,
        "layerMap": layer_map,
        "ruleDecks": rule_decks,
        "processCorners": process_corners,
        "pcellLibrary": pcell_library,
        "compactModels": compact_models,
        "packageRules": package_rules,
        "gdsSignoffInput": {
            "path": str(gds_audit_path) if gds_audit_path else None,
            "gdsGenerated": gds_ready,
            "notTapeoutReady": bool(gds_audit and gds_audit.get("auditFlags", {}).get("not_tapeout_ready")),
        },
        "blockers": blockers,
        "nextArtifacts": [
            "pdk/foundry-pdk-manifest.json",
            "pdk/layer-map.json",
            "pdk/drc-deck",
            "pdk/lvs-deck",
            "pdk/process-corners.json",
            "pdk/compact-models/*.sparam",
            "pdk/pcell-library",
            "pdk/package-rules.json",
            "reports/node-alpha/gds-path/drc-report.json",
            "reports/node-alpha/gds-path/lvs-report.json",
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


def _artifact_report(manifest: dict[str, Any], key: str) -> dict[str, Any]:
    value = manifest.get(key) if manifest else None
    if isinstance(value, dict):
        path = value.get("path")
        version = value.get("version")
    else:
        path = value
        version = None
    exists = bool(path and Path(path).exists())
    return {
        "path": str(path) if path else None,
        "version": version,
        "present": exists,
    }


def _layer_map_report(manifest: dict[str, Any]) -> dict[str, Any]:
    layers = manifest.get("layerMap", []) if manifest else []
    if isinstance(layers, dict):
        layer_items = list(layers.values())
    elif isinstance(layers, list):
        layer_items = layers
    else:
        layer_items = []
    purposes = {
        str(item.get("purpose") or item.get("name") or "").strip().lower().replace("_", "-")
        for item in layer_items
        if isinstance(item, dict)
    }
    normalized = {_normalize_purpose(purpose) for purpose in purposes}
    missing = [purpose for purpose in REQUIRED_LAYER_PURPOSES if purpose not in normalized]
    return {
        "layerCount": len(layer_items),
        "requiredPurposes": list(REQUIRED_LAYER_PURPOSES),
        "observedPurposes": sorted(purpose for purpose in normalized if purpose),
        "missingPurposes": missing,
        "complete": not missing and bool(layer_items),
    }


def _rule_deck_report(manifest: dict[str, Any]) -> dict[str, Any]:
    decks = manifest.get("ruleDecks", {}) if manifest else {}
    if not isinstance(decks, dict):
        decks = {}
    return {
        "drc": _artifact_report(decks, "drc"),
        "lvs": _artifact_report(decks, "lvs"),
        "antenna": _artifact_report(decks, "antenna"),
        "density": _artifact_report(decks, "density"),
    }


def _process_corner_report(manifest: dict[str, Any]) -> dict[str, Any]:
    corners = manifest.get("processCorners", []) if manifest else []
    if not isinstance(corners, list):
        corners = []
    names = [str(item.get("name") if isinstance(item, dict) else item) for item in corners]
    return {
        "count": len(names),
        "corners": names,
        "complete": bool(names),
    }


def _compact_model_report(manifest: dict[str, Any]) -> dict[str, Any]:
    models = manifest.get("compactModels", {}) if manifest else {}
    if not isinstance(models, dict):
        models = {}
    by_device = {device: _artifact_report(models, device) for device in REQUIRED_CORE_MODELS}
    missing = [device for device, report in by_device.items() if not report["present"]]
    return {
        "requiredDevices": list(REQUIRED_CORE_MODELS),
        "byDevice": by_device,
        "missingDevices": missing,
        "complete": not missing,
    }


def _package_rule_report(manifest: dict[str, Any]) -> dict[str, Any]:
    rules = manifest.get("packageRules", {}) if manifest else {}
    if not isinstance(rules, dict):
        rules = {}
    required = ("fiberArray", "edgeCoupler", "padOpening", "thermalKeepout", "probeCard")
    missing = [key for key in required if not rules.get(key)]
    return {
        "requiredRules": list(required),
        "missingRules": missing,
        "rules": rules,
        "complete": not missing,
    }


def _blockers(
    flags: dict[str, bool],
    layer_map: dict[str, Any],
    rule_decks: dict[str, Any],
    process_corners: dict[str, Any],
    compact_models: dict[str, Any],
    package_rules: dict[str, Any],
    pcell_library: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if not flags["foundry_pdk_locked"]:
        blockers.append("foundry_pdk_locked: no real foundry PDK manifest is version-locked.")
    if not flags["layer_map_locked"]:
        blockers.append(f"layer_map_locked: missing purposes {layer_map['missingPurposes']}.")
    if not flags["drc_deck_present"]:
        blockers.append(f"drc_deck_present: missing or unreadable DRC deck at {rule_decks['drc']['path']}.")
    if not flags["lvs_deck_present"]:
        blockers.append(f"lvs_deck_present: missing or unreadable LVS deck at {rule_decks['lvs']['path']}.")
    if not flags["process_corners_present"]:
        blockers.append("process_corners_present: no process corner model list is attached.")
    if not flags["pcell_library_present"]:
        blockers.append(f"pcell_library_present: missing or unreadable PCell library at {pcell_library['path']}.")
    if not flags["compact_models_present"]:
        blockers.append(f"compact_models_present: missing compact models for {compact_models['missingDevices']}.")
    if not flags["package_rules_present"]:
        blockers.append(f"package_rules_present: missing package rules {package_rules['missingRules']}.")
    if not flags["gds_available_for_signoff"]:
        blockers.append("gds_available_for_signoff: generated GDS audit is missing.")
    return blockers


def _normalize_purpose(purpose: str) -> str:
    if purpose in {"wg", "waveguide-core"}:
        return "waveguide"
    if purpose in {"m1", "metal-routing"}:
        return "metal"
    if purpose in {"electrical-pad", "pad-opening"}:
        return "pad"
    if purpose in {"pin", "ports"}:
        return "port"
    return purpose
