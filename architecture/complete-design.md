# OQP-HRM Complete Design Dossier

This document defines what "finished design" means for this repository.

OQP-HRM can be closed as a complete architecture dossier when the repository
contains an auditable specification for every stack layer:

1. computational encoding
2. universal primitive path
3. non-Gaussian resource model
4. ISA and runtime trace
5. physical error model
6. fault-tolerance design path
7. prototype readiness gate map
8. evidence intake contract

The dossier is generated with:

```bash
oqp design-dossier hardware/Heralded_Reset_Mesh_Blueprint.yaml \
  --out reports/node-alpha/qc-path/complete-design-dossier.json
```

## Claim Boundary

`complete_architecture_dossier` means the design is specified and auditable as
a full-stack photonic quantum-computer architecture. It does not mean the chip
is foundry-ready, experimentally validated, or fault tolerant.

A complete quantum computer requires all of these readiness flags to be true:

- `prototype_ready`
- `tapeout_ready`
- `hardware_evidence_complete`
- `fault_tolerance_ready`
- `experimental_primitive_demonstrated`

The current reports intentionally keep these claims false until measured
hardware, foundry PDK, DRC/LVS, decoder, and primitive-demo evidence exists.

## Roadmap Order

The dossier sorts the remaining work by dependency:

1. Accept core devices and attach foundry-calibrated S-parameters.
2. Lock a real foundry PDK and process stack.
3. Run clean DRC/LVS or approved waivers.
4. Close source, detector, packaging, and control hardware.
5. Close automatic calibration.
6. Verify feed-forward operation in hardware.
7. Validate below-threshold fault tolerance and decoder latency.
8. Demonstrate the heralded primitive with a verified dataset.

This is the non-fabricated completion path: the architecture can be finished as
a design dossier now, while the physical quantum computer remains blocked until
the evidence gates pass.
