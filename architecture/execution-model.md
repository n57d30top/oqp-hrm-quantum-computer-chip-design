# OQP-HRM Execution Model v0

Execution is shot-based. A compiled OQP program repeats the same photonic sequence many
times, collects classical measurement results, and decodes the batch.

## Shot Flow

```text
prepare optical modes
-> apply MZI/phase mesh
-> measure selected modes
-> wait for heralding decision
-> reset or route downstream modes
-> record classical result
-> decode classical results into logical readout
```

## Runtime State

- Optical state: modes, phases, and mesh settings.
- Classical state: detector bits, herald bits, route/reset conditions.
- Calibration state: phase offsets, source brightness, detector baselines.
- Decode state: encoding-specific result mapping from measured modes to logical bits.

## Timing

Feed-forward latency is modeled explicitly in `oqp runtime-trace`. Hardware execution
requires detector readout, classical decision logic, and phase/switch update to fit
inside the optical delay budget.
