import logging
from pathlib import Path
from threading import Thread
from typing import Optional

from twisted.internet.defer import Deferred, inlineCallbacks

from golem.envs import (
    EnvConfig,
    Environment,
    Runtime,
    RuntimeOutput,
    RuntimePayload,
)
from golem.envs.wrappers import EnvironmentWrapper, RuntimeWrapper

logger = logging.getLogger(__name__)


class RuntimeLogsWrapper(RuntimeWrapper):

    def __init__(
            self,
            runtime: Runtime,
            logs_dir: Path,
            encoding: str = 'utf-8'
    ) -> None:
        super().__init__(runtime)
        self._logs_dir = logs_dir
        self._encoding = encoding
        self._stdout_thread: Optional[Thread] = None
        self._stderr_thread: Optional[Thread] = None

    def _dump_output(self, output: RuntimeOutput, path: Path) -> None:
        logger.info('Dumping runtime output to %r', path)
        with path.open(mode='w', encoding=self._encoding) as file:
            file.writelines(output)

    @inlineCallbacks
    def prepare(self) -> Deferred:
        yield super().prepare()
        stdout_file = self._logs_dir / f'{self._runtime.id()}_stdout.txt'
        stderr_file = self._logs_dir / f'{self._runtime.id()}_stderr.txt'
        stdout = self._runtime.stdout(self._encoding)
        stderr = self._runtime.stderr(self._encoding)
        self._stdout_thread = Thread(
            target=self._dump_output,
            args=(stdout, stdout_file))
        self._stderr_thread = Thread(
            target=self._dump_output,
            args=(stderr, stderr_file))
        self._stdout_thread.start()
        self._stderr_thread.start()

    @inlineCallbacks
    def clean_up(self) -> Deferred:
        assert self._stdout_thread is not None
        assert self._stderr_thread is not None
        yield super().clean_up()
        self._stdout_thread.join(5)
        if self._stdout_thread.is_alive():
            logger.warning('Cannot join stdout thread')
        self._stderr_thread.join(5)
        if self._stderr_thread.is_alive():
            logger.warning('Cannot join stderr thread')


class EnvironmentLogsWrapper(EnvironmentWrapper):

    def __init__(
            self,
            env: Environment,
            logs_dir: Path,
            encoding: str = 'utf-8'
    ) -> None:
        super().__init__(env)
        self._logs_dir = logs_dir
        self._encoding = encoding

    def runtime(
            self,
            payload: RuntimePayload,
            config: Optional[EnvConfig] = None
    ) -> Runtime:
        runtime = super().runtime(payload, config)
        return RuntimeLogsWrapper(runtime, self._logs_dir, self._encoding)


def dump_logs(
        env: Environment,
        logs_dir: Path,
        encoding: str = 'utf-8'
) -> Environment:
    return EnvironmentLogsWrapper(
        env=env,
        logs_dir=logs_dir,
        encoding=encoding
    )
