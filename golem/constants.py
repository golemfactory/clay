import golem_messages
import semantic_version

import golem
from golem import utils

GOLEM_VERSION = semantic_version.Version(golem.__version__)
GOLEM_MESSAGES_VERSION = semantic_version.Version(golem_messages.__version__)
GOLEM_MESSAGES_SPEC = utils.get_version_spec(GOLEM_MESSAGES_VERSION)
