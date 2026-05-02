# OQP-HRM Feed-Forward v0

Heralded reset requires a classical control plane tightly coupled to the photonic mesh.

## Control Loop

```text
detector event
-> threshold/classify
-> update classical herald bit
-> route/reset instruction becomes active
-> phase/switch setting is applied
```

## Current Model

The current runtime model reports a feed-forward latency budget in nanoseconds. This is
not yet an FPGA/ASIC implementation. It is a timing contract for the next hardware
control layer.

## Required Hardware Artifacts

- Detector timestamp interface.
- Low-latency control logic.
- Phase/switch driver model.
- Optical delay-line budget.
- Calibration loop for drift and thermal cross-talk.
