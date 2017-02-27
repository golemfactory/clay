def __read_version():
    from ConfigParser import ConfigParser
    from golem.core.common import get_golem_path
    from os.path import join
    config = ConfigParser()
    config.read(join(get_golem_path(), '.version.ini'))
    version = config.get('version', 'version')
    splitted_version = version.split('.')
    return "{}.{}".format(splitted_version[0], splitted_version[1])

# CONST
LONG_STANDARD_SIZE = 4

############################
#       VARIABLES          #
############################
APP_NAME = "Brass Golem"
APP_VERSION = __read_version()
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
