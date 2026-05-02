# Open Validation Issues

These are no-budget or partner-assisted tasks. Each issue should preserve the
claim boundary: simulation results are useful evidence, but they are not lab or
foundry proof.

## Issue 1: Independent Device Metric Review

Label: `validation`, `device-sweep`, `good-first-review`

Goal: Review whether the public V3 device acceptance metrics are meaningful for
the coupler, MZI, phase shifter, and truth switch.

Evidence to inspect:

- `reports/node-alpha/deep-hardening-v3-20260502/device-sweep-deep-hardening-v3.json`
- `reports/node-alpha/deep-hardening-v3-20260502/truth-switch-raw-closure-report.json`
- `reports/node-alpha/qc-path/device-acceptance-audit.json`

Definition of done:

- Written comment identifying accepted assumptions, questionable assumptions,
  and any metric that needs 3D, MPB, or S-parameter verification.

## Issue 2: Generic Layout To PDK Gap Review

Label: `validation`, `layout`, `foundry-needed`

Goal: Map the generic layout envelope to a real foundry PDK gap list without
running a paid tapeout.

Evidence to inspect:

- `reports/node-alpha/deep-hardening-v3-20260502/scaled-layout-envelope-report.json`
- `reports/node-alpha/deep-hardening-v3-20260502/max-qubit-envelope-report.json`
- `reports/node-alpha/deep-hardening-v3-20260502/max-qubit-no-go-map-report.json`

Definition of done:

- A foundry-specific gap list for layer mapping, minimum rules, PCells, optical
  ports, electrical pads, DRC decks, and LVS decks.

## Issue 3: S-Parameter Replacement Plan

Label: `validation`, `sparameters`, `hardware-needed`

Goal: Replace the virtual S-parameter placeholders with a realistic foundry or
wafer-measurement plan.

Evidence to inspect:

- `reports/node-alpha/deep-hardening-v3-20260502/virtual-sparameter-acceptance-report.json`
- `reports/node-alpha/qc-path/sparameter-audit.json`

Definition of done:

- Required wavelength range, process corners, port conventions, file format,
  passivity/reciprocity thresholds, and calibration source are specified for all
  four core devices.

## Issue 4: Fusion And Primitive Demo Review

Label: `validation`, `fusion`, `simulation`

Goal: Determine which source, detector, crosstalk, reflection, or timing
assumption dominates the public fusion-performance model.

Evidence to inspect:

- `reports/node-alpha/deep-hardening-v3-20260502/fusion-performance-candidates.json`
- `reports/node-alpha/deep-hardening-v3-20260502/worst-case-corner-sweep-report.json`
- `reports/node-alpha/deep-hardening-v3-20260502/prototype-gap-reduction-report.json`

Definition of done:

- Ranked list of fusion blockers and a next measurement or simulation proposal
  that does not require paid hardware.

## Issue 5: Fault-Tolerance And Decoder Assumption Review

Label: `validation`, `decoder`, `fault-tolerance`

Goal: Review whether the analytical noise and decoder evidence are clearly
separated from hardware-calibrated noise claims.

Evidence to inspect:

- `reports/node-alpha/deep-hardening-v3-20260502/operational-envelope-report.json`
- `reports/node-alpha/deep-hardening-v3-20260502/joint-error-budget-report.json`
- `reports/node-alpha/deep-hardening-v3-20260502/decoder-evidence-report.json`
- `reports/node-alpha/deep-hardening-v3-20260502/control-timing-model-report.json`

Definition of done:

- Written review confirming what can be claimed from analytical/surrogate data
  and what requires hardware-calibrated distributions.

## Issue 6: Reproducibility And CI Review

Label: `validation`, `reproducibility`, `ci`

Goal: Confirm that the public package can be installed, tested, hash-checked,
and regenerated in scratch space without hidden private files.

Evidence to inspect:

- `.github/workflows/ci.yml`
- `docs/30-minute-reproduction.md`
- `ARTIFACTS.md`
- `ARTIFACTS.sha256`
- `reports/node-alpha/report-index.json`

Definition of done:

- Independent run result or issue comment showing tests, JSON validation,
  checksum verification, and V3 scratch regeneration.

## Issue 7: Preprint Technical Review

Label: `paper`, `review`, `no-budget`

Goal: Turn `docs/preprint-outline.md` into a reviewable preprint draft.

Definition of done:

- Draft has figures, method details, explicit claim boundaries, and no
  prototype/tapeout/fault-tolerance overclaim.
