from unittest.mock import Mock, call

from twisted.internet import defer
from twisted.trial.unittest import TestCase as TwistedTestCase

from golem.envs import (
    EnvConfig,
    EnvEventType,
    Environment,
    Prerequisites,
    Runtime,
    RuntimeEventType,
    RuntimePayload
)
from golem.envs.auto_setup import auto_setup


class TestAutoSetup(TwistedTestCase):
    # pylint: disable=too-many-public-methods

    def setUp(self):
        self.env_cls = Mock(spec_set=Environment)
        self.runtime = Mock(spec_set=Runtime)
        self.env = self.env_cls()
        self.env.runtime.return_value = self.runtime
        self.wrapped_cls = auto_setup(self.env_cls)
        self.wrapped_env = self.wrapped_cls()

    def test_supported(self):
        self.assertEqual(self.wrapped_cls.supported(), self.env_cls.supported())

    def test_metadata(self):
        self.assertEqual(self.wrapped_env.metadata(), self.env.metadata())

    def test_parse_prerequisites(self):
        prereq_dict = {'key': 'value'}
        prereq = self.wrapped_cls.parse_prerequisites(prereq_dict)
        self.assertEqual(prereq, self.env_cls.parse_prerequisites.return_value)
        self.env_cls.parse_prerequisites.assert_called_once_with(prereq_dict)

    def test_parse_config(self):
        config_dict = {'key': 'value'}
        config = self.wrapped_cls.parse_config(config_dict)
        self.assertEqual(config, self.env_cls.parse_config.return_value)
        self.env_cls.parse_config.assert_called_once_with(config_dict)

    def test_status(self):
        self.assertEqual(self.wrapped_env.status(), self.env.status())

    @defer.inlineCallbacks
    def test_prepare(self):
        with self.assertRaises(AttributeError):
            yield self.wrapped_env.prepare()

    @defer.inlineCallbacks
    def test_clean_up(self):
        with self.assertRaises(AttributeError):
            yield self.wrapped_env.prepare()

    def test_update_config(self):
        config = Mock(spec_set=EnvConfig)
        self.wrapped_env.update_config(config)
        self.env.update_config.assert_called_once_with(config)

    def test_listen(self):
        event_type = EnvEventType.ENABLED
        listener = lambda _: None  # noqa: E731
        self.wrapped_env.listen(event_type, listener)
        self.env.listen.assert_called_once_with(event_type, listener)

    @defer.inlineCallbacks
    def test_run_benchmark(self):
        self.env.run_benchmark.return_value = defer.succeed(21.37)
        result = yield self.wrapped_env.run_benchmark()
        self.assertEqual(result, 21.37)
        self.env.assert_has_calls((
            call.prepare(),
            call.run_benchmark(),
            call.clean_up()
        ))

    @defer.inlineCallbacks
    def test_install_prerequisites(self):
        prereq = Mock(spec_set=Prerequisites)
        self.env.install_prerequisites.return_value = True
        result = yield self.wrapped_env.install_prerequisites(prereq)
        self.assertEqual(result, True)
        self.env.assert_has_calls((
            call.prepare(),
            call.install_prerequisites(prereq),
            call.clean_up()
        ))

    @defer.inlineCallbacks
    def test_install_prerequisites_during_benchmark(self):

        @defer.inlineCallbacks
        def _benchmark():
            self.env.prepare.assert_called_once()
            self.env.reset_mock()
            prereq = Mock(spec_set=Prerequisites)
            yield self.wrapped_env.install_prerequisites(prereq)
            self.env.prepare.assert_not_called()
            self.env.clean_up.assert_not_called()

        self.env.run_benchmark.side_effect = _benchmark
        yield self.wrapped_env.run_benchmark()
        self.env.clean_up.assert_called_once()

    @defer.inlineCallbacks
    def test_runtime_flow(self):
        master_mock = Mock()  # To assert call order between two mocks
        master_mock.attach_mock(self.env.prepare, 'env_prepare')
        master_mock.attach_mock(self.env.clean_up, 'env_clean_up')
        master_mock.attach_mock(self.runtime.prepare, 'runtime_prepare')
        master_mock.attach_mock(self.runtime.start, 'runtime_start')
        master_mock.attach_mock(self.runtime.stop, 'runtime_stop')
        master_mock.attach_mock(self.runtime.clean_up, 'runtime_clean_up')

        payload = Mock(spec_set=RuntimePayload)
        config = Mock(spec_set=EnvConfig)
        runtime = self.wrapped_env.runtime(payload, config)
        self.env.runtime.assert_called_once_with(payload, config)

        yield runtime.prepare()
        master_mock.assert_has_calls((
            call.env_prepare(),
            call.runtime_prepare()
        ))

        master_mock.reset_mock()
        yield runtime.start()
        master_mock.assert_has_calls((
            call.runtime_start(),
        ))

        master_mock.reset_mock()
        yield runtime.stop()
        master_mock.assert_has_calls((
            call.runtime_stop(),
        ))

        master_mock.reset_mock()
        yield runtime.clean_up()
        master_mock.assert_has_calls((
            call.runtime_clean_up(),
            call.env_clean_up()
        ))

    @defer.inlineCallbacks
    def test_runtime_wait_until_stopped(self):
        payload = Mock(spec_set=RuntimePayload)
        config = Mock(spec_set=EnvConfig)
        runtime = self.wrapped_env.runtime(payload, config)
        yield runtime.wait_until_stopped()
        self.runtime.wait_until_stopped.assert_called_once_with()

    def test_runtime_status(self):
        payload = Mock(spec_set=RuntimePayload)
        config = Mock(spec_set=EnvConfig)
        runtime = self.wrapped_env.runtime(payload, config)
        self.assertEqual(runtime.status(), self.runtime.status())

    def test_runtime_stdin(self):
        payload = Mock(spec_set=RuntimePayload)
        config = Mock(spec_set=EnvConfig)
        runtime = self.wrapped_env.runtime(payload, config)
        stdin = runtime.stdin('utf-7')
        self.runtime.stdin.assert_called_once_with('utf-7')
        self.assertEqual(stdin, self.runtime.stdin())

    def test_runtime_stdout(self):
        payload = Mock(spec_set=RuntimePayload)
        config = Mock(spec_set=EnvConfig)
        runtime = self.wrapped_env.runtime(payload, config)
        stdout = runtime.stdout('utf-7')
        self.runtime.stdout.assert_called_once_with('utf-7')
        self.assertEqual(stdout, self.runtime.stdout())

    def test_runtime_stderr(self):
        payload = Mock(spec_set=RuntimePayload)
        config = Mock(spec_set=EnvConfig)
        runtime = self.wrapped_env.runtime(payload, config)
        stderr = runtime.stderr('utf-7')
        self.runtime.stderr.assert_called_once_with('utf-7')
        self.assertEqual(stderr, self.runtime.stderr())

    def test_runtime_port_mapping(self):
        self.runtime.get_port_mapping.return_value = '127.0.0.1', 666
        payload = Mock(spec_set=RuntimePayload)
        config = Mock(spec_set=EnvConfig)
        runtime = self.wrapped_env.runtime(payload, config)
        mapping = runtime.get_port_mapping(1234)
        self.assertEqual(mapping, ('127.0.0.1', 666))
        self.runtime.get_port_mapping.assert_called_once_with(1234)

    def test_runtime_usage_counters(self):
        payload = Mock(spec_set=RuntimePayload)
        config = Mock(spec_set=EnvConfig)
        runtime = self.wrapped_env.runtime(payload, config)
        counters = runtime.usage_counters()
        self.assertEqual(counters, self.runtime.usage_counters())

    def test_runtime_listen(self):
        payload = Mock(spec_set=RuntimePayload)
        config = Mock(spec_set=EnvConfig)
        runtime = self.wrapped_env.runtime(payload, config)
        event_type = RuntimeEventType.PREPARED
        listener = lambda _: None  # noqa: E731
        runtime.listen(event_type, listener)
        self.runtime.listen.assert_called_once_with(event_type, listener)
