# Value Increase Completion Audit

Objective: increase the value of the OQP-HRM design under the current no-cash
constraint by making the repository easier to diligence, pitch, review, and
fund without adding false hardware claims.

## Success Criteria

| Requirement | Concrete artifact or command | Evidence |
| --- | --- | --- |
| Conservative value scorecard | `reports/node-alpha/no-budget-package/value-scorecard.json` | `status = value_scorecard_generated` |
| Human-readable valuation summary | `reports/node-alpha/no-budget-package/value-scorecard.md` | Lists scores, score breakdown, yield evidence, risk register, and value ladder |
| Transparent score breakdown | `reports/node-alpha/no-budget-package/value-scorecard.json` | `scoreBreakdown` contains technical, commercial, and partner-diligence point items |
| Claim-readiness matrix | `reports/node-alpha/no-budget-package/value-scorecard.json` | Separates simulation-supported claims from foundry, tapeout, hardware, and prototype blockers |
| Diligence risk register | `reports/node-alpha/no-budget-package/value-scorecard.json` | Lists active critical/high risks and mitigations |
| Assumption register | `reports/node-alpha/no-budget-package/value-scorecard.json` | Lists 5 simulation assumptions and the external validation needed for each |
| Reviewer question bank | `docs/reviewer-pack.md` | Defines 6 concrete reviewer questions and the artifact each question should inspect |
| Partner pipeline | `docs/partner-pipeline.md` | Defines 4 no-cash/partner-time stages with success metrics |
| Partner outreach package | `docs/partner-outreach.md` | Contains short email and reviewer ask options |
| Grant concept package | `docs/grant-concept-note.md` | Defines work packages and non-dilutive funding target |
| Data-room index | `docs/data-room-index.md` | Maps decision docs, technical evidence, and missing external evidence |
| Yield improvement | `reports/node-alpha/value-upgrade-20260502/yield-improvement-report.json` | Deterministic system-yield estimate improved from `0.024` to `1.0` |
| Deep-Hardening V3 Max-Out | `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.json` | Completes the simulation-only V3 hardening scorecard without asserting hardware, foundry, prototype, or tapeout readiness |
| Operational envelope | `reports/node-alpha/deep-hardening-v3-20260502/operational-envelope-report.json` | Budgets single-axis loss, detector-efficiency, phase-error, dark-count, and feed-forward margins for 1e-8/1e-9 logical-error targets |
| Joint error budget | `reports/node-alpha/deep-hardening-v3-20260502/joint-error-budget-report.json` | Converts the envelope into combined passing operating profiles for 1e-8/1e-9 with reserve |
| Budget optimizer | `reports/node-alpha/deep-hardening-v3-20260502/budget-optimizer-report.json` | Searches valid budget splits and selects balanced, detector-relaxed, loss-relaxed, and latency-relaxed 1e-9 profiles |
| Throughput report | `reports/node-alpha/deep-hardening-v3-20260502/throughput-report.json` | Lists upper-bound fusion attempts/s, heralded events/s, and logical cycles/s without raising the 200M attempts/s cap |
| Virtual S-parameter acceptance | `reports/node-alpha/deep-hardening-v3-20260502/virtual-sparameter-acceptance-report.json` | Accepts 4/4 virtual models below 0.30% crosstalk and 0.008% reflection while explicitly keeping foundry-calibrated S-parameters false |
| Scaled layout envelope | `reports/node-alpha/deep-hardening-v3-20260502/scaled-layout-envelope-report.json` | Estimates the max-qubit generic layout area, banked ports/pads, route lengths, and tapeout blockers |
| Max-qubit envelope | `reports/node-alpha/deep-hardening-v3-20260502/max-qubit-envelope-report.json` | Selects 760 physical modes / 380 logical dual-rail qubits as the largest local V3 stretch envelope under 18 mm²; rejects the next 768-mode step on area and optical-port ceilings |
| Max-qubit No-Go map | `reports/node-alpha/deep-hardening-v3-20260502/max-qubit-no-go-map-report.json` | Records 712 and 760 closure plus the first rejected 768-mode row and its failure reasons |
| Stress recovery | `reports/node-alpha/deep-hardening-v3-20260502/stress-recovery-report.json` | Passes the 1e-9 combined and worst-case analytical stress points at uniform stress scale `1.0` |
| Control timing model | `reports/node-alpha/deep-hardening-v3-20260502/control-timing-model-report.json` | Provides a 1.17 ns analytical fast path but keeps hardware feed-forward verification false |
| Decoder evidence | `reports/node-alpha/deep-hardening-v3-20260502/decoder-evidence-report.json` | Adds toy matching-decoder graph and sub-15 ns full-decoder evidence while keeping production decoder readiness false |
| Pareto/corner/Monte-Carlo | `reports/node-alpha/deep-hardening-v3-20260502/multiobjective-pareto-report.json` | Adds multi-objective Pareto, 1875-corner worst-case sweep, Monte-Carlo robustness, sensitivity, and consistency reports |
| Prototype gap reduction | `reports/node-alpha/deep-hardening-v3-20260502/prototype-gap-reduction-report.json` | Maps local simulation improvements to prototype gates while preserving real-world hard stops |
| One-command generator | `oqp value-scorecard ...` | CLI writes JSON, Markdown, outreach, grant, reviewer, pipeline, and data-room docs |
| Tests cover generators | `python3 -m unittest discover -s tests -v` | 48 tests pass |
| Report index includes new artifacts | `reports/node-alpha/report-index.json` | `artifactCount = 106`, `missingArtifactCount = 0` |
| No false prototype claim | `value-scorecard.json` summary | `prototypeReady = false`, `tapeoutReady = false`, `foundrySparametersReady = false` |

