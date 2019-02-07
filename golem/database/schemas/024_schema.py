# pylint: disable=no-member
# pylint: disable=unused-argument

import peewee as pw

SCHEMA_VERSION = 24


def migrate(migrator, database, fake=False, **kwargs):
    @migrator.create_model  # pylint: disable=unused-variable
    class DockerWhitelist(pw.Model):
        repository = pw.CharField(primary_key=True)

        class Meta:
            db_table = "dockerwhitelist"


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_model("dockerwhitelist")
