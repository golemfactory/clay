import semantic_version

from os import linesep
from os.path import abspath, dirname, join, sep

from setup_util import setup_commons


def get_golem_path():
    """
    Get a path to the Golem root dir
    :return: Golem root dir
    """
    return sep.join(dirname(abspath(__file__)).split(sep=sep)[:-2])


def update_ini():
    """
    Create a file ($GOLEM/.version.ini) with current Golem version
    """
    version_file = join(get_golem_path(), '.version.ini')
    version = semantic_version.Version(setup_commons.get_version())
    contents = ("[version]{sep}version = {version}{sep}"
                "number = {version_major}{sep}")
    contents = contents.format(
        sep=linesep,
        version=version,
        version_major=version.major,
    )
    with open(version_file, 'wb') as f_:
        f_.write(contents.encode('ascii'))


if __name__ == '__main__':
    update_ini()