## Current Scorecard Snapshot

- Technical evidence score: `90 / 100`
- Partner diligence readiness: `100 / 100`
- Commercial readiness: `25 / 100`
- Scorecard completeness: `100 / 100`
- Immediate sale range: `0-10000`
- Partner package range: `10000-50000`
- Grant leverage target: `50000-300000`
- Deterministic simulation-only system yield: `1.0`
- Max scaled physical modes: `760`
- Max scaled logical dual-rail qubits: `380`
- Nominal fusion success/fidelity: `1.0` / `0.999998`
- Truth-switch raw crosstalk/reflection: `0.0023` / `0.00004`
- Target logical error rates covered: `1e-8`, `1e-9`
- Target `1e-9` operational envelope: distance `61`, max single-axis loss `0.638604 dB`, min detector efficiency `0.772093`
- Target `1e-9` joint budget: logical error `1.47e-13`, reserve positive
- Target `1e-9` optimizer: detector-relaxed efficiency `0.840465`, latency-relaxed max feed-forward `387.883 ns`
- Target `1e-9` stress recovery: uniform stress scale `1.0`, combined and worst-case stress pass
- Control timing: best fast-path latency `1.17 ns`
- Toy decoder: target `1e-9` latency estimate `12.73 ns`, production decoder ready `false`
- Virtual S-parameter acceptance: `4 / 4` virtual devices accepted below 0.30% / 0.008%; foundry S-parameters ready `false`
- Scaled generic layout: max area `17.9800 mm^2`, 760 physical modes, 380 logical dual-rail qubits; next rejected step is 768 physical modes / 384 logical qubits due to the sub-18-mm^2 stretch-area ceiling and optical-port ceiling
- Upper-bound fusion attempts/s: `200000000`
- Reviewer questions: `6`
- Partner pipeline stages: `4`
- Active critical risks: `2`

## Residual Blockers

- No foundry-calibrated S-parameters.
- No PDK-bound DRC/LVS.
- No measured testchip.
- No hardware source/detector/package/control evidence.
- No patentability or freedom-to-operate opinion.

## Completion Decision

The repo value has been increased by converting the existing simulation package
into a stronger diligence and funding package. The result does not increase
prototype readiness, and it deliberately preserves the hard external blockers.
