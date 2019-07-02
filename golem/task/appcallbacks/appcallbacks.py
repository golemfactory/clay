import abc
from pathlib import Path
from typing import Optional, Tuple, Type

from golem_task_api import AppCallbacks

from golem.core.deferred import sync_wait
from golem.envs import Environment, Prerequisites, Runtime, RuntimePayload


class TaskApiPayloadBuilder(abc.ABC):
    @classmethod
    @abc.abstractmethod
    def create_payload(
            cls,
            prereq: Prerequisites,
            shared_dir: Path,
            command: str,
            port: int,
    ) -> RuntimePayload:
        raise NotImplementedError()


class EnvironmentCallbacks(AppCallbacks):
    def __init__(
            self,
            env: Environment,
            prereq: Prerequisites,
            shared_dir: Path,
            payload_maker: Type[TaskApiPayloadBuilder],
    ) -> None:
        self._shared_dir = shared_dir
        self._prereq = prereq
        self._env = env
        self._payload_maker = payload_maker
        self._runtime: Optional[Runtime] = None

    def spawn_server(self, command: str, port: int) -> Tuple[str, int]:
        runtime_payload = self._payload_maker.create_payload(
            self._prereq,
            self._shared_dir,
            command,
            port,
        )
        self._runtime = self._env.runtime(runtime_payload)
        sync_wait(self._runtime.prepare())
        sync_wait(self._runtime.start())
        return self._runtime.get_port_mapping(port)

    async def wait_after_shutdown(self) -> None:
        assert self._runtime is not None
        sync_wait(self._runtime.wait_until_stopped())
