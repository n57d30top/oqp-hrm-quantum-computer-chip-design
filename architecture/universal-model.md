# OQP-HRM Universal Model Path

OQP-HRM uses dual-rail path qubits as the near-term architecture path. Linear optics
alone is not universal, so the universal path depends on non-Gaussian resources:
single-photon sources, photon-number resolving detectors, ancilla/resource states, and
measurement-induced entangling or fusion primitives.

## Selected Near-Term Primitive

The first demonstrator target is a two-qubit heralded fusion cell:

```text
prepare dual-rail qubits
-> route modes into MZI/coupler network
-> apply phase and truth-switch state
-> perform photon-number resolving measurement
-> accept only heralded fusion events
-> decode dual-rail occupancy to logical result
```

This is a conditional universal path. It becomes a full architecture only after the
resource-state factory, multiplexing, error correction, and decoder are specified and
validated against physical loss and detector noise.

The executable report path is:

```bash
oqp eigenmode-device-run hardware/Heralded_Reset_Mesh_Blueprint.yaml --device mzi --out runs/mzi-eigenmode-fdtd.json
oqp fusion-primitive hardware/Heralded_Reset_Mesh_Blueprint.yaml --device-report runs/mzi-eigenmode-fdtd.json --out runs/fusion-primitive.json
```

## Acceptance Targets

- Insertion loss below 1 dB per accepted primitive cell.
- Reflection below 5%.
- Heralded primitive success probability above 1%.
- Feed-forward latency below 10 ns.
- Process fidelity above 99% before fault-tolerance overhead.
