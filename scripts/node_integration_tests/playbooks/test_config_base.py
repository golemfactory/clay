import aenum
import os
from typing import (
    Any,
    Dict,
    List,
    Optional,
    TYPE_CHECKING,
    Union,
)
from scripts.node_integration_tests import helpers

if TYPE_CHECKING:
    from pathlib import Path

    # This prevents mypy from freaking out about enum it doesn't understand.
    requestor = None
    provider = None


class NodeConfig:
    def __init__(self) -> None:
        self.concent = 'staging'
        # if datadir is None it will be automatically created
        self.datadir: Optional[str] = None
        self.log_level: Optional[str] = None
        self.mainnet = False
        self.opts: Dict[str, Any] = {}
        self.password = 'dupa.8'
        self.protocol_id = 1337
        self.rpc_port = 61000
        self.script = 'node'
        self.hyperdrive_port: Optional[int] = None
        self.hyperdrive_rpc_port: Optional[int] = None

    def make_args(self) -> Dict[str, Any]:
        args = {
            '--accept-concent-terms': None,
            '--accept-terms': None,
            '--concent': self.concent,
            '--datadir': self.datadir,
            '--password': self.password,
            '--protocol_id': self.protocol_id,
            '--rpc-address': f'localhost:{self.rpc_port}',
        }
        if self.log_level is not None:
            args['--log-level'] = self.log_level
        if self.mainnet:
            args['--mainnet'] = None
        if self.hyperdrive_port:
            args['--hyperdrive-port'] = self.hyperdrive_port
        if self.hyperdrive_rpc_port:
            args['--hyperdrive-rpc-port'] = self.hyperdrive_rpc_port

        return args

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.__dict__}"


class NodeId(aenum.AutoEnum):
    """
    This enum holds commonly used nodes names.
    Feel free to extend this enum in your tests that require more nodes.
    """
    def _generate_next_value_(name, start, count, last_values):
        return name

    requestor
    provider


def make_node_config_from_env(role: str, counter: int) -> NodeConfig:
    role = role.upper()

    node_config = NodeConfig()
    node_config.concent = os.environ.get('GOLEM_CONCENT_VARIANT',
                                         node_config.concent)
    node_config.log_level = 'DEBUG'
    node_config.password = os.environ.get(f'GOLEM_{role}_PASSWORD',
                                          node_config.password)
    node_config.rpc_port = \
        int(os.environ.get(f'GOLEM_{role}_RPC_PORT',
                           node_config.rpc_port + counter))
    return node_config


class TestConfigBase:
    def __init__(self, *, task_settings: str = 'default') -> None:
        self.dump_output_on_crash = False
        self.dump_output_on_fail = False

        self.nodes: Dict[NodeId, Union[NodeConfig, List[NodeConfig]]] = {}
        for i, node_id in enumerate([NodeId.requestor, NodeId.provider]):
            self.nodes[node_id] = make_node_config_from_env(node_id.value, i)
        self._nodes_index = 0
        self.nodes_root: 'Optional[Path]' = None
        self.task_package = 'test_task_1'
        self.task_settings = task_settings
        self.task_dict = helpers.construct_test_task(
            task_package_name=self.task_package,
            task_settings=self.task_settings,
        )

    @property
    def current_nodes(self) -> Dict[NodeId, NodeConfig]:
        return {
            node_id: (
                node_config if isinstance(node_config, NodeConfig)
                else node_config[min(self._nodes_index, len(node_config)-1)]
            )
            for node_id, node_config in self.nodes.items()
        }

    def use_next_nodes(self) -> None:
        self._nodes_index += 1

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.__dict__}"
