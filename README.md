# OQP-HRM Design Package

Simulation-only design dossier for the Open Quantum Photonics Heralded Reset
Mesh (OQP-HRM) Node Alpha architecture.

This repository contains design material only. It does not contain the simulator
implementation, generated reports, graph outputs, caches, test code, foundry
data, hardware measurements, DRC/LVS evidence, or tapeout material.

## Licence

This design package is licensed under the Creative Commons
Attribution-NonCommercial 4.0 International licence.

- Licence file: `licence.md`
- SPDX identifier: `CC-BY-NC-4.0`
- Legal code: https://creativecommons.org/licenses/by-nc/4.0/legalcode

The licence applies to the design documentation, architecture descriptions,
blueprints, and other non-software design materials in this package.

## Claim Boundary

All performance numbers below are Node Alpha simulation, analytical-surrogate,
or consistency-audit metrics. They are not measured chip data.

This package does not claim:

- build-ready quantum computer
- foundry-calibrated S-parameters
- measured wafer/device performance
- DRC/LVS-clean layout
- foundry-clean tapeout
- prototype readiness
- hardware feed-forward verification
- hardware-calibrated fault tolerance
- commercial product readiness

## Repository Contents

```text
README.md
licence.md
architecture/
docs/
hardware/
  Heralded_Reset_Mesh_Blueprint.yaml
  Heralded_Reset_Mesh_V1_Champion.json
```

The full simulator, tests, reports, and generated artifacts remain outside this
design-only repository.

## Current Maximum Design Point

Final Node Alpha hardening state: Deep-Hardening V3 Max-Out.

| Metric | Value |
| --- | ---: |
| Completion audit | `complete` |
| Deep-hardening score | `110 / 110` |
| Internal consistency checks | `11 / 11` |
| Physical modes | `760` |
| Logical dual-rail qubits | `380` |
| Interferometers at max point | `507` |
| Estimated layout area | `17.979962 mm^2` |
| Area target `<22 mm^2` | `pass` |
| Stretch area target `<18 mm^2` | `pass` |
| Route-length reduction | `89.831377%` |
| Effective optical package ports | `96` |
| Effective electrical package pads | `176` |
| Foundry-calibrated S-parameters | `0 / 4` |
| Prototype ready | `false` |
| Tapeout ready | `false` |
| Hardware measured | `false` |

## Max-Qubit Scaling Envelope

The 760-mode / 380-logical-qubit point is the largest closed local stretch
envelope. The next tested step, 768 modes / 384 logical qubits, is rejected by
both area and optical-port ceilings.

| Physical modes | Logical qubits | Interferometers | Area `mm^2` | Optical ports | Electrical pads | Route reduction | Status |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `704` | `352` | `469` | `15.954386` | `90` | `160` | `89.775499%` | pass |
| `712` | `356` | `475` | `16.253798` | `90` | `160` | `89.784429%` | pass |
| `760` | `380` | `507` | `17.979962` | `96` | `176` | `89.831377%` | pass |
| `768` | `384` | `512` | `18.265349` | `100` | `176` | `89.838417%` | no-go |

No-go reasons for 768 modes:

- `area_at_or_above_18mm2_stretch`
- `effective_optical_package_ports_above_review_ceiling`

## Fusion Performance

Fusion numbers are simulation-model outputs. The `1.0` success value is the
model cap under the current normalized useful-flux surrogate; it is not a
measured deterministic hardware claim.

| Metric | Value |
| --- | ---: |
| Best candidate | `mzi_raw_hardened_node_alpha` |
| Nominal fusion success | `1.0` |
| Nominal fusion process fidelity | `0.9999975000000001` |
| Upgraded source/detector fusion success | `1.0` |
| Upgraded source/detector process fidelity | `0.9999975000000001` |
| Stretch fast-path fusion success | `1.0` |
| Stretch fast-path process fidelity | `0.9999975000000001` |
| Stretch fast-path latency in fusion row | `1.8 ns` |
| MZI useful transmission | `2.465` |
| MZI insertion loss | `0.0012 dB` |
| MZI crosstalk ratio | `0.000002` |
| MZI reflection ratio | `0.000004` |
| Nominal target met | `true` |
| Stretch target met | `true` |

## Truth-Switch Performance

Raw Truth-Switch values are used. The compensated candidate is not substituted
for raw closure.

