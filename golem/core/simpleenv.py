import os
import appdirs


class SimpleEnv(object):
    """ Metaclass that keeps information about golem configuration files location. """

    DATA_DIRECTORY = appdirs.user_config_dir("Golem")

    @classmethod
    def open_env_file(cls, filename, options='a'):
        """ Open configuration file with given option. Create file if it doesn"t exist.
        :param str filename: name of configuration file. File should be placed in configuration files folder
        :param str options: python open file mode options, eg. 'r', 'w' 'a'
        :return:
        """
        f_name = cls.env_file_name(filename)

        if not os.path.exists(f_name):
            with open(f_name, 'a'):
                os.utime(f_name, None)

        return open(f_name, options)

    @classmethod
    def env_file_name(cls, filename):
        """ Return full configuration file name adding configuration files location to the filename
        :param str filename: name of a file
        :return str: name of a file connected with path
        """
        cls.__env_dir_guard()

        if SimpleEnv.DATA_DIRECTORY in filename:
            return filename

        return os.path.join(SimpleEnv.DATA_DIRECTORY, filename)

    @classmethod
    def __env_dir_guard(cls):
        if not os.path.exists(SimpleEnv.DATA_DIRECTORY):
            os.makedirs(SimpleEnv.DATA_DIRECTORY)


