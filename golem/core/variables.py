
####################
#      CONST       #
####################
LONG_STANDARD_SIZE = 4

APP_NAME = "Brass Golem"
APP_VERSION = "0.8.0"
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


###############
# PROTOCOL ID #
###############
class PROTOCOL_ID(object):
    """
    https://docs.python.org/2/faq/programming.html#how-do-i-share-global-variables-across-modules
    https://bytes.com/topic/python/answers/19859-accessing-updating-global-variables-among-several-modules
    """
    P2P_ID = 15
    TASK_ID = 15

    @staticmethod
    def patch_protocol_id(ctx, param, value):
        """
        Used during golem startup for changing the protocol id
        """
        del ctx, param
        if value:
            PROTOCOL_ID.P2P_ID = value
            PROTOCOL_ID.TASK_ID = value


#################
# SESSION CONST #
#################
MSG_TTL = 600
FUTURE_TIME_TOLERANCE = 300
UNVERIFIED_CNT = 15

#################
# RANKING CONST #
#################
BREAK_TIME = 2400
END_ROUND_TIME = 1200
ROUND_TIME = 600
STAGE_TIME = 36000
