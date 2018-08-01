import datetime
import typing
import time
import sys


def retry_until_timeout(
        condition: typing.Callable,
        timeout: datetime.timedelta,
        sleep_interval: typing.Optional[int]=1,
        timeout_message: str = '',
        sleep_action: typing.Optional[typing.Callable]=
        lambda: sys.stderr.write('.\n'),
):
    start = datetime.datetime.now()
    while condition():
        if sleep_action:
            sleep_action()
        if sleep_interval:
            time.sleep(sleep_interval)
        if start + timeout < datetime.datetime.now():
            raise TimeoutError(timeout_message)
    return start, datetime.datetime.now()
