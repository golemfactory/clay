import logging
import os
import time
from copy import deepcopy
from pathlib import Path
from socket import socket, SocketIO, SHUT_WR
from threading import Thread, Lock
from time import sleep
from typing import Optional, Any, Dict, List, Type, ClassVar, \
    Tuple, Iterator, Union, Iterable

from dataclasses import dataclass, field, asdict
from docker.errors import APIError
from golem_task_api.envs import DOCKER_CPU_ENV_ID
from twisted.internet.defer import Deferred, inlineCallbacks, succeed
from twisted.internet.threads import deferToThread
from urllib3.contrib.pyopenssl import WrappedSocket

from golem import hardware
from golem.core.common import is_linux, is_windows, is_osx
from golem.docker.client import local_client
from golem.docker.config import CONSTRAINT_KEYS
from golem.docker.hypervisor import Hypervisor
from golem.docker.hypervisor.docker_for_mac import DockerForMac
from golem.docker.hypervisor.dummy import DummyHypervisor
from golem.docker.hypervisor.hyperv import HyperVHypervisor
from golem.docker.hypervisor.virtualbox import VirtualBoxHypervisor
from golem.envs import (
    BenchmarkResult,
    EnvConfig,
    EnvironmentBase,
    EnvMetadata,
    EnvStatus,
    EnvSupportStatus,
    Prerequisites,
    RuntimeBase,
    RuntimeId,
    RuntimeInput,
    RuntimeOutput,
    RuntimeOutputBase,
    RuntimePayload,
    RuntimeStatus,
    UsageCounter,
    UsageCounterValues
)
from golem.envs.docker import DockerRuntimePayload, DockerPrerequisites
from golem.envs.docker.whitelist import Whitelist

logger = logging.getLogger(__name__)

# Keys used by hypervisors for memory and CPU constraints
mem = CONSTRAINT_KEYS['mem']
cpu = CONSTRAINT_KEYS['cpu']

DOCKER_CPU_METADATA = EnvMetadata(
    id=DOCKER_CPU_ENV_ID,
    description='Docker environment using CPU'
)


@dataclass
class DockerCPUConfig(EnvConfig):
    # The directories this environment is allowed to work in
    work_dirs: List[Path] = field(default_factory=list)
    memory_mb: int = 1024
    cpu_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        dict_ = asdict(self)
        dict_['work_dirs'] = [str(work_dir) for work_dir in dict_['work_dirs']]
        return dict_

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DockerCPUConfig':
        data = data.copy()
        _work_dirs = data.pop('work_dirs')
        work_dirs = [Path(work_dir) for work_dir in _work_dirs]
        return cls(work_dirs=work_dirs, **data)


class DockerOutput(RuntimeOutputBase):

    def __init__(
            self, raw_output: Iterable[bytes], encoding: Optional[str] = None
    ) -> None:
        super().__init__(encoding=encoding)
        self._raw_output = raw_output

    def __iter__(self) -> Iterator[Union[str, bytes]]:
        buffer = b""

        for chunk in self._raw_output:
            buffer += chunk
            lines = buffer.split(b"\n")
            buffer = lines.pop()

            for line in lines:
                yield self._decode(line + b"\n")  # Keep the newline character

        if buffer:
            yield self._decode(buffer)


class InputSocket:
    """ Wrapper class providing uniform interface for different types of
        sockets. It is necessary due to poor design of attach_socket().
        Stdin socket is thread-safe (all operations use lock). """

    def __init__(self, sock: Union[WrappedSocket, SocketIO]) -> None:
        if isinstance(sock, WrappedSocket):
            self._sock: Union[WrappedSocket, socket] = sock
        elif isinstance(sock, SocketIO):
            self._sock = sock._sock
        else:
            raise TypeError(f"Invalid socket class: {sock.__class__}")
        self._lock = Lock()
        self._closed = False

    def write(self, data: bytes) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("Socket closed")
            self._sock.sendall(data)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            if isinstance(self._sock, socket):
                self._sock.shutdown(SHUT_WR)
            else:
                self._sock.shutdown()
            self._sock.close()
            self._closed = True

    def closed(self) -> bool:
        return self._closed


