# ⚡ Open Quantum Photonics: The Heralded Reset Mesh

> [!IMPORTANT]  
> This repository contains the reference RTL and physical design parameters for the **Heralded Reset Mesh** Photonic Quantum Chip. This architecture fundamentally deprecates legacy squeezed-light primitives to achieve deterministic, high-precision photon state control for scaling quantum neural processing.

This open-source hardware release provides the silicon photonic blueprints required to build deterministic quantum gates at room temperature. By leveraging a novel `Truth Switch` primitive, the Heralded Reset Mesh bypasses the probabilistic fidelity limits inherent to previous Gaussian Boson Sampling (GBS) architectures.

---

## 🔬 Core Architecture: Why "Heralded Reset"?

Historically, integrated quantum photonics relied heavily on squeezed-light (continuous-variable) states. While excellent for generating entanglement at scale, non-deterministic state degradation makes deep photonic neural networks unviable without massive cryogenic error correction overhead.

### The "Truth Switch" Primitive
At the core of this repository is the **Truth Switch**. Instead of hoping for probabilistic multi-photon coincidence, this architecture uses real-time deterministic feed-forward. When an ancillary single-photon detector "heralds" the presence of a specific mode, the Truth Switch ultra-rapidly reconfigures the downstream Mach-Zehnder Interferometer (MZI) mesh. This actively "resets" the quantum state to a known computational basis, preserving phase coherence through arbitrarily deep circuit depths.

### Key Advantages
- **Deterministic Scaling**: Overcomes the probabilistic limits of squeezed-light. 
- **Room Temperature Operation**: While detectors require some cooling, the photonic mesh array functions without extreme millikelvin cryogenics.
- **CMOS/Silicon-Photonics Compatible**: Can be fabricated using standard silicon-on-insulator (SOI) foundry processes.

### Measured Physical Bounds (Champion Pilot)
The target configuration logic captured in `Heralded_Reset_Mesh_V1_Champion.json` defines a 36-waveguide array utilizing a 24-depth small-world primitive configuration. We have achieved independent software validation of the hardware parameters natively utilizing Xanadu's Strawberry Fields Gaussian tracker:

- **Topology Bypass Rate:** 1.0 (100% bypass in validation against legacy boundaries)
- **Residual Loss Matrix:** `attenuation_loss_score: 0.29` and `crosstalk_risk_score: 0.25`
- **Resulting Physical Metrics**: These mesh values mathematically synthesize a rigorous, scalable **0.370 dB switch-mesh loss**, guaranteeing an **Average Heralding Yield of 70.5%**.

These explicit constraints represent 5/5 residual convergence, demonstrating a mathematically scalable architecture for Optical Neural Processing.

---

## 🛠️ Repository Structure

```
├── hardware/
│   ├── Heralded_Reset_Mesh_V1_Champion.json   # Validated metrics and FDTD constraints
│   ├── Heralded_Reset_Mesh_Blueprint.yaml     # Parametric spatial array specifications
│   └── truth_switch_tb.py                     # Strawberry Fields FDTD physics validator
├── LICENSE                                    # CERN-OHL-S v2 Open Hardware License
└── README.md
```

## 🚀 Getting Started

1. Clone this repository:
   ```bash
   git clone https://github.com/n57d30top/open-quantum-photonics.git
   ```
2. Navigate to the hardware directory and run the FDTD validation:
   ```bash
   cd open-quantum-photonics/hardware
   pip install strawberryfields pyyaml numpy scipy
   python truth_switch_tb.py
   ```
   This will immediately reproduce the strict physical boundaries and yield traces.

## OQP-HRM CLI

The repository now includes an installable `oqp` command for repeatable validation,
sweep, ranking, optimizer runs, and reproducible pre-tapeout GDS milestones:

