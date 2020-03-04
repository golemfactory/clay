import pathlib
from typing import ClassVar

import dateutil.relativedelta
from golem_messages.constants import MAX_CONCENT_PING_INTERVAL

from golem.core import common

####################
#      CONST       #
####################
LONG_STANDARD_SIZE = 4

############################
#       VARIABLES          #
############################
APP_NAME = "Brass Golem"
PRIVATE_KEY = "keystore.json"
DEFAULT_PROC_FILE = "node_processes.ctl"
MAX_PROC_FILE_SIZE = 1024 * 1024
ENV_TASK_API_DEV = 'GOLEM_TASK_API_DEV'

#################
# NETWORK CONST #
#################
MIN_PORT = 1
MAX_PORT = 65535
# CONNECT TO
MAX_CONNECT_SOCKET_ADDRESSES = 8
DEFAULT_CONNECT_TO = '8.8.8.8'
DEFAULT_CONNECT_TO_PORT = 80

BROADCAST_PUBKEY = b'\xab\xab;\xb0\x89\x10\r\xf8Hs\xd7\x91\xcc\x13\xdb\x0b9tw\x80\xd4t?\xdc\x9dS.\x9at\xe3X\xbcBK\x1c\xef\xdb3\xab}z\xad\xde"ZW\xa9T\xdeN\xb6\xc7P\x0e\xa9\x7fv\x1a\xec\xcbN\x07R\x10'  # noqa pylint: disable=line-too-long

CONCENT_CERTIFICATES_DIR = pathlib.Path(common.get_golem_path()) \
    / 'golem/network/concent/resources/ssl/certs'
CONCENT_CHOICES: dict = {
    'disabled': {'url': None, 'pubkey': None},
    'dev': {
        'url': 'http://devel.concent.golem.network',
        'pubkey': b'\xf3\x97\x19\xcdX\xda\x86tiP\x1c&\xd39M\x9e\xa4\xddb\x89\xb5,]O\xd5cR\x84\xb85\xed\xc9\xa17e,\xb2s\xeb\n1\xcaN.l\xba\xc3\xb7\xc2\xba\xff\xabN\xde\xb3\x0b\xa6l\xbf6o\x81\xe0;',  # noqa pylint: disable=line-too-long
        'deposit_contract_address':
            '0x10ef3a07ea272E024cC0a66eCAe1Ba81eb3f5794',
    },
    'staging': {
        'url': 'https://staging.concent.golem.network',
        'pubkey': b'b\x9b>\xf3\xb3\xefW\x92\x93\xfeIW\xd1\n\xf0j\x91\t\xdf\x95\x84\x81b6C\xe8\xe0\xdb\\.P\x00;rZM\xafQI\xf7G\x95\xe3\xe3.h\x19\xf1\x0f\xfa\x8c\xed\x12:\x88\x8aK\x00C9 \xf0~P',  # noqa pylint: disable=line-too-long
        'certificate': str(CONCENT_CERTIFICATES_DIR / 'staging.crt'),
        'deposit_contract_address':
            '0x884443710CDe8Bb56D10E81059513fb1c4Bf32A3',
    },
    'test': {
        'url': 'https://test.concent.golem.network',
        'pubkey': b"\xf0\x08\xd9\x80V\t\xf3'B\x83\x8dT\xec\xa7s\x1d\xfdC\x92\xa8}GM\x94\x03F\xeaF\xd8\x05\xeaj\xd9p4|y\xef\x0b\xe0\x94\xb3@\xd2{\xf6\x90G \x7f4\x1d\x0f6\xcd\xba\xf8^\x02,;\x91\xdb\xcd",  # noqa pylint: disable=line-too-long
        'certificate': str(CONCENT_CERTIFICATES_DIR / 'test.crt'),
        'deposit_contract_address':
            '0x74751ae0b80276dB6b9310b7F8F79fe044205b83',
    },
    'main': {
        'url': 'https://main.concent.golem.network',
        'pubkey': b'F[\x03\xa8\xab[\x98\xd4\xd4$\xf8\xe1\x0fG\x92\xa1\xb2\xef*\xc5`}\xb52\xaaU\x1f\xd4\x8b\t\xb5=r\\\x8c\x07A`\x8c\x1a\x83\x01>@\x9b\x87\x17\x8d/\xfc\x0b\xa5\xe1\x80.\x9dm\xbcQ\x93hR\x1f6',  # noqa pylint: disable=line-too-long
        'deposit_contract_address':
            '0x98d3ca6528A2532Ffd9BDef50F92189568932570',
    },
}

CONCENT_PULL_INTERVAL = (MAX_CONCENT_PING_INTERVAL / 2).total_seconds()

# Number of task headers transmitted per message
TASK_HEADERS_LIMIT = 20

# Maximum acceptable difference between node time and monitor time (seconds)
MAX_TIME_DIFF = 10

MESSAGE_QUEUE_MAX_AGE = dateutil.relativedelta.relativedelta(months=6)

# How long should peer be banned when failing on resources (seconds)
ACL_BLOCK_TIMEOUT_RESOURCE = 2 * 3600  # s


###############
# PROTOCOL ID #
###############
# FIXME: If import by reference is required, simple dict should be preferred
#       over class container. #2468
class PROTOCOL_CONST(object):
    """
    https://docs.python.org/3/faq/programming.html#how-do-i-share-global-variables-across-modules # noqa
    https://bytes.com/topic/python/answers/19859-accessing-updating-global-variables-among-several-modules # noqa
    """
    NUM: ClassVar[int] = 32
    POSTFIX: ClassVar[str] = ''
    ID: ClassVar[str] = str(NUM) + POSTFIX

    @staticmethod
    def patch_protocol_id(ctx=None, param=None, value=None):
        """
        Used during golem startup for changing the protocol id
        """

        del ctx, param
        if value:
            PROTOCOL_CONST.NUM = int(value)
            PROTOCOL_CONST.ID = str(PROTOCOL_CONST.NUM) + PROTOCOL_CONST.POSTFIX


#################
# SESSION CONST #
#################
UNVERIFIED_CNT = 15

#################
# RANKING CONST #
#################
BREAK_TIME = 2400
END_ROUND_TIME = 1200
ROUND_TIME = 600
STAGE_TIME = 36000

###################
# THREADING CONST #
###################
REACTOR_THREAD_POOL_SIZE = 20

#################
# INCOMES CONST #
#################
PAYMENT_DEADLINE = 24 * 60 * 60

#################
# CONCENT CONST #
#################
NUM_OF_RES_TRANSFERS_NEEDED_FOR_VER = 3

#################
# TASK DEFINITION PICKLED VERSION #
#################

PICKLED_VERSION = 3
