import os

DATA_DIRECTORY  = os.path.join(os.environ.get('GOLEM'), "examples/gnr/node_data")

class SimpleEnv:

    @classmethod
    def __envDirGuard(cls):
        if not os.path.exists(DATA_DIRECTORY):
            os.makedirs(DATA_DIRECTORY)

    @classmethod
    def envFileName(cls, filename):
        cls.__envDirGuard()

        if DATA_DIRECTORY in filename:
            return filename

        return os.path.join(DATA_DIRECTORY, filename)

    @classmethod
    def openEnvFile(cls, filename, options = 'a'):
        fname = cls.envFileName(filename)

        if not os.path.exists(fname):
            with open(fname, 'a'):
                os.utime(fname, None)

        return open(fname, options)
