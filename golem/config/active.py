# pylint: disable=unused-import
import os

from golem_sci.chains import MAINNET


if os.environ.get('GOLEM_ENVIRONMENT') == MAINNET:
    from golem.config.environments.mainnet import *  # noqa
else:
    from golem.config.environments.testnet import *  # noqa
