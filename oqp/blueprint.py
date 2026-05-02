"""Blueprint loading and candidate mutation for OQP-HRM."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


DEFAULT_EFFECTIVE_STAGE_COUNT = 4


@dataclass(frozen=True)
class SpatialModel:
    network_style: str
    lane_mode: str
    waveguide_count: int
    interferometer_count: int
    laser_wavelength_nm: int
    pairing_stride: int = 3


@dataclass(frozen=True)
class Metrics:
    attenuation_loss_score: float
    crosstalk_risk_score: float
    hop_latency_score: float
    heralding_yield: float
    effective_component_stage_count: int = DEFAULT_EFFECTIVE_STAGE_COUNT


@dataclass(frozen=True)
class Blueprint:
    topology_class: str
    solver_target: str
    spatial_model: SpatialModel
    metrics: Metrics
    documentation: list[str]
    source_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "topology_class": self.topology_class,
            "solver_target": self.solver_target,
            "spatial_model": {
                "network_style": self.spatial_model.network_style,
                "lane_mode": self.spatial_model.lane_mode,
                "waveguide_count": self.spatial_model.waveguide_count,
                "interferometer_count": self.spatial_model.interferometer_count,
                "laser_wavelength_nm": self.spatial_model.laser_wavelength_nm,
                "pairing_stride": self.spatial_model.pairing_stride,
            },
            "metrics": {
                "attenuation_loss_score": self.metrics.attenuation_loss_score,
                "effective_component_stage_count": self.metrics.effective_component_stage_count,
                "crosstalk_risk_score": self.metrics.crosstalk_risk_score,
                "hop_latency_score": self.metrics.hop_latency_score,
                "heralding_yield": self.metrics.heralding_yield,
            },
            "documentation": self.documentation,
        }

    def mutate(
        self,
        *,
        waveguide_count: int | None = None,
        interferometer_count: int | None = None,
        pairing_stride: int | None = None,
        heralding_yield: float | None = None,
        attenuation_loss_score: float | None = None,
    ) -> "Blueprint":
        spatial_model = replace(
            self.spatial_model,
            waveguide_count=waveguide_count or self.spatial_model.waveguide_count,
            interferometer_count=interferometer_count or self.spatial_model.interferometer_count,
            pairing_stride=pairing_stride or self.spatial_model.pairing_stride,
        )
        metrics = replace(
            self.metrics,
            heralding_yield=heralding_yield if heralding_yield is not None else self.metrics.heralding_yield,
            attenuation_loss_score=(
                attenuation_loss_score
                if attenuation_loss_score is not None
                else self.metrics.attenuation_loss_score
            ),
        )
        return replace(self, spatial_model=spatial_model, metrics=metrics)


def load_blueprint(path: str | Path) -> Blueprint:
    blueprint_path = Path(path)
    raw_text = blueprint_path.read_text(encoding="utf-8")
    try:
        import yaml

        raw = yaml.safe_load(raw_text)
    except ModuleNotFoundError:
        raw = _load_minimal_blueprint_yaml(raw_text)
    spatial = raw["spatial_model"]
    metrics = raw["metrics"]
    return Blueprint(
        topology_class=raw.get("topology_class", "heralded_reset_truth_switch"),
        solver_target=raw.get("solver_target", "strawberryfields_gaussian"),
        spatial_model=SpatialModel(
            network_style=spatial.get("network_style", "small_world"),
            lane_mode=spatial.get("lane_mode", "device_component"),
            waveguide_count=int(spatial["waveguide_count"]),
            interferometer_count=int(spatial["interferometer_count"]),
            laser_wavelength_nm=int(spatial.get("laser_wavelength_nm", 1550)),
            pairing_stride=int(spatial.get("pairing_stride", 3)),
        ),
        metrics=Metrics(
            attenuation_loss_score=float(metrics["attenuation_loss_score"]),
            crosstalk_risk_score=float(metrics.get("crosstalk_risk_score", 0.0)),
            hop_latency_score=float(metrics.get("hop_latency_score", 1.0)),
            heralding_yield=float(metrics.get("heralding_yield", 1 - metrics["attenuation_loss_score"])),
            effective_component_stage_count=int(
                metrics.get("effective_component_stage_count", DEFAULT_EFFECTIVE_STAGE_COUNT)
            ),
        ),
        documentation=list(raw.get("documentation", [])),
        source_path=str(blueprint_path),
    )


def write_blueprint(blueprint: Blueprint, path: str | Path) -> None:
    import yaml

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(blueprint.to_dict(), sort_keys=False), encoding="utf-8")


def _load_minimal_blueprint_yaml(raw_text: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    section: str | None = None
    for raw_line in raw_text.splitlines():
        line_without_comment = raw_line.split("#", 1)[0].rstrip()
        if not line_without_comment.strip():
            continue
        stripped = line_without_comment.strip()
        if not line_without_comment.startswith(" ") and stripped.endswith(":"):
            section = stripped[:-1]
            parsed[section] = [] if section == "documentation" else {}
            continue
        if not line_without_comment.startswith(" ") and ":" in stripped:
            key, value = stripped.split(":", 1)
            parsed[key.strip()] = _parse_scalar(value.strip())
            section = None
            continue
        if section == "documentation" and stripped.startswith("- "):
            parsed[section].append(_parse_scalar(stripped[2:].strip()))
            continue
        if section and ":" in stripped:
            key, value = stripped.split(":", 1)
            parsed[section][key.strip()] = _parse_scalar(value.strip())
    return parsed


def _parse_scalar(value: str) -> Any:
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value
