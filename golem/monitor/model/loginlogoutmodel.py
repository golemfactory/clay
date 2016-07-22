from modelbase import BasicModel


class LoginModel(BasicModel):

    def __init__(self, metadata):
        super(LoginModel, self).__init__("Login", metadata.cliid, metadata.sessid)

        self.metadata = metadata.dict_repr()


class LogoutModel(BasicModel):

    def __init__(self, metadata):
        super(LogoutModel, self).__init__("Logout", metadata.cliid, metadata.sessid)

        self.metadata = metadata.dict_repr()
