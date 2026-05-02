# OQP-HRM No-Budget Partner Package

## Position

OQP-HRM is a reproducible simulation-first photonic quantum-computer design
package. With no cash budget, the correct objective is not fabrication. The
objective is to make the work cheap to inspect, easy to reproduce, and specific
enough that a university group, foundry program, or quantum-photonics lab can
decide whether to contribute validation effort.

Do not claim this is a build-ready quantum computer. The strongest accurate
claim is:

> OQP-HRM has a Node Alpha simulation package with accepted 2D high-resolution
> candidates for the four core photonic devices, an analytical threshold path,
> generated generic GDS, virtual compact-model placeholders, and explicit
> external evidence gates for foundry, hardware, and lab validation.

## One-Page Summary

Project: Open Quantum Photonics Heralded Reset Mesh (OQP-HRM)

Current asset class: simulation-closed engineering package, not prototype
hardware.

Core simulated devices:

| Device | 20/60 candidate | Crosstalk | Reflection | Status |
| --- | --- | ---: | ---: | --- |
| Coupler | `coupler_gap0p12_len4p5_phi0_w0p5` | `0.01777` | `0` | accepted in Node Alpha 2D sweep |
| MZI | `mzi_gap0p22_len3_phi0_w0p5` | `0.03481` | `2.60e-7` | accepted in Node Alpha 2D sweep |
| Phase shifter | `phase-shifter_gap0p22_len3_phi0_w0p5` | `0.03481` | `2.60e-7` | accepted in Node Alpha 2D sweep |
| Truth switch | `truth-switch_gap0p08_len8_phi0_w0p4` | `0.02867` | `0.00443` | accepted in Node Alpha 2D sweep |

Other current evidence:

- Threshold champion logical error estimate: `2.56e-7`.
- Synthetic syndrome dataset: `10,000` deterministic events.
- GDS: generated and layout-computable.
- Virtual S-parameter files: 4/4 present and hash-verified.
- Prototype readiness: `1/9` criteria complete.
- Testchip yield stress: system yield estimate `0.024`, not robust enough.

## What A Partner Can Validate Without Paying Us

The highest-value no-cash asks are:

1. Run an independent review of the assumptions and report whether the
   simulation gates are meaningful.
2. Re-run a subset of the device sweeps with independent FDTD/MPB tooling.
3. Map the generic GDS to a real silicon-photonics PDK and report the first DRC
   and LVS blockers.
4. Replace virtual S-parameters with foundry compact-model or wafer-measured
   S-parameters for the four core devices.
5. Run a small testchip feasibility review: source/detector coupling, pads,
   packaging, thermal phase-shifter feasibility, and feed-forward timing.
6. Provide hardware-calibrated loss/noise assumptions so the fault-tolerance
   audit can stop using synthetic syndrome data.

## What We Can Still Do With Zero Cash

- Increase sweep breadth on local or donated compute.
- Improve report indexing, hashes, diagrams, and reproduction docs.
- Prepare a preprint-quality technical manuscript.
- Make the testchip package easier for a foundry or university group to audit.
- Add issue templates and validation tasks for open-source contributors.
- Keep all real-world readiness flags blocked until evidence exists.

## What We Cannot Close With Zero Cash

- Foundry-specific PDK signoff.
- Foundry DRC/LVS closure.
- Wafer-calibrated S-parameter compact models.
- Photon source, detector, package, control, calibration, or feed-forward
  hardware evidence.
- A fabricated testchip.
- Patent filing or formal freedom-to-operate opinion.

## 90-Day Zero-Cash Plan

Day 0-7:

- Re-run the local value package.
- Publish report index and hashes.
- Ask three technical reviewers for written assumptions feedback.

Day 8-30:

- Convert the preprint outline into a 6-10 page manuscript.
- Add figures from the report-summary notebook.
- Open validation issues with small, well-scoped tasks.

Day 31-60:

- Contact university photonics groups with the one-page summary and exact
  validation asks.
- Ask foundry programs whether a generic-GDS-to-PDK mapping review is possible
  without paid tapeout.
- Ask open-source photonics contributors to inspect the device metrics and GDS
  manifest.

Day 61-90:

- Incorporate review comments.
- Update high-resolution sweeps only where reviewers find weak assumptions.
- Freeze a partner-review tag with report index hashes and reproduction steps.

## Artifact Map

- Report index: `reports/node-alpha/report-index.json`
- No-budget readiness: `reports/node-alpha/no-budget-package/no-budget-readiness.json`
- Value package: `reports/node-alpha/value-upgrade-20260502/value-upgrade-report.json`
- High-resolution robustness: `reports/node-alpha/value-upgrade-20260502/high-resolution-robustness-report.json`
- GDS audit: `reports/node-alpha/gds-path/gds-audit.json`
- Fault-tolerance audit: `reports/node-alpha/qc-path/fault-tolerance-audit.json`
- S-parameter audit: `reports/node-alpha/qc-path/sparameter-audit.json`
- Reproduction guide: `docs/30-minute-reproduction.md`
- Preprint outline: `docs/preprint-outline.md`
- Validation issues: `docs/open-validation-issues.md`
