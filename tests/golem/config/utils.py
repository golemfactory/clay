import importlib
import os
import sys
from contextlib import contextmanager
from typing import Optional, Generator
from unittest import mock

from golem_sci.chains import MAINNET

from golem.config.environments import GOLEM_ENVIRONMENT_VARIABLE, \
    CONCENT_ENVIRONMENT_VARIABLE
from golem.core.variables import PROTOCOL_CONST

CONFIG_MODULE = 'golem.config.active'


@contextmanager
def mock_config(net: Optional[str] = None) -> Generator:

    protocol_const = mock.Mock(ID=PROTOCOL_CONST.ID,
                               NUM=PROTOCOL_CONST.NUM,
                               POSTFIX=PROTOCOL_CONST.POSTFIX)

    with _patch_environment(net):
        if net:
            config_module = importlib.import_module(CONFIG_MODULE)
            _load_config(net, config_module)
            setattr(config_module, 'PROTOCOL_CONST', protocol_const)
        yield


@contextmanager
def _patch_environment(net) -> Generator:

    os_environ = dict(os.environ)
    os_environ.update({GOLEM_ENVIRONMENT_VARIABLE: net})
    os_environ.pop(CONCENT_ENVIRONMENT_VARIABLE, None)

    sys.modules.pop(CONFIG_MODULE, None)
    sys_modules = dict(sys.modules)

    with mock.patch('os.environ', os_environ):
        with mock.patch('sys.modules', sys_modules):
            yield os_environ, sys_modules


def _load_config(net, config_module):

    if net == MAINNET:
        from golem.config.environments import mainnet as module
    else:
        from golem.config.environments import testnet as module

    for name, value in module.__dict__.items():
        setattr(config_module, name, value)
