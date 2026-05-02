# OQP-HRM Node Alpha Closure

Node Alpha is the simulation-only completion boundary for this repository.

It may use:

- repository code and deterministic reports
- local FDTD/eigenmode simulations
- generic-SiPh GDS artifacts
- compiler, runtime, resource, threshold, and audit models
- synthetic fixtures only when they are clearly test fixtures and not evidence

It may not claim:

- foundry PDK readiness
- foundry-calibrated S-parameters
- DRC/LVS signoff
- measured source, detector, package, control, calibration, or feed-forward data
- measured primitive-demo datasets
- validated hardware-calibrated fault tolerance

The closure report is generated with:

```bash
oqp node-alpha-closure hardware/Heralded_Reset_Mesh_Blueprint.yaml \
  --out reports/node-alpha/qc-path/node-alpha-closure.json
```

`node_alpha_maxed_without_realworld_input` means every local item that Node Alpha
can honestly finish is complete. It does not mean `prototype_ready` or
`complete_quantum_computer`.

The report must keep the real-world hard stops visible so that simulated or
template artifacts cannot be mistaken for measured evidence.
