from golem.monitorconfig import MONITOR_CONFIG
from golem.network.p2p.peersession import P2P_PROTOCOL_ID
from golem.task.tasksession import TASK_PROTOCOL_ID

from modelbase import BasicModel

class LoginLogoutBaseModel(BasicModel):
    def __init__(self, metadata):
        super(LoginLogoutBaseModel, self).__init__(self.TYPE, metadata.cliid, metadata.sessid)
        self.metadata = metadata.dict_repr()
        self.protocol_versions = {
            'monitor': MONITOR_CONFIG['PROTO_VERSION'],
            'p2p': P2P_PROTOCOL_ID,
            'task': TASK_PROTOCOL_ID,
        }

class LoginModel(LoginLogoutBaseModel):
    TYPE = "Login"


class LogoutModel(LoginLogoutBaseModel):
    TYPE = "Logout"
