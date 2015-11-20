from golem.environments.EnvironmentsConfig import EnvironmentsConfig


class EnvironmentsManager:
    ############################
    def __init__(self):
        self.supportedEnvironments = set()
        self.environments = set()
        self.env_config = None

    ############################
    def load_config(self, client_id):
        self.env_config = EnvironmentsConfig.load_config(client_id, self.get_environments_to_config())
        config_entries = self.env_config.get_config_entries()
        for env in self.environments:
            getter_for_env = getattr(config_entries, "get" + env.get_id())
            env.accept_tasks = getter_for_env()

    ############################
    def add_environment(self, environment):
        self.environments.add(environment)
        if environment.supported():
            self.supportedEnvironments.add(environment.get_id())

    ############################
    def supported(self, env_id):
        return env_id in self.supportedEnvironments

    ############################
    def accept_tasks(self, env_id):
        for env in self.environments:
            if env.get_id() == env_id:
                return env.is_accepted()

    ############################
    def get_environments(self):
        return self.environments

    ############################
    def get_environments_to_config(self):
        envs = {}
        for env in self.environments:
            envs[env.get_id()] = (env.get_id(), True)
        return envs

    ############################
    def change_accept_tasks(self, env_id, state):
        for env in self.environments:
            if env.get_id() == env_id:
                env.accept_tasks = state
                config_entries = self.env_config.get_config_entries()
                setter_for_env = getattr(config_entries, "set" + env.get_id())
                setter_for_env(int(state))
                self.env_config = self.env_config.change_config()
                return
