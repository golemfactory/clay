from typing import ClassVar

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

#################
# NETWORK CONST #
#################
BUFF_SIZE = 1024 * 1024
MIN_PORT = 1
MAX_PORT = 65535
# CONNECT TO
MAX_CONNECT_SOCKET_ADDRESSES = 8
DEFAULT_CONNECT_TO = '8.8.8.8'
DEFAULT_CONNECT_TO_PORT = 80

# testing
CONCENT_URL = "http://staging.concent.golem.network"
CONCENT_PUBKEY = b'b\x9b>\xf3\xb3\xefW\x92\x93\xfeIW\xd1\n\xf0j\x91\t\xdf\x95\x84\x81b6C\xe8\xe0\xdb\\.P\x00;rZM\xafQI\xf7G\x95\xe3\xe3.h\x19\xf1\x0f\xfa\x8c\xed\x12:\x88\x8aK\x00C9 \xf0~P'  # noqa pylint: disable=line-too-long

# devel
# CONCENT_URL = "http://devel.concent.golem.network"
# CONCENT_PUBKEY = b'\xf3\x97\x19\xcdX\xda\x86tiP\x1c&\xd39M\x9e\xa4\xddb\x89\xb5,]O\xd5cR\x84\xb85\xed\xc9\xa17e,\xb2s\xeb\n1\xcaN.l\xba\xc3\xb7\xc2\xba\xff\xabN\xde\xb3\x0b\xa6l\xbf6o\x81\xe0;'  # noqa pylint: disable=line-too-long

# Number of task headers transmitted per message
TASK_HEADERS_LIMIT = 20
KEY_DIFFICULTY = 14

# Maximum acceptable difference between node time and monitor time (seconds)
MAX_TIME_DIFF = 10


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
    NUM: ClassVar[int] = 26
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
