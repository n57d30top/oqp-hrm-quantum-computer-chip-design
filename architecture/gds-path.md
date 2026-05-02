# OQP-HRM Pre-Tapeout GDS Path

The GDS milestone is intentionally computable before tapeout readiness. It turns
the OQP-HRM blueprint into a generic-SiPh GDS, manifest, and audit bundle, while
preserving every known foundry and physics gap.

## Generated Artifacts

Default output directory:

```text
reports/node-alpha/gds-path/
```

Required files:

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

## Generic SiPh Layer Map

The default layer map contains waveguide, etch, slab, device, heater, metal,
via, pad, port, label, keepout, and package layers. It is PDK-aware in shape and
metadata, but it is not a foundry PDK.

## Component Library

The generic library includes cells for:

- waveguide
- directional coupler
- MZI
- phase shifter
- truth switch
- optical I/O placeholder
- detector interface
- source interface
- electrical pad

Core device cells consume FDTD/device-sweep evidence from
`reports/node-alpha/qc-path/`. Non-accepted devices are placed as
`fdtd_gap_backed_placeholder` so that GDS computation remains reproducible
without overstating physics or tapeout maturity.

## Audit Boundary

The final audit must keep these flags separate:

```text
gds_generated
layout_computable
fdtd_gap_backed_placeholder
drc_not_run
lvs_not_run
foundry_pdk_missing
not_tapeout_ready
```

Passing this milestone means a GDS exists and is reproducible. It does not mean
the design is foundry-clean, DRC/LVS-clean, packaged, calibrated, or ready for
tapeout.
