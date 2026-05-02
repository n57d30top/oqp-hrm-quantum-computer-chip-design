# Preprint Outline: OQP-HRM Simulation-Closed Photonic QC Design

## Working Title

OQP-HRM: A Reproducible Simulation-Closed Heralded Photonic Quantum-Computer
Design Package With Explicit Foundry and Hardware Evidence Gates

## Abstract Draft

We present OQP-HRM, an open simulation-first design package for a heralded
photonic quantum-computer architecture. The package combines a dual-rail
photonic architecture model, high-resolution Node Alpha 2D FDTD device sweeps,
generic GDS generation, virtual compact-model placeholders, synthetic decoder
datasets, threshold/resource reports, and explicit evidence gates for foundry,
hardware, and laboratory validation. Current simulations identify accepted
20/60 candidates for the coupler, MZI, phase shifter, and truth switch under
the repository's first-pass acceptance metrics. The design is not claimed as a
fabrication-ready prototype: foundry-calibrated S-parameters, PDK DRC/LVS,
measured source/detector/package/control evidence, and hardware-calibrated
noise data remain hard blockers.

## Claim Boundary

Claims to make:

- Reproducible simulation package.
- Accepted 2D high-resolution local candidates for four core devices.
- Generic GDS milestone with explicit signoff blockers.
- Analytical threshold path with synthetic decoder data.
- Evidence contract for real prototype readiness.

Claims not to make:

- Build-ready quantum computer.
- Foundry-clean tapeout.
- Hardware-demonstrated primitive.
- Hardware fault tolerance.
- Patentability or freedom-to-operate.

## Proposed Sections

1. Introduction
2. Related work and model positioning
3. OQP-HRM architecture
4. Device-sweep methodology
5. High-resolution device results
6. Testchip and virtual compact-model package
7. Threshold, decoder, and resource evidence
8. GDS and prototype evidence gates
9. Limitations and partner validation path
10. Reproducibility package

## Key Results To Report

| Result | Current value |
| --- | --- |
| High-resolution robustness status | `all_core_devices_high_resolution_accepted` |
| Accepted devices at 20/60 | coupler, MZI, phase-shifter, truth-switch |
| Threshold champion logical error estimate | `2.56e-7` |
| Synthetic syndrome events | `10,000` |
| Virtual S-parameter files | 4/4 present, hash verified |
| Prototype readiness | 1/9 criteria |
| Testchip system yield estimate | `0.024` |
| GDS state | generated, layout-computable, not tapeout-ready |

## Figure Plan

- System block diagram of the OQP-HRM evidence gates.
- Device table with 20/60 metrics.
- Bar chart: completed vs blocked readiness gates.
- Testchip yield stress plot.
- Artifact dependency graph from the report index.
- Partner validation path: simulation artifact to foundry/lab evidence.

## Related Work Anchors

- Knill, Laflamme, and Milburn introduced efficient linear-optical quantum
  computation with photons, linear optics, measurement, and feed-forward:
  https://www.nature.com/articles/35051009
- Browne and Rudolph proposed resource-efficient linear optical quantum
  computation based on fusion-style operations:
  https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.95.010501
- Fusion-based quantum computation frames universal computation around small
  entangled resource states and entangling measurements:
  https://arxiv.org/abs/2101.09310
- Integrated quantum photonics reviews show why sources, manipulation,
  detection, packaging, and heterogeneous integration remain central hardware
  challenges:
  https://www.nature.com/articles/s41566-019-0532-1

## Reviewer Checklist

- Are the acceptance metrics sufficient for a first-pass 2D device gate?
- Which metrics need MPB/S-parameter extraction before publication?
- Is the truth-switch model physically plausible enough for a preprint, or
  should it be framed only as a placeholder switching-cell hypothesis?
- Does the threshold section overstate synthetic decoder evidence?
- Are the GDS and testchip claims clearly separated from tapeout readiness?
- Which validation task is cheapest for an external partner to reproduce?
