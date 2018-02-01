from golem.database.migration import default_migrate_dir
from golem.database.migration.router import Router


def migrate_schema(db: 'peewee.Database',
                   from_version: int,
                   to_version: int,
                   migrate_dir: str = default_migrate_dir()):

    if from_version == to_version:
        return

    router = Router(db, migrate_dir, schema_version=to_version)
    migrator = router.migrator
    environment = Router.Environment()

    downgrade = from_version > to_version
    reference_version = to_version if downgrade else from_version

    scripts = filter(
        lambda f: Router.Environment.version_from_name(f) > reference_version,
        environment.scripts
    )

    if downgrade:
        scripts = reversed(list(scripts))

    with db.transaction():
        for script in scripts:
            router.run_one(script, migrator, fake=False, downgrade=downgrade)
