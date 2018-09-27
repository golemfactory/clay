# pylint: skip-file
import os

import appdirs

def get_local_datadir(name: str, root_dir=None, use_mainnet=False) -> str:
    """ Helper function for datadir transition.

        It returns path to a data directory of given name in 'data' dir.
        Usage should be avoid at all costs. It is always better to ask for
        a dir the upper layer (like Client instance).
    """
    from golem.config.active import DATA_DIR # type: ignore
    from golem.config.environments.mainnet import DATA_DIR \
                                           as mainnet_data_dir  # noqa

    if use_mainnet:
        data_subdir = mainnet_data_dir
    else:
        data_subdir = DATA_DIR

    if not root_dir:
        root_dir = os.path.join(appdirs.user_data_dir('golem'), name)
    return os.path.join(root_dir, data_subdir)
