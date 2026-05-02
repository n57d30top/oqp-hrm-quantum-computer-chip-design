# OQP-HRM Reviewer Pack

This pack turns the scorecard into concrete technical review questions.
It is designed to collect external diligence evidence without making hardware claims.

## Assumption Register

- 2d_fdtd_candidate_validity: simulation_supported_not_hardware_proven; validation needed: 3D/MPB S-parameter extraction for promoted candidates.
- deterministic_yield_grid_relevance: planning_evidence_only; validation needed: Foundry process distributions and measured wafer statistics.
- virtual_sparameter_usefulness: hash_verified_placeholder; validation needed: Foundry or wafer calibrated Touchstone/compact-model files.
- synthetic_noise_representativeness: analytical_only; validation needed: Hardware-calibrated noise and syndrome distributions.
- generic_layout_portability: layout_envelope_not_foundry_clean; validation needed: Versioned PDK mapping plus DRC/LVS reports.

## Reviewer Questions

- photonic_device_simulation: Which public V3 device candidate is most likely to fail under 3D/MPB S-parameter extraction? Artifact: `reports/node-alpha/deep-hardening-v3-20260502/device-sweep-deep-hardening-v3.json`
- silicon_photonics_process: Which V3 corner axis is least realistic for a foundry process? Artifact: `reports/node-alpha/deep-hardening-v3-20260502/worst-case-corner-sweep-report.json`
- foundry_pdk_layout: What is the first blocking issue when mapping the generic layout envelope to a real PDK? Artifact: `reports/node-alpha/deep-hardening-v3-20260502/scaled-layout-envelope-report.json`
- sparameter_compact_model: What port conventions and process corners are required to replace the virtual S-parameters? Artifact: `reports/node-alpha/qc-path/sparameter-audit.json`
- quantum_error_correction: Which analytical noise assumption most strongly affects the 1e-9 envelope? Artifact: `reports/node-alpha/deep-hardening-v3-20260502/operational-envelope-report.json`
- quantum_photonics_lab: What is the minimal measured primitive-demo dataset that would materially raise diligence value? Artifact: `reports/node-alpha/deep-hardening-v3-20260502/prototype-gap-reduction-report.json`

## Required Review Output

- One paragraph on whether the artifact is internally coherent.
- One paragraph on the first assumption likely to fail in real hardware/foundry flow.
- One recommended next experiment or report that can be done before paid tapeout.
