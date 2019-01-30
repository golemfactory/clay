from golem.network.concent import soft_switch
from golem.tools.testwithdatabase import TestWithDatabase


class TestContentSoftSwitch(TestWithDatabase):
    def test_default_value(self):
        self.assertFalse(soft_switch.is_on())

    def test_turn_on(self):
        soft_switch.turn(True)
        self.assertTrue(soft_switch.is_on())

    def test_turn_off(self):
        soft_switch.turn(True)
        soft_switch.turn(False)
        self.assertFalse(soft_switch.is_on())
