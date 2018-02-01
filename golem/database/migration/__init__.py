from golem.database import schemas


def default_migrate_dir():
    return schemas.__path__[0]
