from unittest import TestCase

from mock import patch

from golem.ranking.manager.time_manager import TimeManager


class TestTimeManager(TestCase):
    @patch("golem.ranking.manager.time_manager.time")
    def test_oracle(self, mock_time):
        oracle = TimeManager(200, 50, 110, 1000)
        self.assertEqual(oracle.break_time, 200)
        self.assertEqual(oracle.round_time, 50)
        self.assertEqual(oracle.end_round_time, 110)
        self.assertEqual(oracle.stage_time, 1000)

        # During round
        mock_time.time.return_value = 1475850990.931
        self.assertAlmostEqual(oracle.sec_to_round(), 329, 0)
        self.assertAlmostEqual(oracle.sec_to_end_round(), 19, 0)
        self.assertAlmostEqual(oracle.sec_to_break(), 129, 0)
        self.assertAlmostEqual(oracle.sec_to_new_stage(), 9, 0)

        # During end round
        mock_time.time.return_value = 1475851010.931
        self.assertAlmostEqual(oracle.sec_to_round(), 309, 0)
        self.assertAlmostEqual(oracle.sec_to_end_round(), 359, 0)
        self.assertAlmostEqual(oracle.sec_to_break(), 109, 0)
        self.assertAlmostEqual(oracle.sec_to_new_stage(), 989, 0)

        # During break
        mock_time.time.return_value = 1475851140.931
        self.assertAlmostEqual(oracle.sec_to_round(), 179, 0)
        self.assertAlmostEqual(oracle.sec_to_end_round(), 229, 0)
        self.assertAlmostEqual(oracle.sec_to_break(), 339, 0)
        self.assertAlmostEqual(oracle.sec_to_new_stage(), 859, 0)
