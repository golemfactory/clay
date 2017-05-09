import os

DENY_LIST_NAME = "deny.ini"


def get_deny_list(datadir, list_name=DENY_LIST_NAME):
    list_path = os.path.join(datadir, list_name)
    if not os.path.isfile(list_path):
        return []

    with open(list_path) as f:
        lines = f.readlines()

    return [line.strip() for line in lines]
