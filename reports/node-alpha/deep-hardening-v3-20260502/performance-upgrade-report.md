# OQP-HRM Deep-Hardening V3

Simulation-only Deep-Hardening V3 Max-Out report. This is not measured chip performance, prototype readiness, foundry readiness, or tapeout readiness.

## Summary

- Max scaled physical modes: `760`
- Max scaled logical dual-rail qubits: `380`
- Target `1e-8` logical error met: `True`
- Target `1e-9` logical error met: `True`
- Best nominal fusion success: `1.0`
- Best nominal fusion fidelity: `0.9999975000000001`
- Best stretch fusion success: `1.0`
- Best stretch fusion fidelity: `0.9999975000000001`
- Truth-switch strict target met: `True`
- Target `1e-9` operational envelope distance: `61`
- Target `1e-9` max single-axis loss: `0.6386042363009726` dB
- Target `1e-9` min single-axis detector efficiency: `0.7720932366132679`
- Target `1e-9` max single-axis phase error: `0.27953436592410935` rad
- Target `1e-9` max single-axis feed-forward latency: `551.976232128157` ns
- Target `1e-9` hardening margin targets met: `True`
- Target `1e-9` joint budget pass: `True`
- Target `1e-9` balanced joint logical error: `1.4711041659587303e-13`
- Target `1e-9` optimized profile count: `8442`
- Target `1e-9` detector-relaxed minimum efficiency: `0.8404652656292875`
- Upper-bound fusion attempts/s: `200000000.0`
- Upper-bound heralded events/s: `200000000.0`
- Virtual S-parameter accepted devices: `4` / `4`
- Max virtual S-parameter crosstalk: `0.0023`
- Max virtual S-parameter reflection: `4e-05`
- Virtual S-parameters below 0.30% / 0.008%: `True` / `True`
- Foundry-calibrated S-parameters ready: `False`
- Max scaled layout area: `17.979962` mm^2
- Max scaled route-length reduction: `0.898313772678447`
- Target `1e-9` stress recovery scale: `1.0`
- Target `1e-9` combined/worst stress pass: `True` / `True`
- Target `1e-9` control timing closed in simulation: `True`
- Best fast-path latency: `1.17` ns
- Target `1e-9` toy decoder latency: `12.732638863577915` ns
- Full decoder below 15 ns: `True`
- Truth-switch raw strict target met: `True`
- Truth-switch raw stretch target met: `True`
- Prototype local simulation criteria improved: `7` / `7`

## Explicit Gaps

- None within the simulation-only objective.

## Artifacts

- deepHardeningV3Report: `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.json`
- deepHardeningV3Markdown: `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.md`
- performanceUpgradeReport: `reports/node-alpha/deep-hardening-v3-20260502/performance-upgrade-report.json`
- performanceUpgradeMarkdown: `reports/node-alpha/deep-hardening-v3-20260502/performance-upgrade-report.md`
- focusedDeviceSweep: `reports/node-alpha/deep-hardening-v3-20260502/device-sweep-deep-hardening-v3.json`
- resourceScalingReport: `reports/node-alpha/deep-hardening-v3-20260502/resource-scaling-report.json`
- fusionPerformanceCandidates: `reports/node-alpha/deep-hardening-v3-20260502/fusion-performance-candidates.json`
- thresholdPerformanceSweep: `reports/node-alpha/deep-hardening-v3-20260502/threshold-performance-sweep.json`
- operationalEnvelopeReport: `reports/node-alpha/deep-hardening-v3-20260502/operational-envelope-report.json`
- jointErrorBudgetReport: `reports/node-alpha/deep-hardening-v3-20260502/joint-error-budget-report.json`
- budgetOptimizerReport: `reports/node-alpha/deep-hardening-v3-20260502/budget-optimizer-report.json`
- throughputReport: `reports/node-alpha/deep-hardening-v3-20260502/throughput-report.json`
- hardenedSimulationProfileReport: `reports/node-alpha/deep-hardening-v3-20260502/hardened-simulation-profile.json`
- virtualSparameterAcceptanceReport: `reports/node-alpha/deep-hardening-v3-20260502/virtual-sparameter-acceptance-report.json`
- scaledLayoutEnvelopeReport: `reports/node-alpha/deep-hardening-v3-20260502/scaled-layout-envelope-report.json`
- maxQubitEnvelopeReport: `reports/node-alpha/deep-hardening-v3-20260502/max-qubit-envelope-report.json`
- maxQubitNoGoMapReport: `reports/node-alpha/deep-hardening-v3-20260502/max-qubit-no-go-map-report.json`
- controlTimingModelReport: `reports/node-alpha/deep-hardening-v3-20260502/control-timing-model-report.json`
- decoderEvidenceReport: `reports/node-alpha/deep-hardening-v3-20260502/decoder-evidence-report.json`
- stressRecoveryReport: `reports/node-alpha/deep-hardening-v3-20260502/stress-recovery-report.json`
- truthSwitchRawClosureReport: `reports/node-alpha/deep-hardening-v3-20260502/truth-switch-raw-closure-report.json`
- multiobjectiveParetoReport: `reports/node-alpha/deep-hardening-v3-20260502/multiobjective-pareto-report.json`
- worstCaseCornerSweepReport: `reports/node-alpha/deep-hardening-v3-20260502/worst-case-corner-sweep-report.json`
- monteCarloRobustnessReport: `reports/node-alpha/deep-hardening-v3-20260502/monte-carlo-robustness-report.json`
- internalConsistencyAudit: `reports/node-alpha/deep-hardening-v3-20260502/internal-consistency-audit.json`
- prototypeGapReductionReport: `reports/node-alpha/deep-hardening-v3-20260502/prototype-gap-reduction-report.json`
- deepHardeningScorecard: `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-scorecard.json`
