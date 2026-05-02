# OQP-HRM Error-Correction Roadmap

The current OQP-HRM stack is not fault tolerant. This file records the path and blockers.

## Required Decisions

- Logical code: dual-rail loss code, cluster-state fusion scheme, or CV/GKP code.
- Resource factory: single-photon, squeezed-state, GKP, or magic-state generation.
- Syndrome extraction circuit and decoder.
- Threshold estimates for loss, detector error, phase error, and feed-forward latency.

## Current Error-Budget Gate

`oqp error-budget` produces a machine-readable first-pass model with:

- source efficiency
- detector efficiency
- mesh loss
- dark-count probability
- phase error
- feed-forward latency

`oqp threshold-sweep` now adds a fusion-surface-code sweep with a syndrome extraction
graph, decoder interface, logical-error estimate, and resource estimate:

```bash
oqp threshold-sweep hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/threshold-sweep --max-runs 16
```

## Fault-Tolerance Status

The project currently provides an architecture path and measurement gates, not a
fault-tolerant logical qubit implementation.
