from .base import NodeTestBase, disable_key_reuse


class ConcentNodeTest(NodeTestBase):

    def test_force_report(self):
        self._run_test('concent.force_report')

    def test_force_download(self):
        self._run_test('concent.force_download')

    def test_force_accept(self):
        self._run_test('concent.force_accept')

    def test_additional_verification(self):
        self._run_test('concent.additional_verification')

    @disable_key_reuse
    def test_force_payment(self):
        self._run_test('concent.force_payment')
