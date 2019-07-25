from golemapp import main
from golem.client import Client
from golem.rpc import utils as rpc_utils


@rpc_utils.expose('test.bignum')
def _get_bignum(self):
    return 2**64 + 1337


# using setattr silences mypy complaining about "has no attribute"
setattr(Client, "_get_bignum", _get_bignum)


main()
