import math
import unittest

from oqp.metrics import loss_fraction_to_db, per_stage_loss, transmission_to_db
from oqp.topology import connected_component_count, mzi_pairs


class MetricsTopologyTest(unittest.TestCase):
    def test_loss_score_normalizes_to_expected_component_loss(self):
        total = loss_fraction_to_db(0.29)
        stage_db, stage_fraction = per_stage_loss(total, 4)

        self.assertAlmostEqual(total, 1.4874165128092474)
        self.assertAlmostEqual(stage_db, 0.37185412820231184)
        self.assertAlmostEqual(stage_fraction, 0.08205938246658029)

    def test_heralding_yield_loss(self):
        self.assertAlmostEqual(transmission_to_db(0.705), 1.518108830086013)

    def test_reference_stride_has_disconnected_lanes(self):
        pairs = mzi_pairs(36, 24, 3)
        self.assertEqual(connected_component_count(36, pairs), 24)

    def test_stride_one_depth_thirty_six_connects_all_modes(self):
        pairs = mzi_pairs(36, 36, 1)
        self.assertEqual(connected_component_count(36, pairs), 1)

    def test_loss_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            loss_fraction_to_db(1.0)
        with self.assertRaises(ValueError):
            transmission_to_db(math.inf)


if __name__ == "__main__":
    unittest.main()
