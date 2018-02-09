from peewee_migrate import Migrator

from golem.database.migration import default_migrate_dir, patch_peewee
from golem.database.migration.router import Router


def migrate_schema(database: 'Database',
                   from_version: int,
                   to_version: int,
                   migrate_dir: str = default_migrate_dir()):

    if from_version == to_version:
        return

    downgrade = from_version > to_version

    router = Router(database.db, migrate_dir, schema_version=to_version)
    scripts, previous_scripts = _scripts(router.environment,
                                         from_version, to_version)

    with patch_peewee():
        migrator = Migrator(router.database)

        # Teach migrator previous changes
        for script in previous_scripts:
            router.run_one(script, migrator, fake=True)

        for script in scripts:
            router.run_one(script, migrator, fake=False, downgrade=downgrade)

    database.set_user_version(to_version)


def _scripts(environment, from_version, to_version):
    downgrade = from_version > to_version
    reference_version = to_version if downgrade else from_version
    all_scripts = environment.scripts

    start_idx = -1

    for idx, script in enumerate(all_scripts):
        version = environment.version_from_name(script)
        if version > reference_version:
            start_idx = idx
            break

    scripts = all_scripts[start_idx:]
    previous_scripts = all_scripts[:start_idx]

    if downgrade:
        previous_scripts += scripts
        scripts = list(reversed(scripts))

    return scripts, previous_scripts
