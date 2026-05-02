# OQP-HRM Non-Gaussian Resource Model

The architecture requires non-Gaussian resources because linear MZI/phase meshes do not
provide universal quantum computing by themselves.

Required resource families:

- Indistinguishable single-photon sources or equivalent non-Gaussian state injection.
- Photon-number resolving detectors.
- Ancilla/resource-state factory for heralded fusion or KLM-style gates.
- Multiplexing strategy to route around failed heralded events.
- Calibration loops for brightness, indistinguishability, detector dark counts, and timing.

`oqp resource-model` emits the current source, detector, and ancilla requirements as a
machine-readable gap report.
