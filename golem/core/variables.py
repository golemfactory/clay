
####################
#      CONST       #
####################
LONG_STANDARD_SIZE = 4

############################
#       VARIABLES          #
############################
APP_NAME = "Brass Golem"
PRIVATE_KEY = "golem_private_key.peb"
PUBLIC_KEY = "golem_public_key.pubkey"
DEFAULT_PROC_FILE = "node_processes.ctl"
MAX_PROC_FILE_SIZE = 1024 * 1024

#################
# NETWORK CONST #
#################
BUFF_SIZE = 1024 * 1024
MIN_PORT = 1
MAX_PORT = 65535
# CONNECT TO
DEFAULT_CONNECT_TO = '8.8.8.8'
DEFAULT_CONNECT_TO_PORT = 80
# NAT PUNCHING
LISTEN_WAIT_TIME = 1
LISTENING_REFRESH_TIME = 120
LISTEN_PORT_TTL = 3600
CONCENT_URL = "http://staging.concent.golem.network"
CONCENT_PUBKEY = b'b\x9b>\xf3\xb3\xefW\x92\x93\xfeIW\xd1\n\xf0j\x91\t\xdf\x95\x84\x81b6C\xe8\xe0\xdb\\.P\x00;rZM\xafQI\xf7G\x95\xe3\xe3.h\x19\xf1\x0f\xfa\x8c\xed\x12:\x88\x8aK\x00C9 \xf0~P'  # noqa pylint: disable=line-too-long

# Number of task headers transmitted per message
TASK_HEADERS_LIMIT = 20


###############
# PROTOCOL ID #
###############
# FIXME: If import by reference is required, simple dict should be preferred
#       over class container.
class PROTOCOL_CONST(object):
    """
    https://docs.python.org/3/faq/programming.html#how-do-i-share-global-variables-across-modules # noqa
    https://bytes.com/topic/python/answers/19859-accessing-updating-global-variables-among-several-modules # noqa
    """
    ID = 21

    @staticmethod
    def patch_protocol_id(ctx, param, value):
        """
        Used during golem startup for changing the protocol id
        """
        del ctx, param
        if value:
            PROTOCOL_CONST.ID = value


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
