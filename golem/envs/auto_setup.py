from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    Tuple
)

from twisted.internet.defer import (
    Deferred,
    DeferredLock,
    inlineCallbacks
)

from golem.envs import (
    CounterId,
    CounterUsage,
    EnvConfig,
    EnvEventListener,
    EnvEventType,
    Environment,
    EnvStatus,
    EnvSupportStatus,
    Prerequisites,
    Runtime,
    RuntimeEventListener,
    RuntimeEventType,
    RuntimeInput,
    RuntimeOutput,
    RuntimePayload,
    RuntimeStatus
)


class RuntimeSetupWrapper(Runtime):

    def __init__(
            self,
            runtime: Runtime,
            start_usage: Callable[[], Deferred],
            end_usage: Callable[[], Deferred]
    ) -> None:
        self._runtime = runtime
        self._start_usage = start_usage
        self._end_usage = end_usage

    @inlineCallbacks
    def prepare(self) -> Deferred:
        yield self._start_usage()
        yield self._runtime.prepare()

    @inlineCallbacks
    def clean_up(self) -> Deferred:
        yield self._runtime.clean_up()
        yield self._end_usage()

    def start(self) -> Deferred:
        return self._runtime.start()

    def wait_until_stopped(self) -> Deferred:
        return self._runtime.wait_until_stopped()

    def stop(self) -> Deferred:
        return self._runtime.stop()

    def status(self) -> RuntimeStatus:
        return self._runtime.status()

    def stdin(self, encoding: Optional[str] = None) -> RuntimeInput:
        return self._runtime.stdin(encoding)

    def stdout(self, encoding: Optional[str] = None) -> RuntimeOutput:
        return self._runtime.stdout(encoding)

    def stderr(self, encoding: Optional[str] = None) -> RuntimeOutput:
        return self._runtime.stderr(encoding)

    def get_port_mapping(self, port: int) -> Tuple[str, int]:
        return self._runtime.get_port_mapping(port)

    def usage_counters(self) -> Dict[CounterId, CounterUsage]:
        return self._runtime.usage_counters()

    def listen(
            self,
            event_type: RuntimeEventType,
            listener: RuntimeEventListener
    ) -> None:
        self._runtime.listen(event_type, listener)


def auto_setup(
        env: Environment,
        start_usage: Callable[[Environment], Deferred],
        end_usage: Callable[[Environment], Deferred]
) -> Environment:

    class EnvSetupWrapper(Environment):

        def __init__(self) -> None:
            self._num_users = 0
            self._lock = DeferredLock()

        @inlineCallbacks
        def _start_usage(self) -> Deferred:
            yield self._lock.acquire()
            try:
                if self._num_users == 0:
                    yield start_usage(env)
                self._num_users += 1
            finally:
                self._lock.release()

        @inlineCallbacks
        def _end_usage(self) -> Deferred:
            yield self._lock.acquire()
            try:
                self._num_users -= 1
                if self._num_users == 0:
                    yield end_usage(env)
            finally:
                self._lock.release()

        @classmethod
        def supported(cls) -> EnvSupportStatus:
            return env.supported()

        def status(self) -> EnvStatus:
            return env.status()

        def prepare(self) -> Deferred:
            raise AttributeError('prepare and clean_up not supported')

        def clean_up(self) -> Deferred:
            raise AttributeError('prepare and clean_up not supported')

        @inlineCallbacks
        def run_benchmark(self) -> Deferred:
            yield self._start_usage()
            try:
                return (yield env.run_benchmark())
            finally:
                yield self._end_usage()

        @classmethod
        def parse_prerequisites(
                cls,
                prerequisites_dict: Dict[str, Any]
        ) -> Prerequisites:
            return env.parse_prerequisites(prerequisites_dict)

        @inlineCallbacks
        def install_prerequisites(
                self,
                prerequisites: Prerequisites
        ) -> Deferred:
            yield self._start_usage()
            try:
                return (yield env.install_prerequisites(prerequisites))
            finally:
                yield self._end_usage()

        @classmethod
        def parse_config(cls, config_dict: Dict[str, Any]) -> EnvConfig:
            return env.parse_config(config_dict)

        def config(self) -> EnvConfig:
            return env.config()

        def update_config(self, config: EnvConfig) -> None:
            env.update_config(config)

        def listen(
                self,
                event_type: EnvEventType,
                listener: EnvEventListener
        ) -> None:
            env.listen(event_type, listener)

        def runtime(
                self,
                payload: RuntimePayload,
                config: Optional[EnvConfig] = None
        ) -> Runtime:
            runtime = env.runtime(payload, config)
            return RuntimeSetupWrapper(
                runtime=runtime,
                start_usage=self._start_usage,
                end_usage=self._end_usage
            )

    return EnvSetupWrapper()
