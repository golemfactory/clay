from unittest import TestCase

from mock import patch

from golem.ranking.manager.time_manager import TimeManager


class TestTimeManager(TestCase):
    @patch("golem.ranking.manager.time_manager.time")
    def test_oracle(self, mock_time):
        oracle = TimeManager(200, 50, 110, 1000)
        assert oracle.break_time == 200
        assert oracle.round_time == 50
        assert oracle.end_round_time == 110
        assert oracle.stage_time == 1000

        # During round
        mock_time.time.return_value = 1475850990.931
        assert int(oracle.sec_to_round()) == 329
        assert int(oracle.sec_to_end_round()) == 19
        assert int(oracle.sec_to_break()) == 129
        assert int(oracle.sec_to_new_stage()) == 9

        # During end round
        mock_time.time.return_value = 1475851010.931
        assert int(oracle.sec_to_round()) == 309
        assert int(oracle.sec_to_end_round()) == 359
        assert int(oracle.sec_to_break()) == 109
        assert int(oracle.sec_to_new_stage()) == 989

        # During break
        mock_time.time.return_value = 1475851140.931
        assert int(oracle.sec_to_round()) == 179
        assert int(oracle.sec_to_end_round()) == 229
        assert int(oracle.sec_to_break()) == 339
        assert int(oracle.sec_to_new_stage()) == 859