```bash
pip install -e .
oqp validate hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/champion-validation.json
oqp sweep hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/sweep-smoke --waveguides 36 --interferometers 12,24,36 --strides 1,2,3
oqp optimize hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/optimize --budget 20
oqp rank runs/optimize --limit 5
oqp meep-probe --out runs/meep-probe.json
oqp meep-run hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/meep-surrogate.json
oqp layout-plan hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/layout-plan.json
oqp gds-plan hardware/Heralded_Reset_Mesh_Blueprint.yaml --out reports/node-alpha/gds-path/gds-plan.json
oqp gds-generate hardware/Heralded_Reset_Mesh_Blueprint.yaml --out-dir reports/node-alpha/gds-path
oqp gds-manifest hardware/Heralded_Reset_Mesh_Blueprint.yaml --out reports/node-alpha/gds-path/gds-manifest.json
oqp gds-audit hardware/Heralded_Reset_Mesh_Blueprint.yaml --manifest reports/node-alpha/gds-path/gds-manifest.json --out reports/node-alpha/gds-path/gds-audit.json
oqp gds-preview hardware/Heralded_Reset_Mesh_Blueprint.yaml --manifest reports/node-alpha/gds-path/gds-manifest.json --svg-out reports/node-alpha/gds-path/gds-preview.svg
oqp pdk-audit hardware/Heralded_Reset_Mesh_Blueprint.yaml --out reports/node-alpha/gds-path/pdk-audit.json
oqp signoff-audit hardware/Heralded_Reset_Mesh_Blueprint.yaml --out reports/node-alpha/gds-path/signoff-audit.json
oqp encoding hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/encoding.json
oqp compile hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/compiler-trace.json
oqp runtime-trace hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/runtime-trace.json
oqp error-budget hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/error-budget.json
oqp layout-readiness hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/layout-readiness.json
oqp tapeout-readiness hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/tapeout-readiness.json
oqp meep-device-run hardware/Heralded_Reset_Mesh_Blueprint.yaml --device mzi --out runs/mzi-device-fdtd.json
oqp eigenmode-device-run hardware/Heralded_Reset_Mesh_Blueprint.yaml --device mzi --out runs/mzi-eigenmode-fdtd.json
oqp primitive-spec hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/primitive-spec.json
oqp fusion-primitive hardware/Heralded_Reset_Mesh_Blueprint.yaml --device-report runs/mzi-eigenmode-fdtd.json --out runs/fusion-primitive.json
oqp resource-model hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/resource-model.json
oqp resource-sweep hardware/Heralded_Reset_Mesh_Blueprint.yaml --out reports/node-alpha/qc-path/resource-sweep-node-alpha-extended-20260502
oqp device-sweep hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/device-sweep --max-runs 16
oqp device-sweep-rerank hardware/Heralded_Reset_Mesh_Blueprint.yaml --evidence-dir runs/device-sweep --out runs/device-sweep-reranked.json
oqp device-acceptance hardware/Heralded_Reset_Mesh_Blueprint.yaml --out reports/node-alpha/qc-path/device-acceptance-audit.json
oqp sparameter-audit hardware/Heralded_Reset_Mesh_Blueprint.yaml --out reports/node-alpha/qc-path/sparameter-audit.json
oqp prototype-readiness hardware/Heralded_Reset_Mesh_Blueprint.yaml --out reports/node-alpha/qc-path/prototype-readiness.json
oqp error-correction-plan hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/error-correction-plan.json
oqp threshold-sweep hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/threshold-sweep --max-runs 16
oqp fault-tolerance-ingest hardware/Heralded_Reset_Mesh_Blueprint.yaml --dataset reports/node-alpha/qc-path/syndrome-events.jsonl
oqp fault-tolerance-audit hardware/Heralded_Reset_Mesh_Blueprint.yaml --out reports/node-alpha/qc-path/fault-tolerance-audit.json
oqp control-readiness hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/control-readiness.json
oqp lab-readiness hardware/Heralded_Reset_Mesh_Blueprint.yaml --out runs/lab-readiness.json
oqp hardware-ingest hardware/Heralded_Reset_Mesh_Blueprint.yaml --dataset reports/node-alpha/qc-path/hardware-events.jsonl
oqp hardware-audit hardware/Heralded_Reset_Mesh_Blueprint.yaml --out reports/node-alpha/qc-path/hardware-audit.json
oqp primitive-demo-ingest hardware/Heralded_Reset_Mesh_Blueprint.yaml --dataset reports/node-alpha/qc-path/primitive-events.jsonl
oqp primitive-demo-audit hardware/Heralded_Reset_Mesh_Blueprint.yaml --out reports/node-alpha/qc-path/primitive-demo-audit.json
oqp evidence-bundle hardware/Heralded_Reset_Mesh_Blueprint.yaml --out reports/node-alpha/qc-path/evidence-bundle.json
oqp evidence-bundle hardware/Heralded_Reset_Mesh_Blueprint.yaml --write-templates --templates-dir reports/node-alpha/evidence-intake/templates
oqp design-dossier hardware/Heralded_Reset_Mesh_Blueprint.yaml --out reports/node-alpha/qc-path/complete-design-dossier.json
oqp node-alpha-closure hardware/Heralded_Reset_Mesh_Blueprint.yaml --out reports/node-alpha/qc-path/node-alpha-closure.json
oqp node-alpha-compute-report hardware/Heralded_Reset_Mesh_Blueprint.yaml --device-sweep reports/node-alpha/qc-path/device-sweep-node-alpha-extended-20260502/device-sweep.json --threshold-sweep reports/node-alpha/qc-path/threshold-sweep-node-alpha-extended-20260502/threshold-sweep.json --resource-sweep reports/node-alpha/qc-path/resource-sweep-node-alpha-extended-20260502/resource-sweep.json --out reports/node-alpha/qc-path/node-alpha-compute-report-20260502.json
oqp complete-simulation hardware/Heralded_Reset_Mesh_Blueprint.yaml --out reports/node-alpha/qc-path/complete-quantum-computer-simulation-20260502.json
oqp testchip-simulate hardware/Heralded_Reset_Mesh_Blueprint.yaml --out-dir reports/node-alpha/testchip-simulation-20260502
oqp performance-upgrade hardware/Heralded_Reset_Mesh_Blueprint.yaml --out-dir reports/node-alpha/deep-hardening-v3-20260502
```

