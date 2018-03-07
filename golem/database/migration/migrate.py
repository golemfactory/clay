from peewee import DatabaseError
from peewee_migrate import Migrator

from golem.database.migration import default_migrate_dir, patch_peewee
from golem.database.migration.router import Router


class MigrationError(DatabaseError):
    pass


class NoMigrationScripts(MigrationError):
    pass


def migrate_schema(database: 'Database',
                   from_version: int,
                   to_version: int,
                   migrate_dir: str = default_migrate_dir()):

    if from_version == to_version:
        return

    router = Router(database.db, migrate_dir, schema_version=to_version)
    environment = router.environment

    scripts = environment.scripts
    to_run, to_fake, downgrade = choose_scripts(scripts, from_version,
                                                to_version)
    if not to_run:
        raise NoMigrationScripts("Cannot migrate schema from version {} to {}: "
                                 "no suitable migration scripts found"
                                 .format(from_version, to_version))

    with patch_peewee(database.fields, database.models):
        migrator = Migrator(router.database)

        # Teach migrator previous changes
        for script in to_fake:
            router.run_one(script, migrator, fake=True)

        for script in to_run:
            router.run_one(script, migrator, fake=False, downgrade=downgrade)

            version = environment.version_from_name(script)
            version -= 1 if downgrade else 0
            database.set_user_version(version)


def choose_scripts(scripts, from_version, to_version):
    start_idx = end_idx = -1

    downgrade = from_version > to_version
    if downgrade:
        from_version, to_version = to_version, from_version

    for idx, script in enumerate(scripts):
        version = Router.Environment.version_from_name(script)

        if version == from_version + 1 and start_idx < 0:
            start_idx = idx
        if version > to_version:
            end_idx = idx
            break

    if start_idx < 0:
        return [], [], False

    if end_idx < 0:
        end_idx = len(scripts)

    to_fake = scripts[:start_idx]
    to_run = scripts[start_idx:end_idx]

    if downgrade:
        to_fake += to_run
        to_run = to_run[::-1]

    return to_run, to_fake, downgrade
