from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple
)

from twisted.internet.defer import Deferred

from golem.envs import (
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
    RuntimeId,
    RuntimeInput,
    RuntimeOutput,
    RuntimePayload,
    RuntimeStatus,
    UsageCounter,
    UsageCounterValues
)


class RuntimeWrapper(Runtime):
    """ A no-op wrapper which proxies all calls to the wrapped Runtime.
     Base class for implementing other wrappers. """

    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime

    def id(self) -> Optional[RuntimeId]:
        return self._runtime.id()

    def prepare(self) -> Deferred:
        return self._runtime.prepare()

    def clean_up(self) -> Deferred:
        return self._runtime.clean_up()

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

    def usage_counter_values(self) -> UsageCounterValues:
        return self._runtime.usage_counter_values()

    def listen(
            self,
            event_type: RuntimeEventType,
            listener: RuntimeEventListener
    ) -> None:
        self._runtime.listen(event_type, listener)


class EnvironmentWrapper(Environment):

    def __init__(self, env: Environment) -> None:
        self._env = env

    @classmethod
    def supported(cls) -> EnvSupportStatus:
        # This method should not be called on a wrapped environment.
        raise AttributeError('Method not supported on a wrapped environment')

    def status(self) -> EnvStatus:
        return self._env.status()

    def prepare(self) -> Deferred:
        return self._env.prepare()

    def clean_up(self) -> Deferred:
        return self._env.clean_up()

    def run_benchmark(self) -> Deferred:
        return self._env.run_benchmark()

    def parse_prerequisites(
            self, prerequisites_dict: Dict[str, Any]
    ) -> Prerequisites:
        return self._env.parse_prerequisites(prerequisites_dict)

    def install_prerequisites(self, prerequisites: Prerequisites) -> Deferred:
        return self._env.install_prerequisites(prerequisites)

    def parse_config(self, config_dict: Dict[str, Any]) -> EnvConfig:
        return self._env.parse_config(config_dict)

    def config(self) -> EnvConfig:
        return self._env.config()

    def update_config(self, config: EnvConfig) -> None:
        self._env.update_config(config)

    def listen(
            self,
            event_type: EnvEventType,
            listener: EnvEventListener
    ) -> None:
        self._env.listen(event_type, listener)

    def supported_usage_counters(self) -> List[UsageCounter]:
        return self._env.supported_usage_counters()

    def runtime(
            self,
            payload: RuntimePayload,
            config: Optional[EnvConfig] = None
    ) -> Runtime:
        return self._env.runtime(payload, config)
