# Partner Outreach Brief

## Short Email

Subject: Open photonic QC simulation package seeking independent validation

Hello,

I am maintaining OQP-HRM, an open simulation-first photonic quantum-computer
design package. It is not a build-ready chip. The current package has accepted
Node Alpha 20/60 2D candidates for the coupler, MZI, phase shifter, and truth
switch, public V3 hardening reports, and explicit evidence gates for foundry,
layout signoff, hardware, and lab validation.

The useful ask is narrow: could your group review one part of the package and
tell us which assumption would fail first in a real photonics flow?

Key artifacts:

- `reports/node-alpha/deep-hardening-v3-20260502/device-sweep-deep-hardening-v3.json`
- `reports/node-alpha/deep-hardening-v3-20260502/worst-case-corner-sweep-report.json`
- `reports/node-alpha/deep-hardening-v3-20260502/scaled-layout-envelope-report.json`
- `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.json`
- `reports/node-alpha/qc-path/sparameter-audit.json`
- `docs/30-minute-reproduction.md`

Current claim boundary: simulation package only; no prototype, no tapeout
readiness, no hardware fault-tolerance claim.

## Reviewer Ask Options

- Device-metric review.
- Generic layout envelope to PDK gap review.
- S-parameter replacement plan.
- Testchip yield stress review.
- Fault-tolerance assumption review.

## Evidence Snapshot

- High-resolution status: `all_core_devices_high_resolution_accepted`
- Accepted devices: `coupler, mzi, phase-shifter, truth-switch`
- Public Deep-Hardening V3 score: `110 / 110`
- Public max envelope: `760` physical modes / `380` logical dual-rail qubits
- Partner diligence readiness: `100 / 100`
- Prototype status: `not_prototype_ready`
- Highest blocker: `No foundry-calibrated S-parameter compact models are attached to core devices.`