| Metric | Value |
| --- | ---: |
| Best raw crosstalk ratio | `0.0023` |
| Best raw crosstalk percent | `0.23%` |
| Best raw reflection ratio | `0.00004` |
| Best raw reflection percent | `0.004%` |
| Raw strict target met | `true` |
| Raw stretch target met | `true` |
| Candidate count searched | `1394` |
| Derived compensated strict target met | `false` |
| Crosstalk gap to V3 target | `0.0` |
| Reflection gap to V3 target | `0.0` |

Targets closed:

- raw crosstalk `<0.30%`
- stretch crosstalk `<0.25%`
- raw reflection `<0.008%`
- stretch reflection `<0.005%`

## Virtual S-Parameter Acceptance

Virtual S-parameter acceptance is a simulator consistency gate only. Foundry
promotion remains blocked.

| Metric | Value |
| --- | ---: |
| Required virtual devices | `4` |
| Accepted virtual devices | `4` |
| Foundry-calibrated device count | `0` |
| All foundry models accepted | `false` |
| Max virtual crosstalk ratio | `0.0023` |
| Max virtual crosstalk percent | `0.23%` |
| Max virtual reflection ratio | `0.00004` |
| Max virtual reflection percent | `0.004%` |
| Below `0.30%` crosstalk | `true` |
| Below `0.25%` crosstalk | `true` |
| Below `0.008%` reflection | `true` |
| Below `0.005%` reflection | `true` |
| Ready for foundry claim | `false` |

## Fault-Tolerance And 1e-9 Envelope

The 1e-9 envelope is an analytical error-budget result, not hardware-calibrated
fault-tolerance evidence.

| Metric | Value |
| --- | ---: |
| 1e-8 logical-error target met | `true` |
| 1e-9 logical-error target met | `true` |
| Recommended distance for 1e-8 | `41` |
| Recommended distance for 1e-9 | `61` |
| Max single-axis loss at 1e-9 | `0.6386042363009726 dB` |
| Min single-axis detector efficiency at 1e-9 | `0.7720932366132679` |
| Detector-efficiency requirement percent | `77.20932366132679%` |
| Max single-axis phase error at 1e-9 | `0.27953436592410935 rad` |
| Max single-axis feed-forward latency at 1e-9 | `551.976232128157 ns` |
| Hardening margin targets met | `true` |
| Stress scenario still fails targets | `false` |

## Joint Error Budget

| Metric | Value |
| --- | ---: |
| Profile count | `6` |
| 1e-8 joint budget pass | `true` |
| 1e-9 joint budget pass | `true` |
| Balanced 1e-9 logical error | `1.4711041659587303e-13` |
| Balanced 1e-9 reserve | `0.0006837202901601963` |
| Balanced additional loss | `0.12042878247293007 dB` |
| Balanced detector efficiency | `0.9544186473226536` |

## Budget Optimizer

| Metric | Value |
| --- | ---: |
| Optimized profile count at 1e-9 | `8442` |
| Best balanced logical error at 1e-9 | `1.4711041659587364e-13` |
| Best balanced reserve at 1e-9 | `0.0006837202901601959` |
| Best balanced used budget fraction | `0.7500000000000001` |
| Detector-relaxed minimum efficiency | `0.8404652656292875` |
| Loss-relaxed max additional loss | `0.4369747808462235 dB` |
| Latency-relaxed max feed-forward | `387.88336248970995 ns` |

## Throughput And Logical Cycles

The attempt rate is deliberately capped and not inflated.

| Metric | Value |
| --- | ---: |
| Max upper-bound fusion attempts/s | `200000000.0` |
| Max upper-bound heralded events/s | `200000000.0` |
| Max upper-bound logical cycles/s | `8695652.173913043` |

## Timing And Decoder

Fast-path feed-forward and full decoder evidence are kept separate. The full
decoder is not claimed to run in the few-ns feed-forward path.

| Metric | Value |
| --- | ---: |
| Best fast-path profile | `v3_sub_1p3ns_fast_path_target` |
| Best fast-path latency | `1.17 ns` |
| Passing timing profiles | `3 / 4` |
| 1e-9 timing closed in simulation | `true` |
| Full decoder separated from fast path | `true` |
| Full decoder excluded from feed-forward window | `true` |
| Hardware feed-forward verified | `false` |
| Toy decoder target count | `2` |
| 1e-9 toy full-decoder latency | `12.732638863577915 ns` |
| Below 15 ns decoder target | `true` |
| Below 50 ns decoder target | `true` |
| Production decoder ready | `false` |
| Sampled evidence sufficient for 1e-9 claim | `false` |

