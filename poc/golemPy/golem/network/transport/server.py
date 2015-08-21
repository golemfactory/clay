class Server(object):
    def __init__(self, config_desc, network):
        self.config_desc = config_desc
        self.network = network

    def new_connection(self, session):
        pass

    def change_config(self, config_desc):
        self.config_desc = config_desc

    def start_accepting(self):
        pass


class BasicServer(Server):
    def __init__(self, config_desc, network):
        Server.__init__(self, config_desc, network)
        self.cur_port = 0

    def change_config(self, config_desc):
        Server.change_config(config_desc)
        if self.curPort != 0:
            self.network.stop_listening()