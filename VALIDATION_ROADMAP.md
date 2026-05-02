# Validation Roadmap

This roadmap turns the public OQP-HRM package from a simulation-only design
dossier into an externally reviewable engineering package. It is intentionally
framed as validation work, not as a claim of working hardware.

## Current Status

- Public design, simulator, tests, and generated V3 reports are available.
- The Deep-Hardening V3 Max-Out completion audit is `complete`.
- The maximum closed local envelope is `760` physical modes / `380` logical
  dual-rail qubits under the `18 mm^2` stretch area gate.
- The next tested point, `768` physical modes / `384` logical qubits, is a
  No-Go row due area and optical-package-port ceilings.
- Foundry-calibrated S-parameters remain `0 / 4`.
- Prototype readiness, tapeout readiness, and hardware measurement status
  remain `false`.

## Validation Gates

| Gate | Target evidence | Current status |
| --- | --- | --- |
| Reproducible simulator | `oqp/`, `tests/`, `pyproject.toml`, and generated reports | public |
| Unit tests | `python3 -m unittest discover -s tests -v` | `48` tests expected |
| V3 report hashes | `ARTIFACTS.md` plus JSON reports | public |
| Independent code review | reviewer notes or issue comments | open |
| Independent photonics review | device-model review notes | open |
| Foundry PDK review | versioned PDK manifest | missing |
| DRC/LVS | clean reports or explicit waivers | missing |
| Foundry S-parameters | calibrated compact models for 4 core devices | missing |
| Package/control review | source, detector, IO, driver, and feed-forward evidence | missing |
| Testchip/device measurement | measured device/testchip data | missing |
| Fault-tolerance review | hardware-calibrated noise plus decoder benchmark | missing |

## Immediate Work Items

1. Run the published reproduction command on a clean machine.
2. Review `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.json`.
3. Verify the checksums in `ARTIFACTS.md`.
4. Inspect the No-Go row in `max-qubit-no-go-map-report.json`.
5. Open technical review issues for crosstalk, reflection, fusion fidelity,
   layout envelope, package ports, timing, and decoder assumptions.

## External Review Questions

- Are the normalized useful-transmission assumptions physically defensible for
  each device row?
- Which Truth-Switch geometry perturbation most plausibly closes crosstalk in a
  real 3D/MPB/FDTD model?
- Is the `v3_maxout_pitch_floor_review` layout profile a plausible review
  floor, or should it be rejected as too dense?
- What minimum foundry-S-parameter evidence is required before any compact-model
  claim can be made?
- What measurement plan would validate or falsify the `760/380` envelope most
  cheaply?

## Non-Goals

- Do not describe this package as a built quantum computer.
- Do not describe this package as foundry-ready.
- Do not describe this package as tapeout-ready.
- Do not describe this package as prototype-ready.
- Do not substitute simulation pass/fail metrics for measured hardware data.
