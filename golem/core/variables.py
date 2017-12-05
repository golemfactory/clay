
####################
#      CONST       #
####################
LONG_STANDARD_SIZE = 4

############################
#       VARIABLES          #
############################
APP_NAME = "Brass Golem"
APP_VERSION = "0.9.0"
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
CONCENT_URL = "https://concent.golem.network"

# Number of task headers transmitted per message
TASK_HEADERS_LIMIT = 20


###############
# PROTOCOL ID #
###############
# FIXME: If import by reference is required, simple dict should be preferred
#       over class container.
# FIXME: Unify P2P_ID and TASK_ID #1692
class PROTOCOL_CONST(object):
    """
    https://docs.python.org/3/faq/programming.html#how-do-i-share-global-variables-across-modules #noqa
    https://bytes.com/topic/python/answers/19859-accessing-updating-global-variables-among-several-modules #noqa
    """
    P2P_ID = 18
    TASK_ID = 18

    @staticmethod
    def patch_protocol_id(ctx, param, value):
        """
        Used during golem startup for changing the protocol id
        """
        del ctx, param
        if value:
            PROTOCOL_CONST.P2P_ID = value
            PROTOCOL_CONST.TASK_ID = value


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
