# pylint: disable=no-member
# pylint: disable=too-few-public-methods
import peewee as pw

try:
    import playhouse.postgres_ext as pw_pext
except ImportError:
    pass

SCHEMA_VERSION = 22


def migrate(migrator, *_args, **_kwargs):
    migrator.add_fields(
        'localrank',
        requestor_efficiency=pw.FloatField(null=True),
        provider_efficacy=pw.ProviderEfficacyField(),
        provider_efficiency=pw.FloatField(default=1.0),
        requestor_paid_sum=pw.FloatField(default=0.0),
        requestor_assigned_sum=pw.FloatField(default=0.0)
    )


def rollback(migrator, *_args, **_kwargs):
    migrator.remove_fields(
        'localrank',
        'requestor_efficiency',
        'provider_efficacy',
        'provider_efficiency',
        'requestor_paid_sum',
        'requestor_assigned_sum'
    )
