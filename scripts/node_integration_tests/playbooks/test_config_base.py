import os
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
)
from scripts.node_integration_tests import helpers


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
        return args

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.__dict__}"


def make_node_config_from_env(role: str, counter: int) -> NodeConfig:
    node_config = NodeConfig()
    node_config.concent = os.environ.get('GOLEM_CONCENT_VARIANT',
                                         node_config.concent)
    node_config.log_level = 'DEBUG'
    node_config.password = os.environ.get(f'GOLEM_{role}_PASSWORD',
                                          node_config.password)
    node_config.rpc_port = \
        int(os.environ.get(f'GOLEM_{role}_RPC_PORT', 61000 + counter))
    return node_config


class TestConfigBase:
    def __init__(self, *, task_settings: str = 'default') -> None:
        self.dump_output_on_crash = False
        self.dump_output_on_fail = False

        self.requestor: Union[None, NodeConfig, List[NodeConfig]] = \
            make_node_config_from_env('REQUESTOR', 0)
        self.provider: Union[None, NodeConfig, List[NodeConfig]] = \
            make_node_config_from_env('PROVIDER', 1)
        self._nodes_index = 0
        self.task_package = 'test_task_1'
        self.task_settings = task_settings
        self.task_dict = helpers.construct_test_task(
            task_package_name=self.task_package,
            task_settings=self.task_settings,
        )

    @property
    def current_requestor(self) -> Optional[NodeConfig]:
        if isinstance(self.requestor, list):
            return self.requestor[min(self._nodes_index, len(self.requestor)-1)]
        return self.requestor

    @property
    def current_provider(self) -> Optional[NodeConfig]:
        if isinstance(self.provider, list):
            return self.provider[min(self._nodes_index, len(self.provider)-1)]
        return self.provider

    def use_next_nodes(self) -> None:
        self._nodes_index += 1

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.__dict__}"
