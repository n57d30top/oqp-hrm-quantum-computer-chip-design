# 30-Minute Reproduction Guide

This guide verifies the public OQP-HRM package from local artifacts. It does
not require fabrication access, paid cloud compute, lab hardware, private
credentials, or excluded partner materials.

The public package contains the simulator core, unit tests, selected Node Alpha
V3 reports, a public report index, and hash manifests. It intentionally excludes
private/full diligence folders, generated caches, graph outputs, and lab
notebooks.

## 1. Install Locally

```bash
python3 -m pip install -e .
```

For a pinned public-core install:

```bash
make install
```

Optional photonics simulator dependencies are available for local experiments:

```bash
python3 -m pip install -e ".[simulation]"
```

The core public test and V3 report flow does not require the optional extra.

## 2. Run The Full Unit Suite

```bash
python3 -m unittest discover -s tests -v
```

Expected result:

```text
Ran 51 tests
OK
```

## 3. Validate The Committed Public Reports

```bash
python3 -m json.tool reports/node-alpha/report-index.json >/dev/null
python3 -m json.tool reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.json >/dev/null
python3 -m json.tool reports/node-alpha/deep-hardening-v3-20260502/virtual-sparameter-acceptance-report.json >/dev/null
python3 -m json.tool reports/node-alpha/qc-path/sparameter-audit.json >/dev/null
```

## 4. Verify Artifact Hashes

On Linux:

```bash
sha256sum -c ARTIFACTS.sha256
```

On macOS:

```bash
shasum -a 256 -c ARTIFACTS.sha256
```

The hash manifest tracks the committed public snapshot. If you regenerate
reports locally, update the manifest before treating hashes as a reviewed
release snapshot.

## 5. One-Command Public Reproduction

```bash
make ci
```

This runs the full unit suite, JSON checks, hash verification, and V3 scratch
regeneration.

The same path can be run in Docker:

```bash
docker build -t oqp-hrm-public .
docker run --rm oqp-hrm-public
```

## 6. Regenerate The V3 Performance Package

Use a scratch output directory so the committed report hashes remain unchanged:

```bash
rm -rf runs/local-deep-hardening-v3
python3 -m oqp.cli performance-upgrade hardware/Heralded_Reset_Mesh_Blueprint.yaml \
  --artifact-root reports/node-alpha \
  --out-dir runs/local-deep-hardening-v3 \
  --focused-max-runs 768
python3 -m json.tool runs/local-deep-hardening-v3/deep-hardening-v3-report.json >/dev/null
```

Expected high-level results in the regenerated report:

- `deepHardeningScore`: `110`
- `internalConsistencyPassed`: `11`
- `maxScaledPhysicalModes`: `760`
- `maxScaledLogicalDualRailQubits`: `380`
- `prototypeReady`: `false`
- `tapeoutReady`: `false`
- `hardwareMeasured`: `false`
- `foundrySparametersReady`: `false`

## 7. Inspect The Public Evidence Index

```bash
python3 - <<'PY'
import json
from pathlib import Path

index = json.loads(Path("reports/node-alpha/report-index.json").read_text())
print(json.dumps(index["summary"], indent=2, sort_keys=True))
PY
```

The index should report zero missing public artifacts. Any historical or private
full-package paths are out of scope for this public repository and are listed as
excluded evidence in `docs/data-room-index.md`.

## 8. Inspect The Evidence Ledger

```bash
python3 -m json.tool docs/evidence-ledger.json >/dev/null
```

The human-readable assumption ledger is `docs/assumption-ledger.md`.

## Interpretation

If the commands above pass, the repository is reproducible as a public,
simulation-only review package. It is still not prototype-ready or tapeout-ready
because the external evidence gates require foundry, hardware, or lab data.
