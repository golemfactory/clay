import enum

from golem.model import GenericKeyValue
from golem.rpc import utils as rpc_utils
from golem.terms import ConcentTermsOfUse

class SoftSwitch(enum.Enum):
    ON: str = 'on'
    OFF: str = 'off'

KEY = "concent_soft_switch"
DEFAULT = SoftSwitch.ON

@rpc_utils.expose('golem.concent.switch')
def is_on() -> bool:
    if not ConcentTermsOfUse.are_accepted():
        return False
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
    if not ConcentTermsOfUse.are_accepted():
        return
    entry, _ = GenericKeyValue.get_or_create(key=KEY)
    entry.value = SoftSwitch.ON.value if on else SoftSwitch.OFF.value
    entry.save()
