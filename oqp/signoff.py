"""DRC/LVS signoff audits for OQP-HRM GDS milestones."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .blueprint import Blueprint


SCHEMA_PREFIX = "open-quantum"
CLEAN_STATUSES = {"clean", "pass", "passed", "ok", "drc_clean", "lvs_clean", "clean_with_waivers"}


def generate_signoff_audit(
    blueprint: Blueprint,
    *,
    gds_audit_path: str | Path | None = "reports/node-alpha/gds-path/gds-audit.json",
    pdk_audit_path: str | Path | None = "reports/node-alpha/gds-path/pdk-audit.json",
    drc_report_path: str | Path | None = "reports/node-alpha/gds-path/drc-report.json",
    lvs_report_path: str | Path | None = "reports/node-alpha/gds-path/lvs-report.json",
    waiver_report_path: str | Path | None = "reports/node-alpha/gds-path/signoff-waivers.json",
) -> dict[str, Any]:
    gds_audit = _read_json(gds_audit_path)
    pdk_audit = _read_json(pdk_audit_path)
    waiver_report = _read_json(waiver_report_path)
    drc = _tool_report("drc", drc_report_path, waiver_report)
    lvs = _tool_report("lvs", lvs_report_path, waiver_report)

    gds_generated = bool(gds_audit and gds_audit.get("auditFlags", {}).get("gds_generated"))
    pdk_ready = bool(pdk_audit and pdk_audit.get("readinessFlags", {}).get("pdk_ready"))
    pdk_drc_lvs_runnable = bool(pdk_audit and pdk_audit.get("readinessFlags", {}).get("drc_lvs_runnable"))
    flags = {
        "gds_generated": gds_generated,
        "pdk_ready": pdk_ready,
        "pdk_drc_lvs_runnable": pdk_drc_lvs_runnable,
        "drc_report_present": drc["present"],
        "lvs_report_present": lvs["present"],
        "waiver_policy_approved": _waiver_policy_approved(waiver_report),
        "drc_clean": drc["clean"],
        "lvs_clean": lvs["clean"],
        "drc_clean_or_waived": drc["cleanOrWaived"],
        "lvs_clean_or_waived": lvs["cleanOrWaived"],
    }
    flags["drc_lvs_clean"] = flags["drc_clean_or_waived"] and flags["lvs_clean_or_waived"]
    flags["signoff_ready"] = gds_generated and pdk_ready and pdk_drc_lvs_runnable and flags["drc_lvs_clean"]
    flags["not_tapeout_ready"] = not flags["signoff_ready"]

    blockers = _blockers(flags, drc, lvs)
    return {
        "schemaVersion": f"{SCHEMA_PREFIX}.signoff-audit.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePath": blueprint.source_path,
        "artifactInputs": {
            "gdsAudit": str(gds_audit_path) if gds_audit_path else None,
            "pdkAudit": str(pdk_audit_path) if pdk_audit_path else None,
            "drcReport": str(drc_report_path) if drc_report_path else None,
            "lvsReport": str(lvs_report_path) if lvs_report_path else None,
            "waiverReport": str(waiver_report_path) if waiver_report_path else None,
        },
        "readinessFlags": flags,
        "drc": drc,
        "lvs": lvs,
        "waivers": _waiver_summary(waiver_report),
        "blockers": blockers,
        "nextArtifacts": [
            "reports/node-alpha/gds-path/drc-report.json",
            "reports/node-alpha/gds-path/lvs-report.json",
            "reports/node-alpha/gds-path/signoff-waivers.json",
            "reports/node-alpha/gds-path/signoff-audit.json",
        ],
    }


def _tool_report(kind: str, path: str | Path | None, waiver_report: dict[str, Any]) -> dict[str, Any]:
    raw = _read_json(path)
    present = bool(raw)
    total = _violation_count(kind, raw)
    fatal = _fatal_count(raw)
    waived = _waived_count(kind, waiver_report)
    unwaived = max(0, total - waived)
    clean_by_status = _status(raw) in CLEAN_STATUSES
    clean = present and fatal == 0 and (raw.get("clean") is True or clean_by_status or total == 0)
    clean_or_waived = clean or (present and _waiver_policy_approved(waiver_report) and fatal == 0 and unwaived == 0)
    return {
        "path": str(path) if path else None,
        "present": present,
        "tool": raw.get("tool") if raw else None,
        "version": raw.get("version") if raw else None,
        "status": _status(raw) if raw else "missing",
        "totalViolations": total,
        "waivedViolations": waived,
        "unwaivedViolations": unwaived,
        "fatalCount": fatal,
        "clean": clean,
        "cleanOrWaived": clean_or_waived,
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


def _status(raw: dict[str, Any]) -> str:
    return str(raw.get("status") or raw.get("result") or "").strip().lower().replace("-", "_")


def _violation_count(kind: str, raw: dict[str, Any]) -> int:
    if not raw:
        return 0
    for key in ("unwaivedViolationCount", "violationCount", "violations", "errorCount", "errors"):
        value = raw.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, list):
            return len(value)
    if kind == "lvs":
        return sum(_count(raw.get(key)) for key in ("mismatchCount", "shortCount", "openCount", "unmatchedPortCount"))
    return 0


def _fatal_count(raw: dict[str, Any]) -> int:
    for key in ("fatalCount", "fatalErrorCount", "crashCount"):
        value = raw.get(key)
        if isinstance(value, int):
            return value
    return 0


def _count(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, list):
        return len(value)
    return 0


def _waived_count(kind: str, waiver_report: dict[str, Any]) -> int:
    if not waiver_report:
        return 0
    direct = waiver_report.get(f"{kind}WaivedViolations")
    if isinstance(direct, int):
        return direct
    if isinstance(direct, list):
        return len(direct)
    waivers = waiver_report.get("waivers")
    if isinstance(waivers, list):
        return sum(1 for item in waivers if isinstance(item, dict) and str(item.get("kind")).lower() == kind)
    return 0


def _waiver_policy_approved(waiver_report: dict[str, Any]) -> bool:
    return bool(
        waiver_report
        and (
            waiver_report.get("waiverPolicyApproved") is True
            or waiver_report.get("approvalStatus") in {"approved", "waived"}
        )
    )


def _waiver_summary(waiver_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "present": bool(waiver_report),
        "waiverPolicyApproved": _waiver_policy_approved(waiver_report),
        "approvalId": waiver_report.get("approvalId") if waiver_report else None,
        "approvedBy": waiver_report.get("approvedBy") if waiver_report else None,
        "drcWaivedViolations": _waived_count("drc", waiver_report),
        "lvsWaivedViolations": _waived_count("lvs", waiver_report),
    }


def _blockers(flags: dict[str, bool], drc: dict[str, Any], lvs: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if not flags["gds_generated"]:
        blockers.append("gds_generated: no generated GDS audit is available for signoff.")
    if not flags["pdk_ready"]:
        blockers.append("pdk_ready: foundry PDK audit has not passed.")
    if not flags["pdk_drc_lvs_runnable"]:
        blockers.append("pdk_drc_lvs_runnable: PDK audit does not yet allow DRC/LVS execution.")
    if not flags["drc_report_present"]:
        blockers.append("drc_report_present: no DRC report is attached.")
    elif not flags["drc_clean_or_waived"]:
        blockers.append(
            f"drc_clean_or_waived: {drc['unwaivedViolations']} unwaived violations and {drc['fatalCount']} fatal errors remain."
        )
    if not flags["lvs_report_present"]:
        blockers.append("lvs_report_present: no LVS report is attached.")
    elif not flags["lvs_clean_or_waived"]:
        blockers.append(
            f"lvs_clean_or_waived: {lvs['unwaivedViolations']} unwaived mismatches and {lvs['fatalCount']} fatal errors remain."
        )
    return blockers
