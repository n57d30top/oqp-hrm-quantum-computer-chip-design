# OQP-HRM Prototype Readiness Gate

`oqp prototype-readiness` is the master audit between the computed GDS milestone
and a real photonically integrated quantum-computer prototype.

It does not mark the system ready from proxy signals. It maps each explicit
goal requirement to concrete artifacts and keeps incomplete items open until
the relevant evidence exists.

## Inputs

Default artifacts:

```text
reports/node-alpha/gds-path/gds-audit.json
reports/node-alpha/qc-path/device-sweep.json
reports/node-alpha/qc-path/control-readiness.json
reports/node-alpha/qc-path/lab-readiness.json
reports/node-alpha/qc-path/threshold-sweep.json
reports/node-alpha/qc-path/fusion-primitive.json
```

## Commands

```bash
oqp device-acceptance hardware/Heralded_Reset_Mesh_Blueprint.yaml \
  --out reports/node-alpha/qc-path/device-acceptance-audit.json

oqp prototype-readiness hardware/Heralded_Reset_Mesh_Blueprint.yaml \
  --out reports/node-alpha/qc-path/prototype-readiness.json
```

## Checklist Criteria

- pre-tapeout GDS exists and is layout-computable
- MZI, directional-coupler, phase-shifter, and truth-switch devices are accepted
- real foundry PDK is selected and version-locked
- GDS is DRC-clean and LVS-clean
- source, detector, fiber/edge-coupler, probe-card, and package path are real
- control electronics and feed-forward operation are hardware-verified
- automatic calibration is implemented
- error-correction path has below-threshold evidence and decoder interface
- heralded quantum primitive is experimentally demonstrated

Current reports intentionally keep the prototype in `not_prototype_ready` until
all criteria have real supporting artifacts.

## Current Device Simulation Model

Core device evidence must be generated with:

```text
eigenmode_device.v4.reference_output_port_normalized_reliability_gate
```

This model removes an earlier cladding cutout that crossed the silicon
waveguide cores in the coupler/MZI region and normalizes through/cross power
against the straight-waveguide output-port reference. It also rejects candidates
whose output-port reference flux is too weak for stable normalization. Reports
without the model marker are classified as stale and must be regenerated.

Recommended Node Alpha sweep after deploying the updated code:

```bash
oqp device-sweep hardware/Heralded_Reset_Mesh_Blueprint.yaml \
  --devices coupler,mzi,phase-shifter,truth-switch \
  --coupling-gaps-um 0.18,0.2 \
  --coupling-lengths-um 3.0,6.0,12.0,18.0 \
  --phase-shifts-rad 0.0,1.5708,3.14159 \
  --waveguide-widths-um 0.45,0.5 \
  --resolution 16 \
  --until 40 \
  --max-runs 96 \
  --out reports/node-alpha/qc-path/device-sweep-v4
```
