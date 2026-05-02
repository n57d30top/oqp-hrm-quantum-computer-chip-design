# No-Budget Completion Audit

Objective: make the public repository more valuable with zero cash budget by
packaging simulation evidence for review, strengthening reproducibility, and
marking all build/prototype gates that still need external foundry, hardware, or
lab input.

## Public Prompt-To-Artifact Checklist

| Requirement | Public artifact or command | Evidence status |
| --- | --- | --- |
| Simulationspaket haerten | `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.json` | V3 Max-Out scorecard complete; simulation-only |
| Device sweeps aktualisieren | `reports/node-alpha/deep-hardening-v3-20260502/device-sweep-deep-hardening-v3.json` | Public committed sweep snapshot |
| Truth-Switch raw closure | `reports/node-alpha/deep-hardening-v3-20260502/truth-switch-raw-closure-report.json` | Raw crosstalk/reflection targets close in model |
| Fusion candidates | `reports/node-alpha/deep-hardening-v3-20260502/fusion-performance-candidates.json` | Model-capped success and fidelity candidates documented |
| Operational envelope | `reports/node-alpha/deep-hardening-v3-20260502/operational-envelope-report.json` | 1e-8 and 1e-9 analytical budget envelope |
| Corner and Monte-Carlo | `reports/node-alpha/deep-hardening-v3-20260502/worst-case-corner-sweep-report.json`, `reports/node-alpha/deep-hardening-v3-20260502/monte-carlo-robustness-report.json` | Worst-case and deterministic surrogate MC evidence |
| Virtual S-parameters | `reports/node-alpha/deep-hardening-v3-20260502/virtual-sparameter-acceptance-report.json` and `reports/node-alpha/qc-path/sparameter-audit.json` | Virtual gate present; foundry gate remains false |
| Layout envelope | `reports/node-alpha/deep-hardening-v3-20260502/scaled-layout-envelope-report.json` | Generic layout envelope only; no DRC/LVS claim |
| Timing and decoder | `reports/node-alpha/deep-hardening-v3-20260502/control-timing-model-report.json`, `reports/node-alpha/deep-hardening-v3-20260502/decoder-evidence-report.json` | Fast path and full decoder are separate |
| Reproduzierbarkeit maximal machen | `docs/30-minute-reproduction.md` | Install, full tests, JSON validation, hash check, scratch regeneration |
| Report index | `reports/node-alpha/report-index.json` | Public paths, sizes, hashes, and readiness flags |
| Partnerpaket | `docs/no-budget-partner-package.md` | One-page public summary, no-cash asks, 90-day plan, artifact map |
| Testchip proposal path | `docs/open-validation-issues.md` and GitHub issues | Defines foundry/lab review asks without claiming hardware evidence |
| Wissenschaftliche Glaubwuerdigkeit | `docs/preprint-outline.md` | Includes claim boundary, result table, figure plan, related-work anchors |
| Open-source value | `docs/open-validation-issues.md` | Public validation tasks with included evidence files and definitions of done |
| CI/test-suite | `.github/workflows/ci.yml` and `python3 -m unittest discover -s tests -v` | Full test workflow and claim-boundary invariant checks |
| No false build claim | `README.md` and `VALIDATION_ROADMAP.md` | Prototype, tapeout, hardware, DRC/LVS, and foundry S-parameter gates remain blocked |

## Public Exclusions

The public repo does not include private/full value-package folders, generated
GDS outputs, lab notebooks, full mission-sweep working directories, graph
outputs, caches, or private partner data. Those items are not public evidence
unless a future release commits them and updates `ARTIFACTS.md`.

## Remaining External Blockers

- Foundry-calibrated S-parameter compact models.
- Real PDK mapping, DRC, and LVS.
- Measured source, detector, package, control, calibration, and feed-forward
  evidence.
- Hardware-calibrated syndrome/noise distributions.
- Fabricated device or testchip measurements.
- Patent filing or legal freedom-to-operate work.

## Completion Standard

This no-budget public package is complete if:

- The documented reproduction commands are valid.
- The committed JSON artifacts parse.
- The hash manifest verifies the committed snapshot.
- The local unit suite passes.
- CI runs tests, JSON validation, hash checks, V3 scratch regeneration, and
  claim-boundary invariants.
- The package does not claim prototype or tapeout readiness.
- Every public deliverable maps to a concrete committed file.
