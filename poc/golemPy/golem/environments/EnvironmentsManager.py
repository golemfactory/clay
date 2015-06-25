from golem.environments.EnvironmentsConfig import EnvironmentsConfig

class EnvironmentsManager:
    ############################
    def __init__(self):
        self.supportedEnvironments = set()
        self.environments = set()
        self.envConfig = None

    ############################
    def loadConfig(self, clientId):
        self.envConfig = EnvironmentsConfig.loadConfig(clientId, self.getEnvironmentsToConfig())
        configEntries = self.envConfig.getConfigEntries()
        for env in self.environments:
            getterForEnv = getattr(configEntries, "get" + env.getId())
            env.acceptTasks = getterForEnv()

    ############################
    def addEnvironment(self, environment):
        self.environments.add(environment)
        if environment.supported():
            self.supportedEnvironments.add(environment.getId())

    ############################
    def supported(self, envId):
        return envId in self.supportedEnvironments

    ############################
    def acceptTasks(self, envId):
        for env in self.environments:
            if env.getId() == envId:
                return env.isAccepted()

    ############################
    def getEnvironments(self):
        return self.environments

    ############################
    def getEnvironmentsToConfig(self):
        envs = {}
        for env in self.environments:
            envs[ env.getId() ] = (env.getId(), True)
        return envs

    ############################
    def changeAcceptTasks(self, envId, state):
        for env in self.environments:
            if env.getId() == envId:
                env.acceptTasks = state
                configEntries = self.envConfig.getConfigEntries()
                setterForEnv = getattr(configEntries, "set" + env.getId())
                setterForEnv(int (state))
                self.envConfig = self.envConfig.changeConfig()
                return