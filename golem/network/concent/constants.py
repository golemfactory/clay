import collections
import datetime

from golem_messages import message

# Maximum Message Transport Time, maximum transport time
# allowed for transmission of a small message (if ping time is
# greater than this, it means the communication is lagged).
mmtt = datetime.timedelta(minutes=0, seconds=5)

# Maximum Time Difference, maximum time difference from actual
# time. (Time synchronisation)
mtd = datetime.timedelta(minutes=0, seconds=10)

# Maximum Action Time, maximum time needed to perform simple
# machine operation.
mat = datetime.timedelta(minutes=2, seconds=15)


DEFAULT_MSG_LIFETIME = (3 * mmtt + 3 * mat)

# Time to wait before sending a message
MSG_DELAYS = collections.defaultdict(
    lambda: datetime.timedelta(0),
    {
        message.ForceReportComputedTask: (2 * mmtt + mat)
    },
)

# A valid period of time for sending a message
MSG_LIFETIMES = {
}

# After what time, send empty ping to concent
PING_TIMEOUT = 60  # seconds
