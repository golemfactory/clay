from ...test_config_base import (
    NodeId
)

from ..wasm_vbr_success.test_config import TestConfig as WasmVbrTestConfig


class TestConfig(WasmVbrTestConfig):
    def __init__(self, *, task_settings: str = 'WASM_g_flite') -> None:
        super().__init__(task_settings=task_settings)
        self.nodes[NodeId.provider].script = 'provider/offer_cancelled'
        del self.nodes[NodeId.provider2]
