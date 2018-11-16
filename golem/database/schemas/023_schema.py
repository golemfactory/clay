# pylint: disable=no-member
# pylint: disable=too-few-public-methods
import peewee as pw

from golem.ranking import ProviderEfficacy


SCHEMA_VERSION = 23


def migrate(migrator, *_args, **_kwargs):
    migrator.add_fields(
        'localrank',
        requestor_efficiency=pw.FloatField(null=True),
        provider_efficacy=pw.ProviderEfficacyField(
            default=ProviderEfficacy(0, 0, 0, 0)),
        provider_efficiency=pw.FloatField(default=1.0),
        requestor_paid_sum=pw.HexIntegerField(default=0),
        requestor_assigned_sum=pw.HexIntegerField(default=0)
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
