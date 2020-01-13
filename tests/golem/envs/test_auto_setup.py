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
from golem.envs.wrappers.auto_setup import auto_setup


class TestAutoSetup(TwistedTestCase):
    # pylint: disable=too-many-public-methods

    def setUp(self):
        self.env = Mock(spec_set=Environment)
        self.runtime = Mock(spec_set=Runtime)
        self.env.runtime.return_value = self.runtime
        self.start_usage = Mock(return_value=defer.succeed(None))
        self.end_usage = Mock(return_value=defer.succeed(None))
        self.wrapped_env = auto_setup(
            self.env, self.start_usage, self.end_usage)

        self.master_mock = Mock()  # To assert call order between multiple mocks
        self.master_mock.attach_mock(self.start_usage, 'start_usage')
        self.master_mock.attach_mock(self.end_usage, 'end_usage')

    def test_parse_prerequisites(self):
        prereq_dict = {'key': 'value'}
        prereq = self.wrapped_env.parse_prerequisites(prereq_dict)
        self.assertEqual(prereq, self.env.parse_prerequisites.return_value)
        self.env.parse_prerequisites.assert_called_once_with(prereq_dict)

    def test_parse_config(self):
        config_dict = {'key': 'value'}
        config = self.wrapped_env.parse_config(config_dict)
        self.assertEqual(config, self.env.parse_config.return_value)
        self.env.parse_config.assert_called_once_with(config_dict)

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
        self.master_mock.attach_mock(self.env.run_benchmark, 'run_benchmark')
        self.env.run_benchmark.return_value = defer.succeed(21.37)
        result = yield self.wrapped_env.run_benchmark()
        self.assertEqual(result, 21.37)
        self.master_mock.assert_has_calls((
            call.start_usage(self.env),
            call.run_benchmark(),
            call.end_usage(self.env)
        ))

    @defer.inlineCallbacks
    def test_install_prerequisites(self):
        self.master_mock.attach_mock(
            self.env.install_prerequisites, 'install_prerequisites')
        prereq = Mock(spec_set=Prerequisites)
        self.env.install_prerequisites.return_value = True
        result = yield self.wrapped_env.install_prerequisites(prereq)
        self.assertEqual(result, True)
        self.master_mock.assert_has_calls((
            call.start_usage(self.env),
            call.install_prerequisites(prereq),
            call.end_usage(self.env)
        ))

    @defer.inlineCallbacks
    def test_install_prerequisites_during_benchmark(self):

        @defer.inlineCallbacks
        def _benchmark():
            self.start_usage.assert_called_once_with(self.env)
            self.start_usage.reset_mock()
            prereq = Mock(spec_set=Prerequisites)
            yield self.wrapped_env.install_prerequisites(prereq)
            self.start_usage.assert_not_called()
            self.end_usage.assert_not_called()

        self.env.run_benchmark.side_effect = _benchmark
        yield self.wrapped_env.run_benchmark()
        self.end_usage.assert_called_once_with(self.env)

    @defer.inlineCallbacks
    def test_runtime_flow(self):
        self.master_mock.attach_mock(self.runtime.prepare, 'runtime_prepare')
        self.master_mock.attach_mock(self.runtime.start, 'runtime_start')
        self.master_mock.attach_mock(self.runtime.stop, 'runtime_stop')
        self.master_mock.attach_mock(self.runtime.clean_up, 'runtime_clean_up')

        payload = Mock(spec_set=RuntimePayload)
        config = Mock(spec_set=EnvConfig)
        runtime = self.wrapped_env.runtime(payload, config)
        self.env.runtime.assert_called_once_with(payload, config)

        yield runtime.prepare()
        self.master_mock.assert_has_calls((
            call.start_usage(self.env),
            call.runtime_prepare()
        ))

        self.master_mock.reset_mock()
        yield runtime.start()
        self.master_mock.assert_has_calls((
            call.runtime_start(),
        ))

        self.master_mock.reset_mock()
        yield runtime.stop()
        self.master_mock.assert_has_calls((
            call.runtime_stop(),
        ))

        self.master_mock.reset_mock()
        yield runtime.clean_up()
        self.master_mock.assert_has_calls((
            call.runtime_clean_up(),
            call.end_usage(self.env)
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
        counters = runtime.usage_counter_values()
        self.assertEqual(counters, self.runtime.usage_counter_values())

    def test_runtime_listen(self):
        payload = Mock(spec_set=RuntimePayload)
        config = Mock(spec_set=EnvConfig)
        runtime = self.wrapped_env.runtime(payload, config)
        event_type = RuntimeEventType.PREPARED
        listener = lambda _: None  # noqa: E731
        runtime.listen(event_type, listener)
        self.runtime.listen.assert_called_once_with(event_type, listener)
