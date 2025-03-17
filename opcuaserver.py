import asyncio
import logging

from asyncua import Server, ua
from asyncua.common.methods import uamethod

@uamethod
def func(parent, value):
    return value * 2


class Opcua_server:
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        # setup our server
        self.server = Server()
        

    async def setup(self, endpoint, uri):
        await self.server.init()
        self.server.set_endpoint(endpoint)

        # set up our own namespace, not really necessary but should as spec
        self.idx = await self.server.register_namespace(uri)
        # populating our address space
        # server.nodes, contains links to very common nodes like objects and root
        myobj = await self.server.nodes.objects.add_object(self.idx, "MyObject")
        self.myvar = await myobj.add_variable(self.idx, "MyVariable", 6.7)
        # Set MyVariable to be writable by clients
        await self.myvar.set_writable()
        await self.server.nodes.objects.add_method(
            ua.NodeId("ServerMethod", self.idx),
            ua.QualifiedName("ServerMethod", self.idx),
            func,
            [ua.VariantType.Int64],
            [ua.VariantType.Int64],
        )
    
    async def serve(self):
        self._logger.info("Start serving!")
        async with self.server:
            while True:
                await asyncio.sleep(1)
                new_val = await self.myvar.get_value() + 0.1
                self._logger.info("Set value of %s to %.1f", self.myvar, new_val)
                await self.myvar.write_value(new_val)

    def start(self):
        asyncio.run(self.setup("opc.tcp://0.0.0.0:4840/freeopcua/server/", "http://automation.ceff.ch"), debug=True)
        asyncio.run(self.serve(), debug=True)


