# type: ignore
# pylint: skip-file
import os

import appdirs

def get_local_datadir(name: str, root_dir=None, data_subdir=None) -> str:
    """ Helper function for datadir transition.

        It returns path to a data directory of given name in 'data' dir.
        Usage should be avoid at all costs. It is always better to ask for
        a dir the upper layer (like Client instance).
    """
    if not data_subdir:
        from golem.config.active import DATA_DIR \
                                     as data_subdir # type: ignore # noqa

    if not root_dir:
        root_dir = os.path.join(appdirs.user_data_dir('golem'), name)
    return os.path.join(root_dir, data_subdir)