## Stress, Corner, And Monte-Carlo Robustness

| Metric | Value |
| --- | ---: |
| Uniform 1e-9 stress scale | `1.0` |
| Combined stress point passes | `true` |
| Worst-case stress point passes | `true` |
| Recovered 1e-9 logical error | `2.7433786406436603e-21` |
| Corner count per device | `1875` |
| Worst-case corner targets pass | `true` |
| Corner fusion success pass | `true` |
| Corner fusion fidelity pass | `true` |
| Corner threshold passes 1e-9 | `true` |
| Monte-Carlo samples | `512` |
| Monte-Carlo pass count | `512` |
| Monte-Carlo failure count | `0` |
| Monte-Carlo pass fraction | `1.0` |
| MC worst Truth-Switch crosstalk | `0.002988889897904043` |
| MC worst Truth-Switch reflection | `0.00005272849519864322` |
| MC worst logical error | `5.0550495965104103e-48` |
| Limiting parameter | `crosstalk` |

## Sensitivity Ranking

The deterministic Monte-Carlo tail analysis identifies which perturbations
damage the design fastest.

| Rank | Parameter | Output metric | Impact score |
| ---: | --- | --- | ---: |
| `1` | `crosstalk` | `truthSwitchCrosstalkRatio` | `0.0005162248018896393` |
| `2` | `reflection` | `truthSwitchReflectionRatio` | `0.000009640483486706118` |
| `3` | `phase` | `logicalErrorRate1e9Distance161` | `2.2078091704581376e-49` |
| `4` | `loss` | `logicalErrorRate1e9Distance161` | `1.9293000103237334e-49` |
| `5` | `detector` | `logicalErrorRate1e9Distance161` | `1.3261221619804452e-49` |
| `6` | `latency` | `logicalErrorRate1e9Distance161` | `1.0658270427227773e-49` |

Engineering priority remains: crosstalk first, reflection second, then phase,
loss, detector efficiency, and latency.

## Pareto And Candidate Search

| Metric | Value |
| --- | ---: |
| Pareto-front candidate count | `545` |
| Truth-Switch raw closure candidates | `1394` |
| Budget optimizer candidates at 1e-9 | `8442` |
| Scaled layout target rows | `20` |

The Pareto front covers coupler, MZI, phase-shifter, and Truth-Switch device
families.

## Baseline Node Alpha Reference

The V3 results above are measured against the original Node Alpha design
baseline.

| Baseline metric | Value |
| --- | ---: |
| Physical modes | `36` |
| Logical dual-rail qubits | `18` |
| Interferometers | `24` |
| Chip area | `6.3574 mm^2` |
| Chip size | `4780.0 um x 1330.0 um` |
| Heralding yield | `0.705` |
| Baseline fusion success | `0.8178362931958357` |
| Baseline fusion process fidelity | `0.9955578964118097` |
| Baseline feed-forward latency | `5.0 ns` |
| Baseline threshold distance | `15` |
| Baseline logical error rate | `2.5617154643831186e-07` |
| Modes per correction cycle | `8100` |
| Deterministic system-yield estimate | `1.0` |

## Readiness Matrix

| Claim | Status |
| --- | --- |
| Simulation package complete | `true` |
| Local performance hardening complete | `true` |
| Layout computable in review model | `true` |
| Foundry S-parameters ready | `false` |
| Hardware-measured device data available | `false` |
| Hardware feed-forward verified | `false` |
| Production decoder ready | `false` |
| DRC run | `false` |
| LVS run | `false` |
| Tapeout ready | `false` |
| Prototype ready | `false` |

## Design Files

- `hardware/Heralded_Reset_Mesh_Blueprint.yaml`: parametric OQP-HRM blueprint.
- `hardware/Heralded_Reset_Mesh_V1_Champion.json`: baseline champion
  configuration.
- `architecture/`: architecture, encoding, microarchitecture, feed-forward,
  resource, control, and roadmap documents.
- `docs/`: partner-review, reproduction, validation, grant, and data-room
  documents.
- `licence.md`: CC BY-NC 4.0 licence notice.

## Interpretation

The current honest simulation maximum is 760 physical modes / 380 logical
dual-rail qubits under the 18 mm^2 stretch envelope. The next tested step,
768 physical modes / 384 logical qubits, is blocked by area and optical package
ports. Further improvement should target optical port banking and crosstalk
first; increasing qubit count without closing those gates would be cosmetic.
