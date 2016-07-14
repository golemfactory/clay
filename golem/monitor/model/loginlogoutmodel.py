from modelbase import BasicModel


class LoginModel(BasicModel):

    def __init__(self, metadata):
        super(LoginModel, self).__init__("Login")

        self.metadata = metadata.dict_repr()


class LogoutModel(BasicModel):

    def __init__(self, metadata):
        super(LogoutModel, self).__init__("Logout")

        self.metadata = metadata.dict_repr()
