# CONST
LONG_STANDARD_SIZE = 4

############################
#       VARIABLES          #
############################
KEYS_PATH = "examples/gnr/node_data/"
PRIVATE_KEY_PREF = "golem_private_key"
PUBLIC_KEY_PREF = "golem_public_key"
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

##################
# P2P VARIABLES #
#################
REFRESH_PEERS_TIMEOUT = 1200
LAST_MESSAGE_BUFFER_LEN = 5
# KADEMLIA BUCKET SIZE
K = 16
CONCURRENCY = 3

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
ROUND_TIME = 1800
STAGE_TIME = 36000

######################
# TRANSACTION SYSTEM #
######################
CONTRACT_ID = "0x07f9c1760809ffd43117da56b2c388f54da69b92"
PAY_HASH = "0x0e785fd3"
INIT_LOTTERY_HASH = "0xec891da1"
ETH_CONN_ADDR = "http://localhost:8080"
