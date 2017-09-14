from devp2p import slogging
from devp2p.protocol import BaseProtocol
from rlp import sedes

from golem.core.common import to_unicode
from golem.core.simpleserializer import CBORSedes, unicode_sedes

logger = slogging.get_logger('golem.protocol')


class TaskProtocol(BaseProtocol):

    protocol_id = 18318  # == GolemProtocol.protocol_id + 1
    version = 1
    name = b'task_proto'

    def __init__(self, peer, service):
        # required by P2PProtocol
        self.config = peer.config
        self.eth_account_info = None
        BaseProtocol.__init__(self, peer, service)

    class reject(BaseProtocol.command):
        """
        Generic reject message,
        sent by both requestors and providers
        """
        cmd_id = 0

        structure = [
            ('cmd_id', sedes.big_endian_int),
            ('reason', CBORSedes),
            ('payload', CBORSedes)
        ]

    class task_request(BaseProtocol.command):
        """
        ComputeTaskDef request,
        sent by providers
        """
        cmd_id = 1

        structure = [
            ('task_id', unicode_sedes),
            ('performance', CBORSedes),
            ('price', sedes.big_endian_int),
            ('max_disk', sedes.big_endian_int),
            ('max_memory', sedes.big_endian_int),
            ('max_cpus', sedes.big_endian_int)
        ]

    class task(BaseProtocol.command):
        """
        ComputeTaskDef and resources,
        sent by requestors
        """
        cmd_id = 2

        structure = [
            ('definition', CBORSedes),
            ('resources', CBORSedes),
            ('resource_options', CBORSedes)
        ]

        @classmethod
        def decode_payload(cls, rlp_data):
            decoded = super().decode_payload(rlp_data)
            try:
                ctd = decoded['definition']
                ctd.task_id = to_unicode(ctd.task_id)
                ctd.subtask_id = to_unicode(ctd.subtask_id)
                ctd.key_id = to_unicode(ctd.key_id)
                ctd.task_owner.key = to_unicode(ctd.task_owner.key)
            except Exception as exc:
                logger.error("Error decoding task definition %s", exc)
            return decoded

    class failure(BaseProtocol.command):
        """
        Computation failure,
        sent by providers
        """
        cmd_id = 3
        structure = [
            ('subtask_id', unicode_sedes),
            ('reason', sedes.binary)
        ]

    class result(BaseProtocol.command):
        """
        Task computation result,
        sent by providers
        """
        cmd_id = 4

        structure = [
            ('subtask_id', unicode_sedes),
            ('computation_time', CBORSedes),
            ('resource_hash', unicode_sedes),
            ('resource_secret', sedes.binary),
            ('resource_options', CBORSedes),
            ('eth_account', CBORSedes)
        ]

        @classmethod
        def decode_payload(cls, rlp_data):
            decoded = super().decode_payload(rlp_data)
            decoded['eth_account'] = to_unicode(decoded['eth_account'])
            return decoded

    class accept_result(BaseProtocol.command):
        """
        Accept task computation result,
        sent by requestors
        """
        cmd_id = 5

        structure = [
            ('subtask_id', unicode_sedes),
            ('remuneration', CBORSedes)
        ]

    class payment_request(BaseProtocol.command):
        """
        Payment information request,
        sent by providers
        """
        cmd_id = 6

        structure = [
            ('subtask_id', unicode_sedes),
        ]

    class payment(BaseProtocol.command):
        """
        Payment information,
        sent by requestors
        """
        cmd_id = 7

        structure = [
            ('subtask_id', unicode_sedes),
            ('transaction_id', unicode_sedes),
            ('remuneration', sedes.big_endian_int),
            ('block_number', sedes.binary)
        ]
