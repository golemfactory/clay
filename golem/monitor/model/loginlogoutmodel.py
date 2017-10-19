from golem.monitorconfig import MONITOR_CONFIG
from golem.core.variables import PROTOCOL_ID




from .modelbase import BasicModel

class LoginLogoutBaseModel(BasicModel):
    def __init__(self, metadata):
        super(LoginLogoutBaseModel, self).__init__(self.TYPE, metadata.cliid, metadata.sessid)
        self.metadata = metadata.dict_repr()
        self.protocol_versions = {
            'monitor': MONITOR_CONFIG['PROTO_VERSION'],
            'p2p': PROTOCOL_ID.P2P_ID,
            'task': PROTOCOL_ID.TASK_ID,
        }

class LoginModel(LoginLogoutBaseModel):
    TYPE = "Login"


class LogoutModel(LoginLogoutBaseModel):
    TYPE = "Logout"
