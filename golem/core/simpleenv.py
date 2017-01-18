import os

import appdirs


def get_local_datadir(name):
    """ Helper function for datadir transition.

        It returns path to a data directory of given name in 'data' dir.
        Usage should be avoid at all costs. It is always better to ask for
        a dir the upper layer (like Client instance).
        """
    return os.path.join(appdirs.user_data_dir('golem'), name)


class SimpleEnv(object):
    """ Metaclass that keeps information about golem configuration files location. """

    @staticmethod
    def env_file_name(filename):
        """ Return full configuration file name adding configuration files location to the filename
        :param str filename: name of a file
        :return str: name of a file connected with path
        """
        # FIXME: Deprecated!

        datadir = get_local_datadir('SimpleEnv')
        if not os.path.exists(datadir):
            os.makedirs(datadir)

        return os.path.join(datadir, filename)
