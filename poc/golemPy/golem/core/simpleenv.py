import os

DATA_DIRECTORY = os.path.join(os.environ.get("GOLEM"), "examples/gnr/node_data")


class SimpleEnv(object):
    """ Metaclass that keeps information about golem configuration files location. """

    @classmethod
    def open_env_file(cls, filename, options='a'):
        """ Open configuration file with given option. Create file if it doesn"t exist.
        :param str filename: name of configuration file. File should be placed in configuration files folder
        :param str options: python open file mode options, eg. 'r', 'w' 'a'
        :return:
        """
        f_name = cls.__env_file_name(filename)

        if not os.path.exists(f_name):
            with open(f_name, 'a'):
                os.utime(f_name, None)

        return open(f_name, options)

    @classmethod
    def __env_dir_guard(cls):
        if not os.path.exists(DATA_DIRECTORY):
            os.makedirs(DATA_DIRECTORY)

    @classmethod
    def __env_file_name(cls, filename):
        cls.__env_dir_guard()

        if DATA_DIRECTORY in filename:
            return filename

        return os.path.join(DATA_DIRECTORY, filename)
