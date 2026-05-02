# OQP-HRM Encoding v0

## Primary Encoding

The first architecture target is dual-rail path encoding:

```text
logical |0> = photon in rail A
logical |1> = photon in rail B
```

Each logical qubit consumes two optical modes. A 36-mode mesh therefore has an initial
capacity of 18 logical dual-rail qubits before reserving modes for ancilla, heralding,
and calibration.

## Secondary Encoding

Continuous-variable GKP modes are tracked as a future route. They require GKP state
preparation, repeated syndrome extraction, and non-Gaussian resource injection.

## Non-Gaussian Requirement

Gaussian transformations alone are not enough for universal quantum computing. The
architecture therefore treats photon-number detection, single-photon sources, GKP
states, or magic-state injection as required resources.
