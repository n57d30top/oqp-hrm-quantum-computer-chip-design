# OQP-HRM Control System Path

The photonic chip needs a classical control plane with nanosecond-class feed-forward.

Required blocks:

- Detector readout and time tagging.
- FPGA/ASIC decision logic.
- DAC/driver channels for phase shifters and truth-switch actuators.
- Shot scheduler.
- Calibration controller for phase, loss, detector baseline, and source brightness.

`oqp control-readiness` reports the current timing budget and missing hardware blocks.
