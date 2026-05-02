# Grant Concept Note

## Project

OQP-HRM Foundry-Validation Path for a Heralded Photonic Quantum-Computer
Testchip

## Funding Target

Order-of-magnitude non-dilutive target: `50000` to `300000`
USD/EUR equivalent, with a midpoint around `150000`.

## Problem

The repository has a reproducible simulation package, but the value is capped by
missing foundry-calibrated S-parameters, PDK signoff, and measured testchip data.
The current deterministic testchip yield stress passes with system yield
`1.0`, but that remains a simulated
tolerance-grid result rather than wafer statistics.

## Objective

Convert the current Node Alpha simulation package into a foundry-reviewable and
measurement-ready testchip package without claiming full quantum-computer
prototype readiness.

## Work Packages

1. Independent 3D/MPB/S-parameter review of four core device candidates.
2. Foundry PDK mapping and first DRC/LVS gap report for the generic GDS.
3. Compact-model replacement for virtual S-parameters.
4. Testchip measurement plan for source, detector, package, and feed-forward
   gates.
5. Hardware-calibrated noise model replacing synthetic syndrome assumptions.

## Success Criteria

- `sparameter-audit` accepts foundry-calibrated models for all four core devices.
- `gds-audit` is tied to a versioned foundry PDK and DRC/LVS report.
- `fault-tolerance-audit` receives hardware-calibrated noise data.
- Prototype readiness remains blocked unless evidence actually exists.

## Current De-Risked Base

- High-resolution device closure: `all_core_devices_high_resolution_accepted`
- Deterministic yield improvement multiplier: `41.666666666666664`
- Report-index missing artifacts: `0`
