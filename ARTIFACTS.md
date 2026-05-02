# Artifact Manifest

This file lists the public reproducibility artifacts and their SHA-256 hashes.
The hashes are intended for review and regression tracking only.
`ARTIFACTS.sha256` is the machine-readable checksum file used by CI.

## Reproduction Commands

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
python3 -m oqp.cli performance-upgrade hardware/Heralded_Reset_Mesh_Blueprint.yaml \
  --artifact-root reports/node-alpha \
  --out-dir runs/local-deep-hardening-v3 \
  --focused-max-runs 768
shasum -a 256 -c ARTIFACTS.sha256
```

Expected test count: `49`.

## Deep-Hardening V3 Reports

| SHA-256 | Artifact |
| --- | --- |
| `faac361b162db498b9dee2660b5dd7cb59744eae0ac80a73ea3426d3d38718b5` | `reports/node-alpha/deep-hardening-v3-20260502/budget-optimizer-report.json` |
| `4964b9c15f816ee42e12b78e9498f46dae775e985ca7885e7389fa93f03036bc` | `reports/node-alpha/deep-hardening-v3-20260502/control-timing-model-report.json` |
| `8035b13f1c9abeadcdaf5770bf2864104a98573ac667dc6ef0ad85c3e6815413` | `reports/node-alpha/deep-hardening-v3-20260502/decoder-evidence-report.json` |
| `b2e129e6588946003c68f0ee946e6ccd8302a360797446d41460630152c7682b` | `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.json` |
| `f1749f1124641b9e0a3c0b7f41a84307e699802d12e4f66dcd7c86d6c772789a` | `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.md` |
| `4d86655dbc5d54ea02c7cc6b42d112795ad297c94d0e23dab2efd1b32cd8a65f` | `reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-scorecard.json` |
| `d320209d1dde1376a2bb72203d68d351ee8042094720da69343ed61f7839f7cc` | `reports/node-alpha/deep-hardening-v3-20260502/device-sweep-deep-hardening-v3.json` |
| `c047a7a1ca759fb05e239ec65718794d2f0e9faa928cf879c72dd76b8b7e781d` | `reports/node-alpha/deep-hardening-v3-20260502/fusion-performance-candidates.json` |
| `168dc3ef84e3c1347e94154a385d09c76c5807d4e21cc5f59166545dc8d5d64c` | `reports/node-alpha/deep-hardening-v3-20260502/hardened-simulation-profile.json` |
| `def46225c02fc902dd81bee280ebadf6e4a7e1e0568e88aab8d1cc6306cce4b1` | `reports/node-alpha/deep-hardening-v3-20260502/internal-consistency-audit.json` |
| `c769bd05f54af0acabea87d10b67804814ab933885839a9eb908a599ac44dbdd` | `reports/node-alpha/deep-hardening-v3-20260502/joint-error-budget-report.json` |
| `463edbeb2cc38bb9c7a2a182e447c618a6f251a5100d4cae2a4a972b789d11c5` | `reports/node-alpha/deep-hardening-v3-20260502/max-qubit-envelope-report.json` |
| `725a5581aa7c51e60355d0a4b4bd58fa6d76c7ed7f8473f481e259715021b032` | `reports/node-alpha/deep-hardening-v3-20260502/max-qubit-no-go-map-report.json` |
| `0bfbf1d7419d1bf330cc5c4504a50e63b0525103481405e380c35a08d683a6fc` | `reports/node-alpha/deep-hardening-v3-20260502/monte-carlo-robustness-report.json` |
| `45d16fb696d395eca817c869f04c70dfa5ee1b0b626a4a482df40546a1fe9819` | `reports/node-alpha/deep-hardening-v3-20260502/multiobjective-pareto-report.json` |
| `e7c93470ba27b973e19c10ae30e1519e6c1a36c3712e43122d52dce605373a30` | `reports/node-alpha/deep-hardening-v3-20260502/operational-envelope-report.json` |
| `b2e129e6588946003c68f0ee946e6ccd8302a360797446d41460630152c7682b` | `reports/node-alpha/deep-hardening-v3-20260502/performance-upgrade-report.json` |
| `f1749f1124641b9e0a3c0b7f41a84307e699802d12e4f66dcd7c86d6c772789a` | `reports/node-alpha/deep-hardening-v3-20260502/performance-upgrade-report.md` |
| `7316b520424a14e87fa1dc07eda828ff10798dce5f4c54e92af85633a15bfc23` | `reports/node-alpha/deep-hardening-v3-20260502/prototype-gap-reduction-report.json` |
| `9dde793d1d565a95208aa6484e982e2cba4d755488c38007a1ffbc84498c8685` | `reports/node-alpha/deep-hardening-v3-20260502/resource-scaling-report.json` |
| `30c0b3b2b8645fa955ed8c5deb157f4e71b8e95ef417f98c798b8dfa9d9b3499` | `reports/node-alpha/deep-hardening-v3-20260502/scaled-layout-envelope-report.json` |
| `6b49c33f3f6b59fc190f9d13a72980c609dcdc891b68ba3a9a14884e82de4cff` | `reports/node-alpha/deep-hardening-v3-20260502/stress-recovery-report.json` |
| `e468267ea256e1b82427d6e851fe15633ef8d698aaabebaf33128812c8963553` | `reports/node-alpha/deep-hardening-v3-20260502/threshold-performance-sweep.json` |
| `f8cc30c42a9ceb9e7eb8071abaa6c5b403f4c470f87ed39cb6471e73cef0b011` | `reports/node-alpha/deep-hardening-v3-20260502/throughput-report.json` |
| `98919797d8840268e1a58d5562db3802dfaf894a9838336a061559401c2114b6` | `reports/node-alpha/deep-hardening-v3-20260502/truth-switch-raw-closure-report.json` |
| `d2bc83c61e6c4fb2653b08f8a578b94af36a07f67bdc9459dc624ae00759749b` | `reports/node-alpha/deep-hardening-v3-20260502/virtual-sparameter-acceptance-report.json` |
| `c0752a727805da650e66cfeb5f210741515c065116645bbc4822b643112515f3` | `reports/node-alpha/deep-hardening-v3-20260502/worst-case-corner-sweep-report.json` |
| `680bd6bdecf4f8d3336f6d2ddc0907cff5cb1ddfa85bd5c0f50df29ef218dad8` | `reports/node-alpha/report-index.json` |

## Device Evidence Reports

| SHA-256 | Artifact |
| --- | --- |
| `a736f1c4062f398fa9bc876cd04164037490456ec8467d1119876fada0e4f21d` | `reports/node-alpha/qc-path/device-acceptance-audit.json` |
| `a5c2f9073fd2de9d7fd4f6f5b872fb7a80a21699cedf7aaa8cadfe8f4e58d1c9` | `reports/node-alpha/qc-path/device-sweep-champion.json` |
| `45d959e1c74c2b6a6659535a620f1bbf6c25b93dc9998df88e9ed2b47e67fbed` | `reports/node-alpha/qc-path/device-sweep.json` |
| `7b9716b0a61c372c6994a31790d4c731b7501105ac36f367bd8d68aa08c43386` | `reports/node-alpha/qc-path/fusion-device-evidence.json` |
| `b4bd415409a32687ec1bc2eb0633e13bce0e0179913242ebe401eb17bbd3aa16` | `reports/node-alpha/qc-path/sparameter-audit.json` |
