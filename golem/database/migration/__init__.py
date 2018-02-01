import inspect
from contextlib import contextmanager

import peewee

import golem
from golem.database import schemas


def default_migrate_dir():
    return schemas.__path__[0]


@contextmanager
def patch_peewee():
    """
    Temporarily assign all known models and field types to the peewee module.
    peewee_migrate assumes that all models and field types are located there.
    """

    def is_field(cls):
        return inspect.isclass(cls) and issubclass(cls, peewee.Field)

    db_fields = [c for _, c in inspect.getmembers(golem.model, is_field)]

    undo = set()

    for db_class in db_fields + golem.model.DB_MODELS:
        property_name = db_class.__name__

        if not hasattr(peewee, property_name):
            undo.add(property_name)
            setattr(peewee, property_name, db_class)

    yield

    for property_name in undo:
        delattr(peewee, property_name)
