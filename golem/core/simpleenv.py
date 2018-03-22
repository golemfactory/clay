import os

import appdirs


def get_local_datadir(name):
    """ Helper function for datadir transition.

        It returns path to a data directory of given name in 'data' dir.
        Usage should be avoid at all costs. It is always better to ask for
        a dir the upper layer (like Client instance).
        """
    return os.path.join(appdirs.user_data_dir('golem'), name)
