
import logging

from opcuaserver import Opcua_server as server
from moonrakerclient import APIConnector as client

class Server:
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        # setup our server
        self.server = server()
        self.client = client()

    def start(self):
        self.server.start()
        self.client.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    srv = Server()
    srv.start()
