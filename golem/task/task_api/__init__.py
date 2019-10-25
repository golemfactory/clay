import abc
import asyncio
from pathlib import Path
from typing import Optional, Tuple, Type

from golem_task_api import TaskApiService

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

    async def start(self, command: str, port: int) -> Tuple[str, int]:
        runtime_payload = self._payload_builder.create_payload(
            self._prereq,
            self._shared_dir,
            command,
            port,
        )
        self._runtime = self._env.runtime(runtime_payload)
        loop = asyncio.get_event_loop()
        await self._runtime.prepare().asFuture(loop)
        await self._runtime.start().asFuture(loop)
        return self._runtime.get_port_mapping(port)

    async def stop(self) -> None:
        assert self._runtime is not None
        loop = asyncio.get_event_loop()
        await self._runtime.stop().asFuture(loop)

    def running(self) -> bool:
        """
        Checks if the service is 'closable' thus needs to be shutdown on errors
        """
        return self._runtime is not None and self._runtime.status() in [
            RuntimeStatus.CREATED,
            RuntimeStatus.PREPARING,
            RuntimeStatus.PREPARED,
            RuntimeStatus.STARTING,
            RuntimeStatus.RUNNING,
        ]

    async def wait_until_shutdown_complete(self) -> None:
        assert self._runtime is not None
        loop = asyncio.get_event_loop()
        try:
            await self._runtime.wait_until_stopped().asFuture(loop)
        finally:
            await self._runtime.clean_up().asFuture(loop)
