from client import Client


class PeerSession:
    def __init__(self, client, address, port):
        assert isinstance(client, Client)
        self.client = client
        self.address = address
        self.port = port

    def __str__(self):
        return "{} : {}".format(self.address, self.port)
     
    def start(self):
        pass
    
    def disconnect(self):
        pass
    
    def ping(self):
        pass
    
    # private
       
    def send(message):
        self.client.sendMessage(message)