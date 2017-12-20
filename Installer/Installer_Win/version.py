from os import linesep
from os.path import abspath, dirname, join, sep

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
    tag = repo.tags[-1]  # get latest tag
    commit_id = repo.head.commit.hexsha  # get last commit id
    for rel_tag in repo.tags:
        if rel_tag.commit.hexsha == commit_id:
            tag = rel_tag
            break

    tag_id = tag.commit.hexsha  # get commit id from tag
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
    version = "[version]{0}version = {1}{2}{0}number = {1}{0}".format(linesep, repo_tag[0],
                                                                      ("-" + repo_tag[1]) if len(repo_tag) > 1 else "")
    with open(version_file, 'wb') as f_:
        f_.write(version.encode('ascii'))


if __name__ == '__main__':
    update_ini()
