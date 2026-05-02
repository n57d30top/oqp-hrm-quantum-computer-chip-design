# OQP-HRM ISA v0

This is the initial instruction set sketch for a simulated heralded reset mesh
processor. It is intentionally minimal so the simulator, compiler, and validation
reports can converge on one execution model.

## Registers and Objects

- `mode`: optical mode index.
- `detector`: measurement channel identifier.
- `classical_bit`: feed-forward condition result.
- `shot`: one repeated execution of a program.

## Instructions

```text
PREPARE mode state
ROUTE mode_a mode_b -> component
MZI mode_a mode_b theta phi
PHASE mode angle
LOSS mode transmission
MEASURE mode basis -> classical_bit
HERALD_WAIT detector condition -> classical_bit
RESET mode target_state when classical_bit
RESULT_DECODE encoding classical_bits -> logical_bits
```

## Execution Model

Programs execute as repeated shots. Optical operations transform modes, measurement
produces classical feed-forward state, and reset/route instructions condition later
mesh settings. The first simulator target is Strawberry Fields Gaussian validation;
future targets include MEEP/FDTD geometry validation and hardware control traces.

## Implemented Trace Gate

`oqp compile` emits `open-quantum.compiler-trace.v1`.
`oqp runtime-trace` emits `open-quantum.runtime-trace.v1`.
