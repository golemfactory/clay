# CONST
LONG_STANDARD_SIZE = 4

############################
#       VARIABLES          #
############################
APP_NAME = "Brass Golem"
APP_VERSION = "0.8.0"
PRIVATE_KEY = "golem_private_key.peb"
PUBLIC_KEY = "golem_public_key.pubkey"
DEFAULT_PROC_FILE = "node_processes.ctl"
MAX_PROC_FILE_SIZE = 1024 * 1024

#####################
# NETWORK VARIABLES #
#####################
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
P2P_PROTOCOL_ID = 14
TASK_PROTOCOL_ID = 15

# class Protocol_Id(object):
#     P2P_PROTOCOL_ID = 123
#
#     def set_p2p_protocol_id(self, new_id):
#         Protocol_Id.P2P_PROTOCOL_ID = new_id



def monkey_patch_protocol(ctx, param, value):
    """
    Used at golem startup
    """
    del ctx, param
    if value:
        # from golem.core.variables import P2P_PROTOCOL_ID, TASK_PROTOCOL_ID
        global P2P_PROTOCOL_ID, TASK_PROTOCOL_ID
        P2P_PROTOCOL_ID = value
        TASK_PROTOCOL_ID = value


#####################
# SESSION VARIABLES #
#####################
MSG_TTL = 600
FUTURE_TIME_TOLERANCE = 300
UNVERIFIED_CNT = 15

#####################
# RANKING VARIABLES #
#####################
BREAK_TIME = 2400
END_ROUND_TIME = 1200
ROUND_TIME = 600
STAGE_TIME = 36000
