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
    reference_version = to_version if downgrade else from_version

    router = Router(database.db, migrate_dir, schema_version=to_version)
    environment = router.environment
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

    with patch_peewee():
        migrator = Migrator(router.database)

        # Teach migrator previous changes
        for script in previous_scripts:
            router.run_one(script, migrator, fake=True, downgrade=downgrade)

        for script in scripts:
            router.run_one(script, migrator, fake=False, downgrade=downgrade)
            # Teach migrator the changes
            router.run_one(script, migrator, fake=True, downgrade=downgrade)

    database.set_user_version(to_version)



