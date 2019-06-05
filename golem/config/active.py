# pylint: disable=unused-import
import os

from golem_sci.chains import MAINNET

from golem.config.environments import GOLEM_ENVIRONMENT_VARIABLE

if os.environ.get(GOLEM_ENVIRONMENT_VARIABLE) == MAINNET:
    from golem.config.environments.mainnet import *  # noqa
else:
    from golem.config.environments.testnet import *  # type: ignore  # pylint:disable=unused-wildcard-import, wildcard-import
