import datetime
import logging

from dateutil.relativedelta import relativedelta

from golem import model

logger = logging.getLogger(__name__)

def get(node_id):
    try:
        return model.CachedNode.select().where(
            model.CachedNode.node == node_id,
        ).get().node_field
    except model.CachedNode.DoesNotExist:
        return None

def store(node):
    """Creates or refreshes node entry"""
    instance, created = model.CachedNode.get_or_create(
        node=node.key,
        defaults={'node_field': node, },
    )
    if not created:
        instance.node_field = node
        instance.save()

def sweep():
    """Sweeps ancient entries"""
    oldest_allowed = datetime.datetime.now() - relativedelta(months=1)
    count = model.CachedNode.delete().where(
        model.CachedNode.modified_date < oldest_allowed,
    ).execute()
    if count:
        logger.info('Sweeped ancient nodes from cache. count=%d', count)
