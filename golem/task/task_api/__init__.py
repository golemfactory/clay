import abc
from pathlib import Path
from typing import Optional, Tuple, Type

from golem_task_api import TaskApiService

from golem.core.deferred import sync_wait
from golem.envs import (
    Environment,
    Prerequisites,
    Runtime,
    RuntimePayload,
    RuntimeStatus,
)


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
        raise NotImplementedError


class EnvironmentTaskApiService(TaskApiService):
    def __init__(
            self,
            env: Environment,
            prereq: Prerequisites,
            shared_dir: Path,
            payload_builder: Type[TaskApiPayloadBuilder],
    ) -> None:
        self._shared_dir = shared_dir
        self._prereq = prereq
        self._env = env
        self._payload_builder = payload_builder
        self._runtime: Optional[Runtime] = None

    def start(self, command: str, port: int) -> Tuple[str, int]:
        runtime_payload = self._payload_builder.create_payload(
            self._prereq,
            self._shared_dir,
            command,
            port,
        )
        self._runtime = self._env.runtime(runtime_payload)
        sync_wait(self._runtime.prepare())
        sync_wait(self._runtime.start())
        return self._runtime.get_port_mapping(port)

    def running(self) -> bool:
        return self._runtime is not None and self._runtime.status() in [
            RuntimeStatus.CREATED,
            RuntimeStatus.PREPARING,
            RuntimeStatus.PREPARED,
            RuntimeStatus.STARTING,
            RuntimeStatus.RUNNING,
        ]

    async def wait_until_shutdown_complete(self) -> None:
        assert self._runtime is not None
        sync_wait(self._runtime.wait_until_stopped())
