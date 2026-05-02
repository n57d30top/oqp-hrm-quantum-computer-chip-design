# OQP-HRM Architecture Overview

OQP-HRM is a photonic coprocessor architecture for experimenting with heralded reset
mesh computation. The current implementation is a simulation-first stack: blueprints
describe a mesh, the CLI validates it with Strawberry Fields, and sweeps rank candidate
microarchitectures by loss, yield, crosstalk, latency, and connectivity.

## Layers

1. Blueprint layer: YAML/JSON device and metric declarations.
2. Topology layer: mode graph and MZI pairing construction.
3. Simulation layer: Gaussian Strawberry Fields validation now, MEEP/FDTD later.
4. Scoring layer: architecture score and champion selection.
5. Control layer: future feed-forward ISA and runtime.
6. Layout layer: future GDS/PDK export path.

## Current Champion

The reference champion uses 36 optical modes, 24 MZI operations, a pairing stride of 3,
and a 70.5% heralding yield. The attenuation loss score maps to a total mesh path loss
near 1.49 dB and an effective per-stage loss near 0.37 dB when normalized over four
component stages.
