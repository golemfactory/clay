import logging

from golem import decorators
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

@decorators.run_with_db()
def sweep():
    """Sweeps ancient entries"""
    subq = model.CachedNode.select(
        model.CachedNode.node,
    ).order_by(
        model.CachedNode.modified_date.desc(),
    ).limit(1000)
    count = model.CachedNode.delete().where(
        model.CachedNode.node.not_in(subq),
    ).execute()
    if count:
        logger.info('Sweeped ancient nodes from cache. count=%d', count)
