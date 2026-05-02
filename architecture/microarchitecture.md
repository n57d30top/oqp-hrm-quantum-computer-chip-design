# OQP-HRM Microarchitecture v0

## Datapath

- Optical modes represented as waveguide lanes.
- MZI operations represented as explicit `ROUTE`, `MZI`, and `PHASE` ISA stages.
- Loss channels approximate mesh transmission.
- Detectors are modeled in the ISA but not physically simulated in v0.

## Control Plane

The control plane is classical. It consumes heralding events and changes downstream
route/reset instructions. In v0, this is represented by metrics and topology checks;
v1 should add a shot-level control trace.

## Metrics

- `heralding_yield`: transmission/success probability used in SF loss channels.
- `attenuation_loss_score`: normalized total mesh loss score.
- `effective_component_stage_count`: divisor for per-stage loss reporting.
- `modeGraphConnectedComponents`: topology connectivity check.
- `architectureScore`: ranking score for sweeps and optimizer output.

## Implemented Gates

- `oqp encoding`: computational mode/qubit encoding.
- `oqp compile`: ISA trace generation.
- `oqp runtime-trace`: shot timing and feed-forward latency model.
- `oqp error-budget`: noise, calibration, and fault-tolerance blockers.
- `oqp meep-device-run`: first MZI/coupler/truth-switch device-cell FDTD.
- `oqp layout-readiness`: PDK/GDS/tapeout blockers.

## Near-Term Gaps

- Add detector and photon-source models.
- Add connected mesh generators beyond fixed-stride pairing.
- Expand the `oqp meep-run` surrogate into full MEEP/FDTD physical geometry generation.
- Expand `oqp layout-plan` into a PDK-aware GDS exporter after a PDK target is selected.