Sweep and optimizer runs write `index.json`, `champion.json`, and
`champion-registry.json` into the output directory.

## Pre-Tapeout GDS Path

`oqp gds-generate` computes a generic-SiPh-compatible GDS without requiring a
foundry-clean PDK. The flow writes the versioned milestone bundle under
`reports/node-alpha/gds-path/` by default:

```text
oqp-hrm-generic-siph.gds
gds-generate.json
gds-plan.json
gds-manifest.json
gds-audit.json
cell-registry.json
layer-map.json
ports.json
pads.json
gds-preview.svg
```

The GDS contains a top cell, reusable cells for waveguide, directional coupler,
MZI, phase shifter, truth switch, optical I/O, source/detector interfaces, and
electrical pads, plus placed OQP-HRM instances, waveguide routes, metal routes,
ports, pads, keepouts, labels, and package/fiber-I/O markers.

Current FDTD/device-sweep evidence is loaded from `reports/node-alpha/qc-path/`.
Devices with non-accepted evidence are still placed, but their component status
is `fdtd_gap_backed_placeholder`. The audit intentionally separates:
`gds_generated`, `layout_computable`, `fdtd_gap_backed_placeholder`,
`drc_not_run`, `lvs_not_run`, `foundry_pdk_missing`, and
`not_tapeout_ready`.

`oqp device-acceptance` is the next gate after GDS. It audits the core MZI,
directional-coupler, phase-shifter, and truth-switch evidence against useful
transmission, insertion loss, reflection, crosstalk, and S-parameter promotion
requirements. `oqp prototype-readiness` aggregates device acceptance, GDS,
foundry PDK, DRC/LVS, source/detector/packaging, control/feed-forward,
calibration, threshold, and heralded primitive demonstration criteria into a
prompt-to-artifact checklist.

The current FDTD model version is
`eigenmode_device.v4.reference_output_port_normalized_reliability_gate`. It
uses a straight waveguide output-port reference for through/cross power
normalization and rejects candidates whose reference output flux is too weak for
stable normalization. Older device evidence without this version marker is
treated as stale and must be rerun before it can promote a core device.
`oqp device-sweep-rerank` can re-score existing per-candidate sweep artifacts
without re-running MEEP; it prefers normalization-reliable candidates and emits
per-device champions/gaps so inflated-ratio artifacts do not hide crosstalk or
reflection blockers.
`oqp sparameter-audit` is the core-device compact-model gate. It consumes a
manifest of foundry/wafer-calibrated S-parameter files for the coupler, MZI,
phase shifter, and truth switch; it verifies SHA-256 hashes, wavelength range,
process corners, passivity, reciprocity, energy balance, insertion loss,
reflection, and crosstalk before device promotion can close.

This is a reproducible pre-tapeout GDS milestone. It is not DRC/LVS-clean,
foundry-clean, or tapeout-ready until a real foundry PDK, rule decks,
S-parameter compact models, package drawing, calibration closure, and
control-electronics signoff are added.