class DockerInput(RuntimeInput):

    def __init__(self, sock: InputSocket, encoding: Optional[str] = None) \
            -> None:
        super().__init__(encoding=encoding)
        self._sock = sock

    def write(self, data: Union[str, bytes]) -> None:
        encoded = self._encode(data)
        self._sock.write(encoded)

    def close(self):
        self._sock.close()


class ContainerPortMapper:
    def __init__(self, hypervisor: Hypervisor) -> None:
        self._hypervisor = hypervisor

    def get_port_mapping(self, container_id: str, port: int) -> Tuple[str, int]:
        return self._hypervisor.get_port_mapping(container_id, port)


class DockerCPURuntime(RuntimeBase):

    CONTAINER_RUNNING: ClassVar[List[str]] = ["running"]
    CONTAINER_STOPPED: ClassVar[List[str]] = ["exited", "dead"]

    STATUS_UPDATE_INTERVAL = 1.0  # seconds

    def __init__(
            self,
            container_config: Dict[str, Any],
            port_mapper: ContainerPortMapper,
            runtime_logger: Optional[logging.Logger] = None,
    ) -> None:
        super().__init__(logger=runtime_logger or logger)

        client = local_client()

        self._status_update_thread: Optional[Thread] = None
        self._container_id: Optional[str] = None
        self._stdin_socket: Optional[InputSocket] = None
        self._port_mapper = port_mapper

        self._counter_update_thread: Optional[Thread] = None
        self._counters = UsageCounterValues()
        self._num_samples = 0

        self._container_config = client.create_container_config(
            **container_config)

    def _inspect_container(self) -> Tuple[str, int]:
        """ Inspect Docker container associated with this runtime. Returns
            (status, exit_code) tuple. """
        assert self._container_id is not None
        client = local_client()
        inspection = client.inspect_container(self._container_id)
        state = inspection["State"]
        return state["Status"], state["ExitCode"]

    def _update_status(self) -> None:
        """ Check status of the container and update the Runtime's status
            accordingly. Assumes the container has been started and not
            removed. Uses lock for status read & write. """

        with self._status_lock:
            if self._status != RuntimeStatus.RUNNING:
                return

            self._logger.debug("Updating runtime status...")

            try:
                container_status, exit_code = self._inspect_container()
            except (APIError, KeyError) as e:
                self._error_occurred(e, "Error inspecting container.")
                return

            if container_status in self.CONTAINER_RUNNING:
                self._logger.debug("Container still running, no status update.")

            elif container_status in self.CONTAINER_STOPPED:
                if exit_code == 0:
                    self._stopped()
                else:
                    self._error_occurred(
                        None, f"Container stopped with exit code {exit_code}.")

            else:
                self._error_occurred(
                    None, f"Unexpected container status: '{container_status}'.")

    def _update_status_loop(self) -> None:
        """ Periodically call _update_status(). Stop when the container is no
            longer running. """
        while self.status() == RuntimeStatus.RUNNING:
            self._update_status()
            sleep(self.STATUS_UPDATE_INTERVAL)

        self._logger.info("Runtime is no longer running. "
                          "Stopping status update thread.")

    def _update_counters(self) -> None:
        start_time = time.time()
        client = local_client()
        stream = iter(
            client.stats(self._container_id, decode=True, stream=True))

        # Container cannot be removed when the stream is being read and the
        # stream will not terminate until the container is removed.
        # Therefore an explicit status check is needed.
        active_status = (RuntimeStatus.RUNNING, RuntimeStatus.STARTING)
        while self.status() in active_status:
            self._counters.clock_ms = (time.time() - start_time) * 1000

            try:
                stats = next(stream)
            except StopIteration:
                break
            except APIError:
                logger.error("Cannot get docker stats")
                continue

            try:
                cpu_stats = stats['cpu_stats']['cpu_usage']
                logger.debug("CPU usage: %r", cpu_stats)
                # Using max because Docker sometimes output all zeros when the
                # container is shutting down.
                self._counters.cpu_kernel_ns = max(
                    self._counters.cpu_kernel_ns,
                    cpu_stats['usage_in_kernelmode'])
                self._counters.cpu_user_ns = max(
                    self._counters.cpu_user_ns,
                    cpu_stats['usage_in_usermode'])
                self._counters.cpu_total_ns = max(
                    self._counters.cpu_total_ns,
                    cpu_stats['total_usage'])

                mem_stats = stats['memory_stats']
                logger.debug("RAM usage: %r", mem_stats)
                self._counters.ram_max_bytes = mem_stats['max_usage']
                total_usage = self._counters.ram_avg_bytes * self._num_samples
                self._counters.ram_avg_bytes = (
                    (total_usage + mem_stats['usage']) /
                    (self._num_samples + 1)
                )

                self._num_samples += 1
            except (KeyError, TypeError):
                if self.status() is RuntimeStatus.RUNNING:
                    self._logger.warning("Invalid Docker stats: %r", stats)

    def id(self) -> Optional[RuntimeId]:
        return self._container_id

    def prepare(self) -> Deferred:
        self._change_status(
            from_status=RuntimeStatus.CREATED,
            to_status=RuntimeStatus.PREPARING)
        self._logger.info("Preparing runtime...")

        def _prepare():
            client = local_client()
            result = client.create_container_from_config(self._container_config)

            container_id = result.get("Id")
            assert isinstance(container_id, str), "Invalid container ID"
            self._container_id = container_id

            for warning in result.get("Warnings") or []:
                self._logger.warning("Container creation warning: %s", warning)

            sock = client.attach_socket(
                container_id, params={'stdin': True, 'stream': True}
            )
            self._stdin_socket = InputSocket(sock)

        deferred_prepare = deferToThread(_prepare)
        deferred_prepare.addCallback(self._prepared)
        deferred_prepare.addErrback(self._error_callback(
            "Creating container failed."))
        return deferred_prepare

    def clean_up(self) -> Deferred:
        self._change_status(
            from_status=[RuntimeStatus.FAILURE, RuntimeStatus.STOPPED],
            to_status=RuntimeStatus.CLEANING_UP)
        self._logger.info("Cleaning up runtime...")

        def _clean_up():
            client = local_client()
            client.remove_container(self._container_id)

        # Close STDIN in case it wasn't closed on stop()
        def _close_stdin(res):
            if self._stdin_socket is not None:
                self._stdin_socket.close()
            return res

        deferred_cleanup = deferToThread(_clean_up)
        deferred_cleanup.addCallback(self._torn_down)
        deferred_cleanup.addErrback(self._error_callback(
            f"Failed to remove container '{self._container_id}'."))
        deferred_cleanup.addBoth(_close_stdin)
        return deferred_cleanup

    def start(self) -> Deferred:
        self._change_status(
            from_status=RuntimeStatus.PREPARED,
            to_status=RuntimeStatus.STARTING)

        # Counter thread must be spawned before starting the container because
        # some containers exit so fast we wouldn't get any stats otherwise.
        self._logger.debug("Spawning counter update thread...")
        self._counter_update_thread = Thread(target=self._update_counters)
        self._counter_update_thread.start()
        self._logger.debug("Status counter thread spawned.")

        def _start():
            self._logger.info("Starting container '%s'...", self._container_id)
            client = local_client()
            client.start(self._container_id)

        def _spawn_status_update_thread(_):
            self._logger.debug("Spawning status update thread...")
            self._status_update_thread = Thread(target=self._update_status_loop)
            self._status_update_thread.start()
            self._logger.debug("Status update thread spawned.")

        deferred_start = deferToThread(_start)
        deferred_start.addCallback(self._started)
        deferred_start.addCallback(_spawn_status_update_thread)
        deferred_start.addErrback(self._error_callback(
            f"Starting container '{self._container_id}' failed."))
        return deferred_start

    def stop(self) -> Deferred:
        with self._status_lock:
            self._assert_status(self._status, RuntimeStatus.RUNNING)
        self._logger.info("Stopping container '%s'...", self._container_id)

        def _stop():
            client = local_client()
            client.stop(self._container_id)

        def _join_counter_update_thread(res):
            self._logger.debug("Joining counter update thread...")
            self._counter_update_thread.join(1)
            if self._counter_update_thread.is_alive():
                self._logger.warning("Failed to join counter update thread.")
            else:
                self._logger.debug("Counter update thread joined.")
            return res

        def _join_status_update_thread(res):
            self._logger.debug("Joining status update thread...")
            self._status_update_thread.join(self.STATUS_UPDATE_INTERVAL * 2)
            if self._status_update_thread.is_alive():
                self._logger.warning("Failed to join status update thread.")
            else:
                self._logger.debug("Status update thread joined.")
            return res

        def _close_stdin(res):
            if self._stdin_socket is not None:
                self._stdin_socket.close()
            return res

        deferred_stop = deferToThread(_stop)
        deferred_stop.addCallback(self._stopped)
        deferred_stop.addErrback(self._error_callback(
            f"Stopping container '{self._container_id}' failed."))
        deferred_stop.addBoth(_join_counter_update_thread)
        deferred_stop.addBoth(_join_status_update_thread)
        deferred_stop.addBoth(_close_stdin)
        return deferred_stop

    def stdin(self, encoding: Optional[str] = None) -> RuntimeInput:
        self._assert_status(
            self.status(), [
                RuntimeStatus.PREPARED,
                RuntimeStatus.STARTING,
                RuntimeStatus.RUNNING
            ])
        assert self._stdin_socket is not None
        return DockerInput(sock=self._stdin_socket, encoding=encoding)

    def _get_raw_output(self, stdout=False, stderr=False, stream=True) \
            -> Iterable[bytes]:
        """ Attach to the output (STDOUT or STDERR) of a container. If stream
            is True the returned value is an iterator that advances when
            something is printed by the container. Otherwise, it is a list
            containing single `bytes` object with all output data. An empty
            list is returned if error occurs. """

        assert stdout or stderr
        assert self._container_id is not None
        self._logger.debug(
            "Attaching to output of container '%s'...", self._container_id)
        client = local_client()

        try:
            raw_output = client.attach(
                container=self._container_id,
                stdout=stdout, stderr=stderr, logs=True, stream=stream)
            self._logger.debug("Successfully attached to output.")
            # If not using stream the output is a single `bytes` object
            return raw_output if stream else [raw_output]
        except APIError as e:
            self._error_occurred(
                e, "Error attaching to container's output.", set_status=False)
            return []

    def _get_output(self, encoding: Optional[str] = None, **kwargs) \
            -> RuntimeOutput:
        """ Get output (STDERR or STDOUT) of this Runtime. """

        stream_available = [
            RuntimeStatus.PREPARED,
            RuntimeStatus.STARTING,
            RuntimeStatus.RUNNING
        ]
        self._assert_status(
            self.status(), stream_available + [
                RuntimeStatus.STOPPED,
                RuntimeStatus.FAILURE
            ])

        raw_output: Iterable[bytes] = []

        if self.status() in stream_available:
            raw_output = self._get_raw_output(stream=True, **kwargs)

        # If container is no longer running the stream will not work (it just
        # hangs forever). So we have to get all the output 'offline'.
        # Status update is needed because the container may have stopped
        # between checking and attaching to the output.
        self._update_status()
        if self.status() not in stream_available:
            self._logger.debug("Container no longer running. "
                               "Getting offline output.")
            raw_output = self._get_raw_output(stream=False, **kwargs)

        return DockerOutput(raw_output, encoding=encoding)

    def stdout(self, encoding: Optional[str] = None) -> RuntimeOutput:
        return self._get_output(stdout=True, encoding=encoding)

    def stderr(self, encoding: Optional[str] = None) -> RuntimeOutput:
        return self._get_output(stderr=True, encoding=encoding)

    def get_port_mapping(self, port: int) -> Tuple[str, int]:
        assert self._container_id is not None
        return self._port_mapper.get_port_mapping(self._container_id, port)

    def usage_counter_values(self) -> UsageCounterValues:
        return deepcopy(self._counters)


