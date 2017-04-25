from setup.setup_commons import file_name
from golem.core.common import get_golem_path

from os.path import join


def update_ini():
    version_file = join(get_golem_path(), '.version.ini')
    file_name_ = file_name().split('-')
    tag = file_name_[1]
    commit = file_name_[2]
    version = "[version]\nversion = {}\n".format(tag + ("-" + commit) if commit.startswith('0x') else "")
    with open(version_file, 'wb') as f_:
        f_.write(version)

if __name__ == '__main__':
    update_ini()