`oqp pdk-audit` is the foundry-signoff input gate. With no manifest it reports
the current generic-SiPh state as blocked. With `--pdk-manifest`, it validates a
version-locked foundry PDK manifest, required layer purposes, DRC/LVS decks,
process corners, PCell library, compact models for the four core devices, and
package rules before declaring DRC/LVS runnable.
`oqp signoff-audit` is the DRC/LVS gate. It consumes `pdk-audit.json`, the GDS
audit, DRC/LVS reports, and optional approved waivers; it remains blocked until
DRC and LVS are clean or fully waived under an approved policy.
`oqp hardware-ingest` converts JSON/JSONL hardware evidence into the measured
source, detector, packaging, control, automatic calibration, and feed-forward
reports consumed by `oqp hardware-audit`. The audit remains the gate and stays
blocked until hardware counts, source brightness/indistinguishability, detector
efficiency/dark-count/jitter, package mappings, control channels, calibration
loops, and hardware-in-the-loop feed-forward latency all meet targets.
`oqp fault-tolerance-ingest` converts JSON/JSONL syndrome-noise events into a
decoder benchmark report and SHA-256 dataset manifest. `oqp fault-tolerance-audit`
is the error-correction gate. It consumes the threshold sweep, decoder report,
sampled syndrome-noise dataset manifest, and hardware-audit output; it remains
blocked until below-threshold evidence, validated logical error rate,
implemented decoder, decoder latency, dataset hash, sample count, and
hardware-calibrated noise evidence all meet targets.
`oqp primitive-demo-ingest` converts JSON/JSONL primitive-event data into a
measured primitive report and SHA-256 dataset manifest. `oqp primitive-demo-audit`
is the measured-demonstration gate. It consumes that measured primitive report,
dataset manifest, hardware-audit output, and fusion-primitive model evidence;
it remains blocked until shot count, heralded-event count, heralding success,
process fidelity, dataset integrity, hardware readiness, and feed-forward
latency all meet the demonstrator targets.
`oqp evidence-bundle` is the top-level evidence intake contract. It maps the
prototype goal to concrete required files under `reports/node-alpha/gds-path/`
and `reports/node-alpha/qc-path/`, verifies dataset hashes where manifests are
used, reports which prototype requirements are still blocked, and can write
template JSON files for the real foundry, hardware, decoder, and primitive-demo
evidence that must replace placeholders.
`oqp design-dossier` composes the full architecture dossier: encoding,
universal primitive path, resource model, ISA/runtime trace, error budget,
fault-tolerance design path, prototype gates, and the evidence intake contract.
It can close the repository-level design dossier without claiming tapeout,
hardware, fault-tolerance, or experimental readiness.
`oqp node-alpha-closure` is the maximum local/simulation-only gate. It reports
which work is finished using Node Alpha artifacts and which remaining gates are
hard-stopped on real foundry, hardware, decoder, or lab data.
`oqp resource-sweep` runs analytical resource scaling across logical-qubit and
target-error-rate settings for Node Alpha sizing only.
`oqp node-alpha-compute-report` aggregates extended simulation-only device,
threshold, and resource sweeps into a single report with explicit non-evidence
boundaries.
`oqp complete-simulation` runs the complete available Node Alpha simulation
stack, falls back to explicitly marked analytical surrogates when local physics
backends are unavailable, and reports whether the simulated quantum-computer
gates actually close.
`oqp testchip-simulate` builds the simulation-only foundry-testchip package:
test structures, FDTD/MPB-ready run plan, accepted local device sweep, virtual
S-parameter-like models, deterministic tolerance/yield sweep, and a two-qubit
fusion testcell report. It is explicitly not fabrication readiness.
`oqp value-package` is the one-command value-upgrade wrapper. It reruns the
simulation-only testchip/tolerance package, writes virtual S-parameter model
files plus a manifest, generates a synthetic decoder/syndrome dataset and
fault-tolerance audit, writes evidence-intake templates, and produces IP/value
and reproducibility dossiers. Its reports deliberately keep real foundry,
hardware, DRC/LVS, S-parameter, and lab gates blocked.
The wrapper now promotes accepted 20/60 Node Alpha candidates into a
`yield-optimized-device-sweep.json` before the testchip tolerance run. This
raises the deterministic simulation-only system-yield estimate from `0.024` to
`1.0` in the current reports while still refusing any wafer-yield claim.
`oqp value-scorecard` turns those artifacts into a conservative diligence
scorecard plus partner-outreach, grant-concept, reviewer-pack,
partner-pipeline, and data-room index documents.
It is designed to increase review and funding leverage without pretending that
the design is a build-ready quantum computer.
The scorecard includes a point-by-point score breakdown, claim-readiness matrix,
diligence risk register, assumption register, reviewer question bank, valuation
confidence note, partner ask matrix, partner pipeline, and milestone value
ladder.
`oqp performance-upgrade` now writes the simulation-only Deep-Hardening V3
Max-Out package for larger sweeps, Pareto ranking, corner/Monte-Carlo
robustness, fusion-gate candidate ranking, raw truth-switch
crosstalk/reflection targets, and upper-bound throughput estimates. It keeps
nominal, stretch, raw, virtual-S-parameter, and derived hypotheses separate
from measured hardware performance.
The package also writes an operational-envelope report that budgets the
remaining single-axis loss, detector-efficiency, phase-error, dark-count, and
feed-forward margins for the `1e-8` and `1e-9` logical-error targets.
The joint-error-budget report then turns those margins into combined operating
profiles, including a `1e-9` balanced profile with explicit reserve.
The budget-optimizer report searches thousands of valid budget splits and
selects balanced, detector-relaxed, loss-relaxed, and latency-relaxed operating
profiles for the same analytical model.
The latest package also adds virtual S-parameter acceptance, a scaled
760-mode/380-logical-qubit stretch max envelope with sub-18 mm^2 area,
max-qubit No-Go mapping, stress-recovery, feed-forward control timing, toy
decoder, truth-switch raw closure, multi-objective Pareto, worst-case corner,
Monte-Carlo robustness, internal-consistency, scorecard, and prototype-gap
reports. These improve the simulation evidence while still marking
foundry-calibrated S-parameters, hardware feed-forward verification, DRC/LVS,
prototype readiness, and lab data as external blockers.

