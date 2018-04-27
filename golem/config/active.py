# pylint: disable=unused-import
import os

from golem_sci.chains import MAINNET

from golem.config.environments import GOLEM_ENVIRONMENT_VARIABLE, \
    CONCENT_ENVIRONMENT_VARIABLE
from golem.core import variables

if os.environ.get(GOLEM_ENVIRONMENT_VARIABLE) == MAINNET:
    from golem.config.environments.mainnet import *  # noqa
else:
    from golem.config.environments.testnet import *  # noqa

CONCENT_VARIANT = variables.CONCENT_CHOICES[
    os.environ.get(CONCENT_ENVIRONMENT_VARIABLE, 'disabled')
]
