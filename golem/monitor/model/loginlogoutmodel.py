from golem.monitorconfig import MONITOR_CONFIG

from golem.network.p2p.golemprotocol import GolemProtocol
from golem.network.p2p.taskprotocol import TaskProtocol
from .modelbase import BasicModel

class LoginLogoutBaseModel(BasicModel):
    def __init__(self, metadata):
        super(LoginLogoutBaseModel, self).__init__(self.TYPE, metadata.cliid, metadata.sessid)
        self.metadata = metadata.dict_repr()
        self.protocol_versions = {
            'monitor': MONITOR_CONFIG['PROTO_VERSION'],
            'p2p': GolemProtocol.version,
            'task': TaskProtocol.version,
        }

class LoginModel(LoginLogoutBaseModel):
    TYPE = "Login"


class LogoutModel(LoginLogoutBaseModel):
    TYPE = "Logout"
