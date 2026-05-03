# Assumption Ledger

This ledger is for reviewers. It lists the assumptions most likely to change
the OQP-HRM public simulation envelope. It is not hardware evidence.

| Assumption | Used in | Current evidence | Risk | Next test |
| --- | --- | --- | --- | --- |
| Truth-Switch dielectric perturbation | Truth-Switch crosstalk/reflection, fusion rows | Raw hardened simulation profile and surrogate switch model | high | 3D-FDTD/MPB extraction with mode-overlap and port calibration |
| Virtual S-parameters | compact-model acceptance, crosstalk/reflection gates | virtual consistency gate, 4/4 virtual accepted | high | foundry or wafer-calibrated Touchstone files with passivity/reciprocity checks |
| Normalized useful-flux surrogate | fusion success and `usefulTransmission` | analytical source-bank/port-normalized aggregate | high | hardware-calibrated source/detector model and measured primitive-demo data |
| Synthetic/analytical noise | 1e-9 envelope, decoder evidence, stress recovery | analytical error-budget model and toy decoder | high | hardware-calibrated syndrome/noise distributions and independent decoder review |
| Generic layout pitch and package banking | 760-mode layout envelope | review-floor layout model, no DRC/LVS | medium-high | PDK mapping, DRC/LVS decks, package/port review |
| 200M attempts/s cap | throughput and logical-cycle estimates | deliberate upper-bound cap, not raised by optimization | medium | measured source/detector/control timing and thermal/power model |
| Full decoder separation | timing/readiness claims | fast path and full decoder are explicitly separate | medium | production decoder implementation and hardware timing budget |

The highest-value next evidence jump is from surrogate/analytical closure to
independent 3D/MPB and foundry-calibrated S-parameter evidence for the four core
devices.
