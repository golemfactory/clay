import abc
import asyncio
import time
import contextlib
import socket
from pathlib import Path
from typing import Optional, Tuple, Type
import logging

from golem_task_api import TaskApiService

from golem.envs import (
    Environment,
    Prerequisites,
    Runtime,
    RuntimePayload,
    RuntimeStatus,
)

logger = logging.getLogger(__name__)


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


async def wait_until_socket_open(host: str, port: int, timeout: float = 3.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with contextlib.closing(
                socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            if sock.connect_ex((host, port)) == 0:
                return
        await asyncio.sleep(0.05)
    raise Exception(f'Could not connect to socket ({host}, {port})')


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
        host, port = self._runtime.get_port_mapping(port)
        await wait_until_socket_open(host, port, 10.0)
        return host, port

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
        logger.debug('wait_until_shutdown_complete() runtime=%r', self._runtime)
        assert self._runtime is not None
        loop = asyncio.get_event_loop()
        await self._runtime.wait_until_stopped().asFuture(loop)
        logger.debug('done()')