class DockerCPUEnvironment(EnvironmentBase):

    MIN_MEMORY_MB: ClassVar[int] = 1024
    MIN_CPU_COUNT: ClassVar[int] = 1

    NETWORK_MODE: ClassVar[str] = 'bridge'
    DNS_SERVERS: ClassVar[List[str]] = []
    DNS_SEARCH_DOMAINS: ClassVar[List[str]] = []
    DROPPED_KERNEL_CAPABILITIES: ClassVar[List[str]] = [
        'audit_control',
        'audit_write',
        'mac_admin',
        'mac_override',
        'mknod',
        'net_admin',
        'net_bind_service',
        'net_raw',
        'setfcap',
        'setpcap',
        'sys_admin',
        'sys_boot',
        'sys_chroot',
        'sys_module',
        'sys_nice',
        'sys_pacct',
        'sys_resource',
        'sys_time',
        'sys_tty_config'
    ]

    BENCHMARK_IMAGE = 'golemfactory/cpu_benchmark:1.0'

    @classmethod
    def supported(cls) -> EnvSupportStatus:
        if cls._get_hypervisor_class() is None:
            return EnvSupportStatus(False, "No supported hypervisor found")
        return EnvSupportStatus(True)

    @classmethod
    def _get_hypervisor_class(cls) -> Optional[Type[Hypervisor]]:
        if is_linux():
            return DummyHypervisor
        if is_windows():
            if HyperVHypervisor.is_available():
                return HyperVHypervisor
            if VirtualBoxHypervisor.is_available():
                return VirtualBoxHypervisor
        if is_osx():
            if DockerForMac.is_available():
                return DockerForMac
        return None

    def __init__(
            self,
            config: DockerCPUConfig,
            env_logger: Optional[logging.Logger] = None,
    ) -> None:
        super().__init__(logger=env_logger or logger)
        self._validate_config(config)
        self._config = config

        hypervisor_cls = self._get_hypervisor_class()
        if hypervisor_cls is None:
            raise EnvironmentError("No supported hypervisor found")
        self._hypervisor = hypervisor_cls.instance(self._get_hypervisor_config)
        self._port_mapper = ContainerPortMapper(self._hypervisor)
        self._update_work_dirs(config.work_dirs)
        self._constrain_hypervisor(config)

    def _get_hypervisor_config(self) -> Dict[str, int]:
        return {
            mem: self._config.memory_mb,
            cpu: self._config.cpu_count
        }

    def prepare(self) -> Deferred:
        if self._status != EnvStatus.DISABLED:
            raise ValueError(f"Cannot prepare because environment is in "
                             f"invalid state: '{self._status}'")
        self._status = EnvStatus.PREPARING
        self._logger.info("Preparing environment...")

        def _prepare():
            try:
                self._hypervisor.setup()
            except Exception as e:
                self._error_occurred(e, "Preparing environment failed.")
                raise
            self._env_enabled()

        return deferToThread(_prepare)

    def clean_up(self) -> Deferred:
        if self._status not in [EnvStatus.ENABLED, EnvStatus.ERROR]:
            raise ValueError(f"Cannot clean up because environment is in "
                             f"invalid state: '{self._status}'")
        self._status = EnvStatus.CLEANING_UP
        self._logger.info("Cleaning up environment...")

        def _clean_up():
            try:
                self._hypervisor.quit()
            except Exception as e:
                self._error_occurred(e, "Cleaning up environment failed.")
                raise
            self._env_disabled()

        return deferToThread(_clean_up)

    @inlineCallbacks
    def run_benchmark(self) -> Deferred:
        image, tag = self.BENCHMARK_IMAGE.split(':')
        yield self.install_prerequisites(DockerPrerequisites(
            image=image,
            tag=tag,
        ))
        payload = DockerRuntimePayload(
            image=image,
            tag=tag,
            user=None if is_windows() else str(os.getuid()),
            env={},
        )
        runtime = self.runtime(payload)
        yield runtime.prepare()
        # Connect to stdout before starting the runtime because getting if after
        # the container stops sometimes fails for unclear reasons
        stdout = runtime.stdout('utf-8')
        yield runtime.start()
        yield runtime.wait_until_stopped()
        try:
            if runtime.status() == RuntimeStatus.FAILURE:
                raise RuntimeError('Benchmark run failed.')
            # Benchmark is supposed to output a single line containing a float
            benchmark_result = BenchmarkResult()
            benchmark_result.performance = float(list(stdout)[0])
            return benchmark_result
        finally:
            yield runtime.clean_up()

    @classmethod
    def parse_prerequisites(cls, prerequisites_dict: Dict[str, Any]) \
            -> DockerPrerequisites:
        return DockerPrerequisites(**prerequisites_dict)

    def install_prerequisites(self, prerequisites: Prerequisites) -> Deferred:
        assert isinstance(prerequisites, DockerPrerequisites)
        if self._status != EnvStatus.ENABLED:
            raise ValueError(f"Cannot prepare prerequisites because environment"
                             f"is in invalid state: '{self._status}'")
        self._logger.info("Preparing prerequisites...")

        if not Whitelist.is_whitelisted(prerequisites.image):
            self._logger.info(
                "Docker image '%s' is not whitelisted.",
                prerequisites.image,
            )
            return succeed(False)

        def _prepare():
            try:
                client = local_client()
                client.pull(
                    prerequisites.image,
                    tag=prerequisites.tag
                )
            except Exception as e:
                self._error_occurred(
                    e, "Preparing prerequisites failed.", set_status=False)
                raise
            self._prerequisites_installed(prerequisites)
            return True

        return deferToThread(_prepare)

    @classmethod
    def parse_config(cls, config_dict: Dict[str, Any]) -> DockerCPUConfig:
        return DockerCPUConfig(**config_dict)

    def config(self) -> DockerCPUConfig:
        return deepcopy(self._config)

    def update_config(self, config: EnvConfig) -> None:
        assert isinstance(config, DockerCPUConfig)
        if self._status != EnvStatus.DISABLED:
            raise ValueError(
                "Config can be updated only when the environment is disabled")
        self._logger.info("Updating environment configuration...")

        self._logger.info("Validating configuration...")
        self._validate_config(config)
        self._logger.info("Configuration positively validated.")

        if config.work_dirs != self._config.work_dirs:
            self._update_work_dirs(config.work_dirs)
        self._constrain_hypervisor(config)
        self._config = self.parse_config(asdict(config))
        self._config_updated(config)

    @classmethod
    def _validate_config(cls, config: DockerCPUConfig) -> None:
        for work_dir in config.work_dirs:
            if not work_dir.is_dir():
                raise ValueError(f"Invalid working directory: '{work_dir}'")
            # Check for duplicates, not allowed
            if config.work_dirs.count(work_dir) > 1:
                raise ValueError(f"Duplicate working directory: '{work_dir}'")
            # Check for parents, not allowed
            for check_dir in config.work_dirs:
                if check_dir == work_dir:
                    continue
                if work_dir in check_dir.parents:
                    raise ValueError("Working dir can not be parent: parent="
                                     f"'{work_dir}', child='{check_dir}'")
                if check_dir in work_dir.parents:
                    raise ValueError("Working dir can not be parent: parent="
                                     f"'{check_dir}', child='{work_dir}'")
        if config.memory_mb < cls.MIN_MEMORY_MB:
            raise ValueError(f"Not enough memory: {config.memory_mb} MB")
        if config.cpu_count < cls.MIN_CPU_COUNT:
            raise ValueError(f"Not enough CPUs: {config.cpu_count}")

    def _update_work_dirs(self, work_dirs: List[Path]) -> None:
        self._logger.info("Updating hypervisor's working directory...")
        try:
            self._hypervisor.update_work_dirs(work_dirs)
        except Exception as e:
            self._error_occurred(e, "Updating working directory failed.")
            raise
        self._logger.info("Working directory successfully updated.")

    def _constrain_hypervisor(self, config: DockerCPUConfig) -> None:
        current = self._hypervisor.constraints()
        target = {
            mem: config.memory_mb,
            cpu: config.cpu_count
        }

        if target == current:
            self._logger.info("No need to reconfigure hypervisor.")
            return

        self._logger.info("Hypervisor configuration differs. "
                          "Reconfiguring hypervisor...")
        try:
            with self._hypervisor.reconfig_ctx():
                self._hypervisor.constrain(**target)
        except Exception as e:
            self._error_occurred(e, "Reconfiguring hypervisor failed.")
            raise
        self._logger.info("Hypervisor successfully reconfigured.")

    def supported_usage_counters(self) -> List[UsageCounter]:
        return [
            UsageCounter.CLOCK_MS,
            UsageCounter.CPU_TOTAL_NS,
            UsageCounter.CPU_USER_NS,
            UsageCounter.CPU_KERNEL_NS,
            UsageCounter.RAM_MAX_BYTES,
            UsageCounter.RAM_AVG_BYTES
        ]

    def runtime(
            self,
            payload: RuntimePayload,
            config: Optional[EnvConfig] = None
    ) -> DockerCPURuntime:
        assert isinstance(payload, DockerRuntimePayload)
        if not Whitelist.is_whitelisted(payload.image):
            raise RuntimeError(f"Image '{payload.image}' is not whitelisted.")

        if config is not None:
            assert isinstance(config, DockerCPUConfig)
        else:
            config = self.config()

        return self._create_runtime(config, payload)

    def _create_host_config(
            self,
            config: DockerCPUConfig,
            payload: DockerRuntimePayload,
    ) -> Dict[str, Any]:
        cpus = hardware.cpus()[:config.cpu_count]
        cpuset_cpus = ','.join(map(str, cpus))
        mem_limit = f'{config.memory_mb}m'  # 'm' is for megabytes

        binds = None
        if payload.binds is not None:
            binds = self._hypervisor.create_volumes(payload.binds)

        port_bindings = None
        if payload.ports:
            port_bindings = {
                f'{port}/tcp': {'HostIp': '0.0.0.0', 'HostPort': port}
                for port in payload.ports
            }

        client = local_client()
        return client.create_host_config(
            cpuset_cpus=cpuset_cpus,
            mem_limit=mem_limit,
            binds=binds,
            port_bindings=port_bindings,
            privileged=False,
            network_mode=self.NETWORK_MODE,
            dns=self.DNS_SERVERS,
            dns_search=self.DNS_SEARCH_DOMAINS,
            cap_drop=self.DROPPED_KERNEL_CAPABILITIES
        )

    def _create_container_config(
            self,
            config: DockerCPUConfig,
            payload: DockerRuntimePayload,
    ) -> Dict[str, Any]:
        image = f"{payload.image}:{payload.tag}"
        volumes = [b.target for b in payload.binds] if payload.binds else None
        host_config = self._create_host_config(config, payload)
        ports = [(p, 'tcp') for p in payload.ports] if payload.ports else None

        return dict(
            image=image,
            volumes=volumes,
            command=payload.command,
            user=payload.user,
            environment=payload.env,
            working_dir=payload.work_dir,
            ports=ports,
            host_config=host_config,
            stdin_open=True
        )

    def _create_runtime(
            self,
            config: DockerCPUConfig,
            payload: DockerRuntimePayload,
    ) -> DockerCPURuntime:
        container_config = self._create_container_config(config, payload)

        return DockerCPURuntime(
            container_config,
            self._port_mapper,
            runtime_logger=self._logger)
