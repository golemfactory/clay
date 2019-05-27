import logging
from pathlib import Path
from socket import socket, SocketIO, SHUT_WR
from threading import Thread, Lock
from time import sleep
from typing import Optional, Any, Dict, List, Type, ClassVar, \
    NamedTuple, Tuple, Iterator, Union, Iterable

from docker.errors import APIError
from twisted.internet.defer import Deferred
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
from golem.docker.hypervisor.xhyve import XhyveHypervisor
from golem.docker.task_thread import DockerBind
from golem.envs import Environment, EnvSupportStatus, Payload, EnvConfig, \
    Runtime, EnvMetadata, EnvStatus, CounterId, CounterUsage, RuntimeStatus, \
    EnvId, Prerequisites, RuntimeOutput, RuntimeInput
from golem.envs.docker import DockerPayload, DockerPrerequisites
from golem.envs.docker.whitelist import Whitelist

logger = logging.getLogger(__name__)

# Keys used by hypervisors for memory and CPU constraints
mem = CONSTRAINT_KEYS['mem']
cpu = CONSTRAINT_KEYS['cpu']


class DockerCPUConfigData(NamedTuple):
    work_dir: Path
    memory_mb: int = 1024
    cpu_count: int = 1


class DockerCPUConfig(DockerCPUConfigData, EnvConfig):
    """ This exists because NamedTuple must be single superclass """

    def to_dict(self) -> Dict[str, Any]:
        dict_ = self._asdict()
        dict_['work_dir'] = str(dict_['work_dir'])
        return dict_

    @staticmethod
    def from_dict(dict_: Dict[str, Any]) -> 'DockerCPUConfig':
        work_dir = Path(dict_.pop('work_dir'))
        return DockerCPUConfig(work_dir=work_dir, **dict_)


class DockerOutput(RuntimeOutput):

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


class DockerCPURuntime(Runtime):

    CONTAINER_RUNNING: ClassVar[List[str]] = ["running"]
    CONTAINER_STOPPED: ClassVar[List[str]] = ["exited", "dead"]

    STATUS_UPDATE_INTERVAL = 1.0  # seconds

    def __init__(
            self,
            payload: DockerPayload,
            host_config: Dict[str, Any],
            volumes: Optional[List[str]]
    ) -> None:
        super().__init__(logger=logger)

        image = f"{payload.image}:{payload.tag}"
        client = local_client()

        self._status_update_thread: Optional[Thread] = None
        self._container_id: Optional[str] = None
        self._stdin_socket: Optional[InputSocket] = None
        self._container_config = client.create_container_config(
            image=image,
            volumes=volumes,
            command=payload.command,
            user=payload.user,
            environment=payload.env,
            working_dir=payload.work_dir,
            host_config=host_config,
            stdin_open=True
        )

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

            logger.debug("Updating runtime status...")

            try:
                container_status, exit_code = self._inspect_container()
            except (APIError, KeyError) as e:
                self._error_occurred(e, "Error inspecting container.")
                return

            if container_status in self.CONTAINER_RUNNING:
                logger.debug("Container still running, no status update.")

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

        logger.info("Runtime is no longer running. "
                    "Stopping status update thread.")

    def prepare(self) -> Deferred:
        self._change_status(
            from_status=RuntimeStatus.CREATED,
            to_status=RuntimeStatus.PREPARING)
        logger.info("Preparing runtime...")

        def _prepare():
            client = local_client()
            result = client.create_container_from_config(self._container_config)

            container_id = result.get("Id")
            assert isinstance(container_id, str), "Invalid container ID"
            self._container_id = container_id

            for warning in result.get("Warnings") or []:
                logger.warning("Container creation warning: %s", warning)

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
        logger.info("Cleaning up runtime...")

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
        logger.info("Starting container '%s'...", self._container_id)

        def _start():
            client = local_client()
            client.start(self._container_id)

        def _spawn_status_update_thread(_):
            logger.debug("Spawning status update thread...")
            self._status_update_thread = Thread(target=self._update_status_loop)
            self._status_update_thread.start()
            logger.debug("Status update thread spawned.")

        deferred_start = deferToThread(_start)
        deferred_start.addCallback(self._started)
        deferred_start.addCallback(_spawn_status_update_thread)
        deferred_start.addErrback(self._error_callback(
            f"Starting container '{self._container_id}' failed."))
        return deferred_start

    def stop(self) -> Deferred:
        with self._status_lock:
            self._assert_status(self._status, RuntimeStatus.RUNNING)
        logger.info("Stopping container '%s'...", self._container_id)

        def _stop():
            client = local_client()
            client.stop(self._container_id)

        def _join_status_update_thread(res):
            logger.debug("Joining status update thread...")
            self._status_update_thread.join(self.STATUS_UPDATE_INTERVAL * 2)
            if self._status_update_thread.is_alive():
                logger.warning("Failed to join status update thread.")
            else:
                logger.debug("Status update thread joined.")
            return res

        def _close_stdin(res):
            if self._stdin_socket is not None:
                self._stdin_socket.close()
            return res

        deferred_stop = deferToThread(_stop)
        deferred_stop.addCallback(self._stopped)
        deferred_stop.addErrback(self._error_callback(
            f"Stopping container '{self._container_id}' failed."))
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
        logger.debug(
            "Attaching to output of container '%s'...", self._container_id)
        client = local_client()

        try:
            raw_output = client.attach(
                container=self._container_id,
                stdout=stdout, stderr=stderr, logs=True, stream=stream)
            logger.debug("Successfully attached to output.")
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
            logger.debug("Container no longer running. Getting offline output.")
            raw_output = self._get_raw_output(stream=False, **kwargs)

        return DockerOutput(raw_output, encoding=encoding)

    def stdout(self, encoding: Optional[str] = None) -> RuntimeOutput:
        return self._get_output(stdout=True, encoding=encoding)

    def stderr(self, encoding: Optional[str] = None) -> RuntimeOutput:
        return self._get_output(stderr=True, encoding=encoding)

    def usage_counters(self) -> Dict[CounterId, CounterUsage]:
        raise NotImplementedError

    def call(self, alias: str, *args, **kwargs) -> Deferred:
        raise NotImplementedError


