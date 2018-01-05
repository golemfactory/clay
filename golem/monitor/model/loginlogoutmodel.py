from golem.core.variables import PROTOCOL_CONST
from golem.monitorconfig import MONITOR_CONFIG

from .modelbase import BasicModel

class LoginLogoutBaseModel(BasicModel):
    def __init__(self, metadata):
        super(LoginLogoutBaseModel, self).__init__(self.TYPE, metadata.cliid, metadata.sessid)
        self.metadata = metadata.dict_repr()
        self.protocol_versions = {
            'monitor': MONITOR_CONFIG['PROTO_VERSION'],
            'p2p': PROTOCOL_CONST.ID,
            'task': PROTOCOL_CONST.ID,
        }

class LoginModel(LoginLogoutBaseModel):
    TYPE = "Login"


class LogoutModel(LoginLogoutBaseModel):
    TYPE = "Logout"
