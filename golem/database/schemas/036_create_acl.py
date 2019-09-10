# pylint: disable=no-member
# pylint: disable=unused-argument
import datetime as dt
import peewee as pw
from pathlib import Path
from typing import Set

SCHEMA_VERSION = 36


def migrate_txt(database):

    def _read_set_from_file(path: Path) -> Set[str]:
        try:
            with path.open() as f:
                return set(line.strip() for line in f)
        except OSError:
            return set()

    def _remove_file(path: Path) -> None:
        if(path.exists()):
            path.unlink()

    DENY_LIST_NAME = "deny.txt"
    ALL_EXCEPT_ALLOWED = "ALL_EXCEPT_ALLOWED"
    nodes_ids = []
    datadir = Path(database.database).parent
    deny_list_path = datadir / DENY_LIST_NAME
    nodes_ids = _read_set_from_file(deny_list_path)
    if(len(nodes_ids) > 0):
        if ALL_EXCEPT_ALLOWED in nodes_ids:
            nodes_ids.remove(ALL_EXCEPT_ALLOWED)
            nodes = [{'node_id': node_id, 'node_name': None}
                     for node_id in nodes_ids]
            ACLAllowedNodes.insert_many(nodes).execute()
        nodes = [{'node_id': node_id, 'node_name': None}
                 for node_id in nodes_ids]
        ACLDeniedNodes.insert_many(nodes).execute()
    self._remove_file()


def migrate(migrator, database, fake=False, **kwargs):
    @migrator.create_model
    class ACLAllowedNodes(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        node_id = pw.CharField(max_length=255, unique=True)
        node_name = pw.CharField(max_length=255)

        class Meta:
            db_table = "aclallowednodes"

    @migrator.create_model
    class ACLDeniedNodes(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        node_id = pw.CharField(max_length=255, unique=True)
        node_name = pw.CharField(max_length=255)

        class Meta:
            db_table = "acldeniednodes"

    migrator.python(migrate_txt, database)


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_model('acldeniednodes')
    migrator.remove_model('aclallowednodes')
