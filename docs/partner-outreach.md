# Partner Outreach Brief

## Short Email

Subject: Open photonic QC simulation package seeking independent validation

Hello,

I am maintaining OQP-HRM, an open simulation-first photonic quantum-computer
design package. It is not a build-ready chip. The current package has accepted
Node Alpha 20/60 2D candidates for the coupler, MZI, phase shifter, and truth
switch, plus a generated generic GDS and explicit evidence gates for foundry,
hardware, and lab validation.

The useful ask is narrow: could your group review one part of the package and
tell us which assumption would fail first in a real photonics flow?

Key artifacts:

- `reports/node-alpha/value-upgrade-20260502/high-resolution-robustness-report.json`
- `reports/node-alpha/value-upgrade-20260502/yield-improvement-report.json`
- `reports/node-alpha/gds-path/gds-audit.json`
- `reports/node-alpha/qc-path/sparameter-audit.json`
- `docs/30-minute-reproduction.md`

Current claim boundary: simulation package only; no prototype, no tapeout
readiness, no hardware fault-tolerance claim.

## Reviewer Ask Options

- Device-metric review.
- Generic GDS to PDK gap review.
- S-parameter replacement plan.
- Testchip yield stress review.
- Fault-tolerance assumption review.

## Evidence Snapshot

- High-resolution status: `all_core_devices_high_resolution_accepted`
- Accepted devices: `coupler, mzi, phase-shifter, truth-switch`
- Deterministic system yield: `1.0`
- Partner diligence readiness: `100 / 100`
- Prototype status: `not_prototype_ready`
- Highest blocker: `No foundry-calibrated S-parameter compact models are attached to core devices.`
