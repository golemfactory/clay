import functools
from typing import Callable, Optional

from twisted.internet.defer import (
    Deferred,
    DeferredLock,
    inlineCallbacks
)

from golem.envs import (
    EnvConfig,
    Environment,
    Prerequisites,
    Runtime,
    RuntimePayload,
)
from golem.envs.wrappers import EnvironmentWrapper, RuntimeWrapper


class RuntimeSetupWrapper(RuntimeWrapper):

    def __init__(
            self,
            runtime: Runtime,
            start_usage: Callable[[], Deferred],
            end_usage: Callable[[], Deferred]
    ) -> None:
        super().__init__(runtime)
        self._start_usage = start_usage
        self._end_usage = end_usage

    @inlineCallbacks
    def prepare(self) -> Deferred:
        yield self._start_usage()
        yield super().prepare()

    @inlineCallbacks
    def clean_up(self) -> Deferred:
        yield super().clean_up()
        yield self._end_usage()


class EnvSetupWrapper(EnvironmentWrapper):

    def __init__(
            self,
            env: Environment,
            start_usage: Callable[[], Deferred],
            end_usage: Callable[[], Deferred]
    ) -> None:
        super().__init__(env)
        self._num_users = 0
        self._lock = DeferredLock()
        self._start_usage = start_usage
        self._end_usage = end_usage

    @inlineCallbacks
    def _prepare_runtime(self) -> Deferred:
        yield self._lock.acquire()
        try:
            if self._num_users == 0:
                yield self._start_usage()
            self._num_users += 1
        finally:
            self._lock.release()

    @inlineCallbacks
    def _clean_up_runtime(self) -> Deferred:
        yield self._lock.acquire()
        try:
            self._num_users -= 1
            if self._num_users == 0:
                yield self._end_usage()
        finally:
            self._lock.release()

    def prepare(self) -> Deferred:
        raise AttributeError('prepare and clean_up not supported')

    def clean_up(self) -> Deferred:
        raise AttributeError('prepare and clean_up not supported')

    @inlineCallbacks
    def run_benchmark(self) -> Deferred:
        yield self._prepare_runtime()
        try:
            return (yield self._env.run_benchmark())
        finally:
            yield self._clean_up_runtime()

    @inlineCallbacks
    def install_prerequisites(
            self,
            prerequisites: Prerequisites
    ) -> Deferred:
        yield self._prepare_runtime()
        try:
            return (yield self._env.install_prerequisites(prerequisites))
        finally:
            yield self._clean_up_runtime()

    def runtime(
            self,
            payload: RuntimePayload,
            config: Optional[EnvConfig] = None
    ) -> Runtime:
        runtime = self._env.runtime(payload, config)
        return RuntimeSetupWrapper(
            runtime=runtime,
            start_usage=self._prepare_runtime,
            end_usage=self._clean_up_runtime
        )


def auto_setup(
        env: Environment,
        start_usage: Callable[[Environment], Deferred],
        end_usage: Callable[[Environment], Deferred]
) -> Environment:
    """ Wrap given environment so that it automatically calls start_usage when
        it's needed and end_usage when it's no longer needed. By 'needed' we
        mean there are active Runtime objects created by this environment, or
        benchmark is running, or runtime prerequisites are being installed. """

    return EnvSetupWrapper(
        env=env,
        start_usage=functools.partial(start_usage, env),
        end_usage=functools.partial(end_usage, env)
    )
