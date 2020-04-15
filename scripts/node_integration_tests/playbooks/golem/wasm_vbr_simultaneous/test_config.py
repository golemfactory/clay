from aenum import extend_enum

from pathlib import Path

from ...test_config_base import (
    make_node_config_from_env,
    NodeId
)

from ..wasm_vbr_success.test_config import TestConfig as WasmVbrTestConfig

extend_enum(NodeId, 'provider3', 'provider3')


THIS_DIR: Path = Path(__file__).resolve().parent


class TestConfig(WasmVbrTestConfig):
    def __init__(self, *, task_settings: str = 'WASM_g_flite') -> None:
        super().__init__(task_settings=task_settings)
        self.nodes[NodeId.provider2].opts = {
            'overwrite_results': str(THIS_DIR.parent / "fake_result.png"),
        }

        self.nodes[NodeId.provider3] = make_node_config_from_env(
            NodeId.provider3.value, 3
        )
