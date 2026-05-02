# No-Budget Completion Audit

Objective: make the repository more valuable with zero cash budget by packaging
the simulation evidence for partner review, strengthening reproducibility, and
marking all build/prototype gates that still need external foundry, hardware,
or lab input.

## Prompt-To-Artifact Checklist

| Requirement | Artifact or command | Evidence status |
| --- | --- | --- |
| Simulationspaket haerten | `reports/node-alpha/value-upgrade-20260502/high-resolution-robustness-report.json` | 20/60 accepted devices: coupler, MZI, phase-shifter, truth-switch |
| Reproduzierbarkeit maximal machen | `docs/30-minute-reproduction.md` | Contains install, tests, value-package, GDS audit, JSON validation, and notebook steps |
| One-command value package | `python3 -m oqp.cli value-package ...` | Regenerates value-upgrade report, testchip package, threshold, decoder, S-parameter audit, evidence bundle |
| Report index | `reports/node-alpha/report-index.json` | Contains paths, sizes, SHA-256 hashes, schema versions, summaries, readiness flags |
| Partnerpaket | `docs/no-budget-partner-package.md` | Includes one-page summary, no-cash asks, 90-day plan, artifact map |
| Testchip proposal path | `docs/no-budget-partner-package.md` and `docs/open-validation-issues.md` | Defines foundry/lab review asks and testchip yield review issue |
| Wissenschaftliche Glaubwuerdigkeit | `docs/preprint-outline.md` | Includes claim boundary, result table, figure plan, related-work anchors |
| Open-source value | `docs/open-validation-issues.md` | Six scoped validation issues with evidence files and definitions of done |
| Demo notebook | `notebooks/node-alpha-report-summary.ipynb` | Reads local reports and plots readiness/device status |
| CI/test-suite | `.github/workflows/ci.yml` and `python3 -m unittest tests.test_architecture_models` | Unit-test workflow added; local test command passes |
| No false build claim | `reports/node-alpha/no-budget-package/no-budget-readiness.json` | Prototype, GDS, S-parameter, hardware-noise, and testchip yield gates remain blocked |

## Remaining External Blockers

- Foundry-calibrated S-parameter compact models.
- Real PDK mapping, DRC, and LVS.
- Measured source, detector, package, control, calibration, and feed-forward
  evidence.
- Hardware-calibrated syndrome/noise distributions.
- Fabricated testchip and measured yield.
- Patent filing or legal freedom-to-operate work.

## Completion Standard

This no-budget package is complete if:

- The documented reproduction commands are valid.
- The generated JSON artifacts parse.
- The local unit suite passes.
- The package does not claim prototype or tapeout readiness.
- Every zero-cash deliverable maps to a concrete file.
