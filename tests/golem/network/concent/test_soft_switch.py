from golem import terms
from golem.network.concent import soft_switch
from golem.tools.testwithdatabase import TestWithDatabase

class TestContentSoftSwitch(TestWithDatabase):
    def test_default_value_wo_terms(self):
        self.assertFalse(soft_switch.is_on())

    def test_default_value_w_terms(self):
        terms.ConcentTermsOfUse.accept()
        self.assertTrue(soft_switch.is_on())

    def test_turn_on_wo_terms(self):
        soft_switch.turn(True)
        self.assertFalse(soft_switch.is_on())

    def test_turn_on_w_terms(self):
        terms.ConcentTermsOfUse.accept()
        soft_switch.turn(True)
        self.assertTrue(soft_switch.is_on())

    def test_turn_off(self):
        terms.ConcentTermsOfUse.accept()
        soft_switch.turn(True)
        soft_switch.turn(False)
        self.assertFalse(soft_switch.is_on())
