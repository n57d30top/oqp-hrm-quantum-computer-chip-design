# OQP-HRM Reviewer Pack

This pack turns the scorecard into concrete technical review questions.
It is designed to collect external diligence evidence without making hardware claims.

## Assumption Register

- 2d_fdtd_candidate_validity: simulation_supported_not_hardware_proven; validation needed: 3D/MPB S-parameter extraction for promoted candidates.
- deterministic_yield_grid_relevance: planning_evidence_only; validation needed: Foundry process distributions and measured wafer statistics.
- virtual_sparameter_usefulness: hash_verified_placeholder; validation needed: Foundry or wafer calibrated Touchstone/compact-model files.
- synthetic_noise_representativeness: analytical_only; validation needed: Hardware-calibrated noise and syndrome distributions.
- generic_gds_portability: layout_computable_not_foundry_clean; validation needed: Versioned PDK mapping plus DRC/LVS reports.

## Reviewer Questions

- photonic_device_simulation: Which accepted 20/60 device candidate is most likely to fail under 3D/MPB S-parameter extraction? Artifact: `reports/node-alpha/value-upgrade-20260502/high-resolution-robustness-report.json`
- silicon_photonics_process: Which tolerance axis in the deterministic yield grid is least realistic for a foundry process? Artifact: `reports/node-alpha/value-upgrade-20260502/yield-improvement-report.json`
- foundry_pdk_layout: What is the first blocking issue when mapping the generic GDS to a real PDK? Artifact: `reports/node-alpha/gds-path/gds-manifest.json`
- sparameter_compact_model: What port conventions and process corners are required to replace the virtual S-parameters? Artifact: `reports/node-alpha/qc-path/sparameter-audit.json`
- quantum_error_correction: Which synthetic noise assumption most strongly affects the below-threshold analytical path? Artifact: `reports/node-alpha/qc-path/fault-tolerance-audit.json`
- quantum_photonics_lab: What is the minimal measured primitive-demo dataset that would materially raise diligence value? Artifact: `reports/node-alpha/value-upgrade-20260502/testchip/fusion-testcell-report.json`

## Required Review Output

- One paragraph on whether the artifact is internally coherent.
- One paragraph on the first assumption likely to fail in real hardware/foundry flow.
- One recommended next experiment or report that can be done before paid tapeout.