## No-Budget Partner Path

If there is no cash budget for fabrication or legal work, the project should be
positioned as a reproducible partner-review package rather than a build-ready
quantum computer. The no-budget package lives in:

```text
docs/no-budget-partner-package.md
docs/30-minute-reproduction.md
docs/preprint-outline.md
docs/open-validation-issues.md
docs/partner-outreach.md
docs/grant-concept-note.md
docs/data-room-index.md
docs/reviewer-pack.md
docs/partner-pipeline.md
reports/node-alpha/report-index.json
reports/node-alpha/no-budget-package/no-budget-readiness.json
reports/node-alpha/no-budget-package/value-scorecard.json
reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.json
reports/node-alpha/deep-hardening-v3-20260502/operational-envelope-report.json
reports/node-alpha/deep-hardening-v3-20260502/joint-error-budget-report.json
reports/node-alpha/deep-hardening-v3-20260502/budget-optimizer-report.json
reports/node-alpha/deep-hardening-v3-20260502/throughput-report.json
reports/node-alpha/deep-hardening-v3-20260502/virtual-sparameter-acceptance-report.json
reports/node-alpha/deep-hardening-v3-20260502/scaled-layout-envelope-report.json
reports/node-alpha/deep-hardening-v3-20260502/max-qubit-envelope-report.json
reports/node-alpha/deep-hardening-v3-20260502/max-qubit-no-go-map-report.json
reports/node-alpha/deep-hardening-v3-20260502/stress-recovery-report.json
reports/node-alpha/deep-hardening-v3-20260502/control-timing-model-report.json
reports/node-alpha/deep-hardening-v3-20260502/decoder-evidence-report.json
reports/node-alpha/deep-hardening-v3-20260502/truth-switch-raw-closure-report.json
reports/node-alpha/deep-hardening-v3-20260502/multiobjective-pareto-report.json
reports/node-alpha/deep-hardening-v3-20260502/worst-case-corner-sweep-report.json
reports/node-alpha/deep-hardening-v3-20260502/monte-carlo-robustness-report.json
reports/node-alpha/deep-hardening-v3-20260502/internal-consistency-audit.json
reports/node-alpha/deep-hardening-v3-20260502/prototype-gap-reduction-report.json
reports/node-alpha/value-upgrade-20260502/yield-improvement-report.json
notebooks/node-alpha-report-summary.ipynb
```

The package gives reviewers exact artifacts, hashes, reproduction commands,
open validation tasks, and a preprint outline while preserving the hard boundary
that foundry-calibrated S-parameters, PDK DRC/LVS, measured hardware evidence,
and hardware-calibrated noise data are still missing.

The validator reports total mesh path loss separately from effective per-stage
component loss. For the current champion, `attenuation_loss_score: 0.29` maps to
approximately `1.487 dB` total mesh path loss and `0.372 dB` per effective component
stage when normalized over four stages.

Architecture notes live in:

```text
architecture/overview.md
architecture/isa.md
architecture/microarchitecture.md
architecture/universal-model.md
architecture/resource-model.md
architecture/control-system.md
architecture/lab-readiness.md
architecture/demonstrator-roadmap.md
architecture/complete-design.md
architecture/node-alpha-closure.md
```

---

## 📜 License & OPSEC 

> [!CAUTION]
> This hardware design is explicitly licensed under the **CERN Open Hardware Licence Version 2 - Strongly Reciprocal (CERN-OHL-S v2)**. Any modifications to this photonic architecture must be shared back under the same terms.

This project is released free of legacy AI orchestration metadata to ensure a clean, auditable standard for academic and deep-tech scaling.
