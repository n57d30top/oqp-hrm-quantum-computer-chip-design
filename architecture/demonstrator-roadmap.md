# OQP-HRM Demonstrator Roadmap

## Phase 1: Device Cell

Tune MZI, coupler, phase-shifter, and truth-switch cells until FDTD shows low
reflection and useful mode-resolved transmission.

Current command surface:

```bash
oqp eigenmode-device-run hardware/Heralded_Reset_Mesh_Blueprint.yaml --device mzi --out runs/mzi-eigenmode-fdtd.json
oqp device-sweep hardware/Heralded_Reset_Mesh_Blueprint.yaml --devices mzi,coupler,truth-switch --out runs/device-sweep
```

## Phase 2: Primitive

Build a two-qubit heralded fusion primitive from the best device cells. Validate
success probability, loss, crosstalk, and timing.

Current command surface:

```bash
oqp fusion-primitive hardware/Heralded_Reset_Mesh_Blueprint.yaml --device-report runs/mzi-eigenmode-fdtd.json --out runs/fusion-primitive.json
```

## Phase 3: Resource State

Add source, detector, ancilla, multiplexing, and feed-forward models. Produce resource
estimates per logical qubit and per correction cycle.

## Phase 4: Fault Tolerance

Select a code, generate syndrome extraction circuits, implement a decoder, and sweep
thresholds over physical error parameters.

Current command surface:

```bash
oqp threshold-sweep hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/threshold-sweep
```

## Phase 5: Hardware Readiness

Select a foundry PDK, implement GDS cells, pass DRC/LVS, define packaging and control
electronics, and run hardware-in-the-loop calibration.

Current command surface:

```bash
oqp tapeout-readiness hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/tapeout-readiness.json
```
