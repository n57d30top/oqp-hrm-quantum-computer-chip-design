# Value Increase Completion Audit

Objective: increase the value of the public OQP-HRM design under the current
no-cash constraint by making the repository easier to diligence, reproduce,
review, and fund without adding false hardware claims.

## Public Success Criteria

| Requirement | Public artifact or command | Evidence |
| --- | --- | --- |
| Conservative claim boundary | `README.md` | Build, foundry, DRC/LVS, hardware, prototype, tapeout, and product-readiness claims remain blocked |
| Public artifact hashes | `ARTIFACTS.md`, `ARTIFACTS.sha256` | Committed public reports can be checksum-verified |
| Public report index | `reports/node-alpha/report-index.json` | Index contains only public committed artifacts and reports zero missing public artifacts |
| Reproduction guide | `docs/30-minute-reproduction.md` | Install, full tests, JSON validation, hash verification, and scratch V3 regeneration |
| CI workflow | `.github/workflows/ci.yml` | Tests, JSON validation, checksums, V3 scratch regeneration, and claim-boundary invariants |
| Partner outreach package | `docs/partner-outreach.md` | Contains short email and reviewer ask options |
| Grant concept package | `docs/grant-concept-note.md` | Defines work packages and non-dilutive funding target |
| Reviewer question bank | `docs/reviewer-pack.md` | Defines concrete reviewer questions and public evidence files |
| Partner pipeline | `docs/partner-pipeline.md` | Defines no-cash/partner-time stages with success metrics |
| Data-room index | `docs/data-room-index.md` | Maps public evidence, public exclusions, and missing external evidence |
| Deep-Hardening V3 Max-Out | `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.json` | Completes the simulation-only V3 hardening scorecard without asserting hardware, foundry, prototype, or tapeout readiness |
| Device sweep | `reports/node-alpha/deep-hardening-v3-20260502/device-sweep-deep-hardening-v3.json` | Public committed device-sweep snapshot |
| Truth-Switch raw closure | `reports/node-alpha/deep-hardening-v3-20260502/truth-switch-raw-closure-report.json` | Raw crosstalk/reflection closure; compensated candidate is not substituted |
| Fusion candidates | `reports/node-alpha/deep-hardening-v3-20260502/fusion-performance-candidates.json` | Model-capped success/fidelity candidates with claim-boundary notes |
| Operational envelope | `reports/node-alpha/deep-hardening-v3-20260502/operational-envelope-report.json` | Budgets single-axis loss, detector-efficiency, phase-error, dark-count, and feed-forward margins for 1e-8/1e-9 logical-error targets |
| Joint error budget | `reports/node-alpha/deep-hardening-v3-20260502/joint-error-budget-report.json` | Converts the envelope into combined passing operating profiles for 1e-8/1e-9 with reserve |
| Budget optimizer | `reports/node-alpha/deep-hardening-v3-20260502/budget-optimizer-report.json` | Searches valid budget splits and selects balanced, detector-relaxed, loss-relaxed, and latency-relaxed 1e-9 profiles |
| Throughput report | `reports/node-alpha/deep-hardening-v3-20260502/throughput-report.json` | Lists upper-bound fusion attempts/s, heralded events/s, and logical cycles/s without raising the 200M attempts/s cap |
| Virtual S-parameter acceptance | `reports/node-alpha/deep-hardening-v3-20260502/virtual-sparameter-acceptance-report.json` | Accepts 4/4 virtual models while explicitly keeping foundry-calibrated S-parameters false |
| Layout envelope | `reports/node-alpha/deep-hardening-v3-20260502/scaled-layout-envelope-report.json` | Estimates generic layout area, banked ports/pads, route lengths, and tapeout blockers |
| Max-qubit No-Go map | `reports/node-alpha/deep-hardening-v3-20260502/max-qubit-no-go-map-report.json` | Records 712 and 760 closure plus the first rejected 768-mode row and failure reasons |
| Stress recovery | `reports/node-alpha/deep-hardening-v3-20260502/stress-recovery-report.json` | Passes the 1e-9 combined and worst-case analytical stress points at uniform stress scale `1.0` |
| Control timing model | `reports/node-alpha/deep-hardening-v3-20260502/control-timing-model-report.json` | Provides a 1.17 ns analytical fast path while keeping hardware feed-forward verification false |
| Decoder evidence | `reports/node-alpha/deep-hardening-v3-20260502/decoder-evidence-report.json` | Adds toy matching-decoder graph and sub-15 ns full-decoder evidence while keeping production decoder readiness false |
| Pareto/corner/Monte-Carlo | `reports/node-alpha/deep-hardening-v3-20260502/multiobjective-pareto-report.json` | Adds multi-objective Pareto, 1875-corner worst-case sweep, Monte-Carlo robustness, sensitivity, and consistency reports |
| Prototype gap reduction | `reports/node-alpha/deep-hardening-v3-20260502/prototype-gap-reduction-report.json` | Maps local simulation improvements to prototype gates while preserving real-world hard stops |
| Tests cover generators | `python3 -m unittest discover -s tests -v` | 49 tests pass locally |

## Current Scorecard Snapshot

- Internal simulation evidence score: `90 / 100`
- External hardware evidence score: blocked/not scored as validated hardware
- Partner diligence readiness: `100 / 100`
- Commercial readiness: `25 / 100`
- Scorecard completeness: `100 / 100`
- Immediate sale range: `0-10000`
- Partner package range: `10000-50000`
- Grant leverage target: `50000-300000`
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
- Virtual S-parameter acceptance: `4 / 4` virtual devices accepted; foundry S-parameters ready `false`
- Scaled generic layout: max area `17.9800 mm^2`, 760 physical modes, 380 logical dual-rail qubits; next rejected step is 768 physical modes / 384 logical qubits due to the sub-18-mm^2 stretch-area ceiling and optical-port ceiling
- Upper-bound fusion attempts/s: `200000000`
- Active critical risks: missing external foundry/hardware validation

## Public Exclusions

The public repo does not include private/full value-package folders, generated
GDS outputs, lab notebooks, full mission-sweep working directories, graph
outputs, caches, or private partner data. Those files are not public evidence
unless committed in a future release and added to the hash manifest.

## Residual Blockers

- No foundry-calibrated S-parameters.
- No PDK-bound DRC/LVS.
- No measured device or testchip.
- No hardware source/detector/package/control evidence.
- No patentability or freedom-to-operate opinion.

## Completion Decision

The repo value has been increased by converting the simulation-only design into
a stronger public reproducibility and diligence package. The result does not
increase prototype readiness, and it deliberately preserves the hard external
blockers.
