# 30-Minute Reproduction Guide

This guide verifies the no-budget OQP-HRM package from local artifacts. It does
not require fabrication access, paid cloud compute, lab hardware, or private
credentials.

## 1. Install Locally

```bash
python3 -m pip install -e .
```

## 2. Run The Unit Tests

```bash
python3 -m unittest tests.test_architecture_models
```

Expected result:

```text
Ran 40 tests
OK
```

## 3. Regenerate The Value Package

```bash
python3 -m oqp.cli value-package hardware/Heralded_Reset_Mesh_Blueprint.yaml \
  --artifact-root reports/node-alpha \
  --device-sweep reports/node-alpha/qc-path/device-sweep.json \
  --out-dir reports/node-alpha/value-upgrade-20260502 \
  --syndrome-event-count 10000 \
  --shots 10000 \
  --target-logical-error-rate 1e-6
```

Expected high-level result:

- `status`: `value_package_generated`
- `highResolutionStatus`: `all_core_devices_high_resolution_accepted`
- `faultToleranceReady`: `false`
- `virtualSparameterModelsReadyForFoundryGate`: `false`
- `prototypeStatus`: `not_prototype_ready`

## 4. Regenerate The Generic GDS Gate

```bash
python3 -m oqp.cli gds-generate hardware/Heralded_Reset_Mesh_Blueprint.yaml \
  --out-dir reports/node-alpha/gds-path

python3 -m oqp.cli gds-audit hardware/Heralded_Reset_Mesh_Blueprint.yaml \
  --manifest reports/node-alpha/gds-path/gds-manifest.json \
  --out reports/node-alpha/gds-path/gds-audit.json
```

Expected result:

- `gds_generated`: `true`
- `layout_computable`: `true`
- `fdtd_gap_backed_placeholder`: `false`
- `foundry_pdk_missing`: `true`
- `drc_not_run`: `true`
- `lvs_not_run`: `true`
- `not_tapeout_ready`: `true`

## 5. Inspect The Report Index

```bash
python3 -m json.tool reports/node-alpha/report-index.json >/dev/null
python3 -m json.tool reports/node-alpha/no-budget-package/no-budget-readiness.json >/dev/null
```

Optional summary:

```bash
python3 - <<'PY'
import json
from pathlib import Path

for path in [
    "reports/node-alpha/value-upgrade-20260502/value-upgrade-report.json",
    "reports/node-alpha/value-upgrade-20260502/high-resolution-robustness-report.json",
    "reports/node-alpha/no-budget-package/no-budget-readiness.json",
]:
    data = json.loads(Path(path).read_text())
    print(path)
    print(json.dumps(data.get("summary") or data.get("simulationPosition"), indent=2, sort_keys=True))
PY
```

## 6. Run The Demo Notebook

Open `notebooks/node-alpha-report-summary.ipynb` and run all cells. It only
reads local JSON reports and plots the current simulation/readiness status.

## Interpretation

If the commands above pass, the repository is reproducible as a no-budget,
simulation-only partner package. It is still not prototype-ready because the
external evidence gates require foundry, hardware, or lab data.
