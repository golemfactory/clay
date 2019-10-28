from golem.network.concent import soft_switch
from golem.tools.testwithdatabase import TestWithDatabase


class ConcentSwitchTestMixin:
    @property
    def _default(self):
        raise NotImplementedError()

    def _turn(self, on: bool):
        raise NotImplementedError()

    def _is_on(self):
        raise NotImplementedError()

    def test_default_value(self):
        self.assertEqual(self._is_on(), self._default)

    def test_turn_on(self):
        self._turn(False)
        self._turn(True)
        self.assertTrue(self._is_on())

    def test_turn_off(self):
        self._turn(True)
        self._turn(False)
        self.assertFalse(self._is_on())


class TestConcentSoftSwitch(ConcentSwitchTestMixin, TestWithDatabase):
    @property
    def _default(self):
        return False

    def _turn(self, on: bool):
        return soft_switch.concent_turn(on)

    def _is_on(self):
        return soft_switch.concent_is_on()


class TestConcentRequiredAsProvider(ConcentSwitchTestMixin, TestWithDatabase):
    @property
    def _default(self):
        return True

    def _turn(self, on: bool):
        return soft_switch.required_as_provider_turn(on)

    def _is_on(self):
        return soft_switch.is_required_as_provider()
