from contextlib import contextmanager

import peewee

from golem.database import schemas


def default_migrate_dir():
    return schemas.__path__[0]


@contextmanager
def patch_peewee(db_fields, db_models):
    """
    Temporarily assign all known models and field types to the peewee module.
    peewee_migrate assumes that all models and field types are located there.
    """

    undo = set()
    replace = dict()

    for db_class in db_fields + db_models:
        property_name = db_class.__name__

        if hasattr(peewee, property_name):
            replace[property_name] = getattr(peewee, property_name)
        else:
            undo.add(property_name)

        setattr(peewee, property_name, db_class)

    yield

    for name in undo:
        delattr(peewee, name)
    for name, value in replace.items():
        setattr(peewee, name, value)
