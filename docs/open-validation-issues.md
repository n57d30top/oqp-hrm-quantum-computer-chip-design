# Open Validation Issues

These are no-budget or partner-assisted tasks. Each issue should preserve the
claim boundary: simulation results are useful evidence, but they are not lab or
foundry proof.

## Issue 1: Independent Device Metric Review

Label: `validation`, `device-sweep`, `good-first-review`

Goal: Review whether the current 2D FDTD acceptance metrics are meaningful for
the coupler, MZI, phase shifter, and truth switch.

Evidence to inspect:

- `reports/node-alpha/value-upgrade-20260502/high-resolution-robustness-report.json`
- `reports/node-alpha/qc-path/mission-20260502144050-g1swlg-device-sweep.json`
- `reports/node-alpha/qc-path/mission-20260502143702-hlhk77-device-sweep.json`

Definition of done:

- Written comment identifying accepted assumptions, questionable assumptions,
  and any metric that needs 3D, MPB, or S-parameter verification.

## Issue 2: Generic GDS To PDK Gap Review

Label: `validation`, `gds`, `foundry-needed`

Goal: Map the generic GDS audit to a real foundry PDK gap list without running a
paid tapeout.

Evidence to inspect:

- `reports/node-alpha/gds-path/gds-manifest.json`
- `reports/node-alpha/gds-path/gds-audit.json`
- `reports/node-alpha/gds-path/oqp-hrm-generic-siph.gds`

Definition of done:

- A foundry-specific gap list for layer mapping, minimum rules, PCells, optical
  ports, electrical pads, DRC decks, and LVS decks.

## Issue 3: S-Parameter Replacement Plan

Label: `validation`, `sparameters`, `hardware-needed`

Goal: Replace the virtual S-parameter placeholders with a realistic foundry or
wafer-measurement plan.

Evidence to inspect:

- `reports/node-alpha/qc-path/sparameter-models.json`
- `reports/node-alpha/qc-path/sparameter-audit.json`

Definition of done:

- Required wavelength range, process corners, port conventions, file format,
  passivity/reciprocity thresholds, and calibration source are specified for all
  four core devices.

## Issue 4: Testchip Yield Stress Review

Label: `validation`, `testchip`, `simulation`

Goal: Determine which parameters dominate the current low system-yield estimate.

Evidence to inspect:

- `reports/node-alpha/value-upgrade-20260502/testchip/yield-sweep.json`
- `reports/node-alpha/value-upgrade-20260502/testchip/testchip-simulation.json`

Definition of done:

- Ranked list of yield blockers and a next sweep proposal that does not require
  paid hardware.

## Issue 5: Fault-Tolerance Assumption Review

Label: `validation`, `decoder`, `fault-tolerance`

Goal: Review whether the synthetic syndrome/noise data are clearly separated
from hardware-calibrated noise claims.

Evidence to inspect:

- `reports/node-alpha/qc-path/fault-tolerance-audit.json`
- `reports/node-alpha/qc-path/decoder-report.json`
- `reports/node-alpha/qc-path/syndrome-noise-dataset.json`

Definition of done:

- Written review confirming what can be claimed from synthetic data and what
  requires hardware-calibrated distributions.

## Issue 6: Preprint Technical Review

Label: `paper`, `review`, `no-budget`

Goal: Turn `docs/preprint-outline.md` into a reviewable preprint draft.

Definition of done:

- Draft has figures, method details, explicit claim boundaries, and no
  prototype/tapeout/fault-tolerance overclaim.
