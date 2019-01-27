import enum

from golem.model import GenericKeyValue
from golem.rpc import utils as rpc_utils


class SoftSwitch(enum.Enum):
    ON: str = 'on'
    OFF: str = 'off'


KEY = "concent_soft_switch"
DEFAULT = SoftSwitch.OFF


@rpc_utils.expose('golem.concent.switch')
def is_on() -> bool:
    query = GenericKeyValue.select().where(
        GenericKeyValue.key == KEY,
    ).limit(1)
    try:
        value = SoftSwitch(query[0].value)
    except IndexError:
        value = DEFAULT
    return value == SoftSwitch.ON


@rpc_utils.expose('golem.concent.switch.turn')
def turn(on: bool) -> None:
    entry, _ = GenericKeyValue.get_or_create(key=KEY)
    entry.value = SoftSwitch.ON.value if on else SoftSwitch.OFF.value
    entry.save()
