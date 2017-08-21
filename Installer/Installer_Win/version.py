from os.path import abspath, dirname, join, sep
from sys import platform

from git import Repo


def get_golem_path():
    """
    Get a path to the Golem root dir
    :return: Golem root dir
    """
    return sep.join(dirname(abspath(__file__)).split(sep=sep)[:-2])


def get_tag():
    """
    Get wheel name
    :return: Name for wheel
    """
    repo = Repo(get_golem_path())
    tag = repo.tags[-2]  # get latest tag
    tag_id = tag.commit.hexsha  # get commit id from tag
    commit_id = repo.head.commit.hexsha  # get last commit id
    if platform.startswith('linux'):
        from platform import architecture
        if architecture()[0].startswith('64'):
            plat = "linux_x86_64"
        else:
            plat = "linux_i386"
    elif platform.startswith('win'):
        plat = "win32"
    elif platform.startswith('darwin'):
        plat = "macosx_10_12_x86_64"
    else:
        raise SystemError("Incorrect platform: {}".format(platform))
    if commit_id != tag_id:  # devel package
        return "{}-0x{}{}".format(tag.name, commit_id[:4], commit_id[-4:])
    else:  # release package
        return "{}".format(tag.name)


def update_ini():
    """
    Create a file ($GOLEM/.version.ini) with current Golem version
    """
    version_file = join(get_golem_path(), '.version.ini')
    repo_tag = get_tag().split('-')
    version = "[version]\nversion = {}{}\n".format(repo_tag[0], ("-" + repo_tag[1]) if len(repo_tag) > 1 else "")
    with open(version_file, 'wb') as f_:
        f_.write(version.encode('ascii'))


if __name__ == '__main__':
    update_ini()