class DockerCPUEnvironment(Environment):

    ENV_ID: ClassVar[EnvId] = 'docker_cpu'
    ENV_DESCRIPTION: ClassVar[str] = 'Docker environment using CPU'

    MIN_MEMORY_MB: ClassVar[int] = 1024
    MIN_CPU_COUNT: ClassVar[int] = 1

    SHARED_DIR_PATH: ClassVar[str] = '/golem'

    NETWORK_MODE: ClassVar[str] = 'none'
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

    @classmethod
    def supported(cls) -> EnvSupportStatus:
        logger.info('Checking environment support status...')
        if cls._get_hypervisor_class() is None:
            return EnvSupportStatus(False, "No supported hypervisor found")
        logger.info('Environment supported.')
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
            if XhyveHypervisor.is_available():
                return XhyveHypervisor
        return None

    def __init__(self, config: DockerCPUConfig) -> None:
        super().__init__(logger=logger)
        self._validate_config(config)
        self._config = config

        hypervisor_cls = self._get_hypervisor_class()
        if hypervisor_cls is None:
            raise EnvironmentError("No supported hypervisor found")
        self._hypervisor = hypervisor_cls.instance(self._get_hypervisor_config)

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
        logger.info("Preparing environment...")

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
        logger.info("Cleaning up environment...")

        def _clean_up():
            try:
                self._hypervisor.quit()
            except Exception as e:
                self._error_occurred(e, "Cleaning up environment failed.")
                raise
            self._env_disabled()

        return deferToThread(_clean_up)

    @classmethod
    def metadata(cls) -> EnvMetadata:
        return EnvMetadata(
            id=cls.ENV_ID,
            description=cls.ENV_DESCRIPTION,
            supported_counters=[],  # TODO: Specify usage counters
            custom_metadata={}
        )

    @classmethod
    def parse_prerequisites(cls, prerequisites_dict: Dict[str, Any]) \
            -> DockerPrerequisites:
        return DockerPrerequisites(**prerequisites_dict)

    def install_prerequisites(self, prerequisites: Prerequisites) -> Deferred:
        assert isinstance(prerequisites, DockerPrerequisites)
        if self._status != EnvStatus.ENABLED:
            raise ValueError(f"Cannot prepare prerequisites because environment"
                             f"is in invalid state: '{self._status}'")
        logger.info("Preparing prerequisites...")

        def _prepare():
            if not Whitelist.is_whitelisted(prerequisites.image):
                logger.info(
                    "Docker image '%s' is not whitelisted.",
                    prerequisites.image,
                )
                return False
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
        return DockerCPUConfig(*self._config)

    def update_config(self, config: EnvConfig) -> None:
        assert isinstance(config, DockerCPUConfig)
        if self._status != EnvStatus.DISABLED:
            raise ValueError(
                "Config can be updated only when the environment is disabled")
        logger.info("Updating environment configuration...")

        self._validate_config(config)
        if config.work_dir != self._config.work_dir:
            self._update_work_dir(config.work_dir)
        self._constrain_hypervisor(config)
        self._config = DockerCPUConfig(*config)
        self._config_updated(config)

    @classmethod
    def _validate_config(cls, config: DockerCPUConfig) -> None:
        logger.info("Validating configuration...")
        if not config.work_dir.is_dir():
            raise ValueError(f"Invalid working directory: '{config.work_dir}'")
        if config.memory_mb < cls.MIN_MEMORY_MB:
            raise ValueError(f"Not enough memory: {config.memory_mb} MB")
        if config.cpu_count < cls.MIN_CPU_COUNT:
            raise ValueError(f"Not enough CPUs: {config.cpu_count}")
        logger.info("Configuration positively validated.")

    def _update_work_dir(self, work_dir: Path) -> None:
        logger.info("Updating hypervisor's working directory...")
        try:
            self._hypervisor.update_work_dir(work_dir)
        except Exception as e:
            self._error_occurred(e, "Updating working directory failed.")
            raise
        logger.info("Working directory successfully updated.")

    def _constrain_hypervisor(self, config: DockerCPUConfig) -> None:
        current = self._hypervisor.constraints()
        target = {
            mem: config.memory_mb,
            cpu: config.cpu_count
        }

        if target == current:
            logger.info("No need to reconfigure hypervisor.")
            return

        logger.info("Hypervisor configuration differs. "
                    "Reconfiguring hypervisor...")
        try:
            with self._hypervisor.reconfig_ctx():
                self._hypervisor.constrain(**target)
        except Exception as e:
            self._error_occurred(e, "Reconfiguring hypervisor failed.")
            raise
        logger.info("Hypervisor successfully reconfigured.")

    @classmethod
    def parse_payload(cls, payload_dict: Dict[str, Any]) -> DockerPayload:
        return DockerPayload.from_dict(payload_dict)

    def runtime(
            self,
            payload: Payload,
            shared_dir: Optional[Path] = None,
            config: Optional[EnvConfig] = None
    ) -> DockerCPURuntime:
        assert isinstance(payload, DockerPayload)
        if not Whitelist.is_whitelisted(payload.image):
            raise RuntimeError(f"Image '{payload.image}' is not whitelisted.")

        if config is not None:
            assert isinstance(config, DockerCPUConfig)
        else:
            config = self.config()

        host_config = self._create_host_config(config, shared_dir)
        volumes = [self.SHARED_DIR_PATH] if shared_dir else None
        return DockerCPURuntime(payload, host_config, volumes)

    def _create_host_config(
            self, config: DockerCPUConfig, shared_dir: Optional[Path]) \
            -> Dict[str, Any]:

        cpus = hardware.cpus()[:config.cpu_count]
        cpuset_cpus = ','.join(map(str, cpus))
        mem_limit = f'{config.memory_mb}m'  # 'm' is for megabytes

        if shared_dir is not None:
            binds = self._hypervisor.create_volumes([DockerBind(
                source=shared_dir,
                target=self.SHARED_DIR_PATH,
                mode='rw'
            )])
        else:
            binds = None

        client = local_client()
        return client.create_host_config(
            cpuset_cpus=cpuset_cpus,
            mem_limit=mem_limit,
            binds=binds,
            privileged=False,
            network_mode=self.NETWORK_MODE,
            dns=self.DNS_SERVERS,
            dns_search=self.DNS_SEARCH_DOMAINS,
            cap_drop=self.DROPPED_KERNEL_CAPABILITIES
        )
