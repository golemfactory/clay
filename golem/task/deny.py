import os

DENY_LIST_NAME = "deny.txt"


def get_deny_set(datadir, list_name=DENY_LIST_NAME):
    deny_set = set()

    list_path = os.path.join(datadir, list_name)
    if not os.path.isfile(list_path):
        return deny_set

    with open(list_path) as f:
        for line in f:
            deny_set.add(line.strip())

    return deny_set