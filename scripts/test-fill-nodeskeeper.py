#!/usr/bin/env python
import faker
from golem_messages import cryptography
from golem_messages.factories.datastructures.p2p import Node as NodeFactory
from golem_messages import utils

from golem.network import nodeskeeper


fake = faker.Faker()
# Keep reference to avoid garbage collection of db
_db = None

def init_db(datadir):
    from golem.database import database
    from golem.model import DB_MODELS, db, DB_FIELDS
    global _db  # pylint: disable=global-statement
    _db = database.Database(
        db,
        fields=DB_FIELDS,
        models=DB_MODELS,
        db_dir=datadir,
    )

def store_one():
    nodeskeeper.store(
        NodeFactory(
            key=utils.encode_hex(cryptography.ECCx(None).raw_pubkey),
            node_name=f'[F] {fake.name()}',
        ),
    )

def main(datadir):
    import sys
    from golem import model
    sys.stderr.write('\ninit_db\n')
    init_db(datadir)
    sys.stderr.write(f'{model.CachedNode.select().count()} nodes\n')
    sys.stderr.write('fill')
    for i in range(fake.random_int(min=100, max=1000)):
        if not i % 100:
            sys.stderr.write('.')
            sys.stderr.flush()
        store_one()
    sys.stderr.write('\n')
    sys.stderr.write(f'{model.CachedNode.select().count()} nodes\n')
    sys.stderr.write('sweep\n')
    nodeskeeper.sweep()
    sys.stderr.write(f'{model.CachedNode.select().count()} nodes\n')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description="Fill nodeskeeper with dummy nodes",
    )
    parser.add_argument('-d', dest='datadir', required=True,)
    args = parser.parse_args()
    main(args.datadir)
