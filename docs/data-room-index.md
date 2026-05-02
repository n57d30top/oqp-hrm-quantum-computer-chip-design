# OQP-HRM Data Room Index

## Decision Documents

- Value scorecard: `reports/node-alpha/no-budget-package/value-scorecard.json`
- Partner outreach: `docs/partner-outreach.md`
- Grant concept: `docs/grant-concept-note.md`
- Reviewer pack: `docs/reviewer-pack.md`
- Partner pipeline: `docs/partner-pipeline.md`
- No-budget package: `docs/no-budget-partner-package.md`
- Reproduction guide: `docs/30-minute-reproduction.md`

## Technical Evidence

- High-resolution robustness: `reports/node-alpha/value-upgrade-20260502/high-resolution-robustness-report.json`
- Yield improvement: `reports/node-alpha/value-upgrade-20260502/yield-improvement-report.json`
- Yield-optimized device sweep: `reports/node-alpha/value-upgrade-20260502/yield-optimized-device-sweep.json`
- Deep-Hardening V3 Max-Out: `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.json`
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
- Pareto/corner/Monte-Carlo: `reports/node-alpha/deep-hardening-v3-20260502/multiobjective-pareto-report.json`, `reports/node-alpha/deep-hardening-v3-20260502/worst-case-corner-sweep-report.json`, `reports/node-alpha/deep-hardening-v3-20260502/monte-carlo-robustness-report.json`
- Prototype gap reduction: `reports/node-alpha/deep-hardening-v3-20260502/prototype-gap-reduction-report.json`
- Value package: `reports/node-alpha/value-upgrade-20260502/value-upgrade-report.json`
- GDS audit: `reports/node-alpha/gds-path/gds-audit.json`
- S-parameter audit: `reports/node-alpha/qc-path/sparameter-audit.json`
- Fault-tolerance audit: `reports/node-alpha/qc-path/fault-tolerance-audit.json`
- Prototype readiness: `reports/node-alpha/qc-path/prototype-readiness.json`
- Report index and hashes: `reports/node-alpha/report-index.json`

## Missing External Evidence

- Foundry PDK manifest.
- DRC and LVS reports.
- Foundry-calibrated S-parameters.
- Hardware source/detector/package/control evidence.
- Hardware-calibrated syndrome/noise dataset.
- Measured testchip results.

## Claim-Readiness Summary

- simulation_package_reproducible: ready
- core_devices_accepted_in_2d_node_alpha: ready
- deterministic_testchip_yield_stress_passed: ready
- foundry_sparameter_ready: blocked_external_evidence
- tapeout_ready: blocked_external_evidence
- hardware_fault_tolerance_ready: blocked_external_evidence
- prototype_ready: blocked_external_evidence
