# OQP-HRM Public Data Room Index

This index maps the evidence that is actually included in the public repository.
It separates public simulation artifacts from private/excluded full-package
materials and from external hardware/foundry evidence that does not exist yet.

## Public Decision Documents

- README and claim boundary: `README.md`
- Artifact manifest and hashes: `ARTIFACTS.md`, `ARTIFACTS.sha256`
- Commercial licensing note: `COMMERCIAL-LICENSING.md`
- Validation roadmap: `VALIDATION_ROADMAP.md`
- Reproduction guide: `docs/30-minute-reproduction.md`
- Partner outreach: `docs/partner-outreach.md`
- Grant concept: `docs/grant-concept-note.md`
- Reviewer pack: `docs/reviewer-pack.md`
- Partner pipeline: `docs/partner-pipeline.md`
- Public partner package: `docs/no-budget-partner-package.md`
- Value audit: `docs/value-increase-completion-audit.md`

## Public Technical Evidence

- Public report index: `reports/node-alpha/report-index.json`
- Deep-Hardening V3 Max-Out: `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.json`
- Deep-Hardening V3 Markdown summary: `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.md`
- Scorecard: `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-scorecard.json`
- Device sweep: `reports/node-alpha/deep-hardening-v3-20260502/device-sweep-deep-hardening-v3.json`
- Fusion candidates: `reports/node-alpha/deep-hardening-v3-20260502/fusion-performance-candidates.json`
- Hardened simulation profile: `reports/node-alpha/deep-hardening-v3-20260502/hardened-simulation-profile.json`
- Operational envelope: `reports/node-alpha/deep-hardening-v3-20260502/operational-envelope-report.json`
- Joint error budget: `reports/node-alpha/deep-hardening-v3-20260502/joint-error-budget-report.json`
- Budget optimizer: `reports/node-alpha/deep-hardening-v3-20260502/budget-optimizer-report.json`
- Throughput report: `reports/node-alpha/deep-hardening-v3-20260502/throughput-report.json`
- Virtual S-parameter acceptance: `reports/node-alpha/deep-hardening-v3-20260502/virtual-sparameter-acceptance-report.json`
- Scaled layout envelope: `reports/node-alpha/deep-hardening-v3-20260502/scaled-layout-envelope-report.json`
- Max-qubit envelope: `reports/node-alpha/deep-hardening-v3-20260502/max-qubit-envelope-report.json`
- Max-qubit No-Go map: `reports/node-alpha/deep-hardening-v3-20260502/max-qubit-no-go-map-report.json`
- Stress recovery: `reports/node-alpha/deep-hardening-v3-20260502/stress-recovery-report.json`
- Control timing model: `reports/node-alpha/deep-hardening-v3-20260502/control-timing-model-report.json`
- Decoder evidence: `reports/node-alpha/deep-hardening-v3-20260502/decoder-evidence-report.json`
- Truth-switch raw closure: `reports/node-alpha/deep-hardening-v3-20260502/truth-switch-raw-closure-report.json`
- Pareto report: `reports/node-alpha/deep-hardening-v3-20260502/multiobjective-pareto-report.json`
- Worst-case corner sweep: `reports/node-alpha/deep-hardening-v3-20260502/worst-case-corner-sweep-report.json`
- Monte-Carlo robustness: `reports/node-alpha/deep-hardening-v3-20260502/monte-carlo-robustness-report.json`
- Prototype gap reduction: `reports/node-alpha/deep-hardening-v3-20260502/prototype-gap-reduction-report.json`
- Internal consistency audit: `reports/node-alpha/deep-hardening-v3-20260502/internal-consistency-audit.json`
- Public device acceptance audit: `reports/node-alpha/qc-path/device-acceptance-audit.json`
- Public device sweep champion: `reports/node-alpha/qc-path/device-sweep-champion.json`
- Public device sweep: `reports/node-alpha/qc-path/device-sweep.json`
- Public fusion device evidence: `reports/node-alpha/qc-path/fusion-device-evidence.json`
- Public S-parameter audit: `reports/node-alpha/qc-path/sparameter-audit.json`

## Public Simulator And Tests

- Python package: `oqp/`
- CLI entry point: `oqp = oqp.cli:main`
- Unit tests: `tests/`
- Package metadata: `pyproject.toml`
- CI workflow: `.github/workflows/ci.yml`

## Excluded From The Public Repository

The following historical/full-package paths are not part of the public repo and
must not be used as public evidence unless they are committed in a future
release:

- Full value-upgrade folder.
- No-budget generated package folder.
- Generic GDS path and GDS audit outputs.
- Lab/demo notebooks.
- Full private QC-path working directories and mission sweeps.
- Graphify outputs and local caches.
- Private partner materials.

## Missing External Evidence

- Foundry PDK manifest.
- DRC and LVS reports.
- Foundry-calibrated S-parameters.
- Hardware source/detector/package/control evidence.
- Hardware-calibrated syndrome/noise dataset.
- Measured device or testchip results.
- Patentability and freedom-to-operate review.

## Claim-Readiness Summary

- public_simulation_package_reproducible: ready
- public_unit_tests_present: ready
- public_v3_report_snapshot_hashed: ready
- public_ci_defined: ready
- foundry_sparameter_ready: blocked_external_evidence
- tapeout_ready: blocked_external_evidence
- hardware_fault_tolerance_ready: blocked_external_evidence
- prototype_ready: blocked_external_evidence
