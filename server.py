
from moonraker_api import MoonrakerListener, MoonrakerClient
from moonraker_api.const import (
    WEBSOCKET_STATE_CONNECTING,
    WEBSOCKET_STATE_CONNECTED,
    WEBSOCKET_STATE_STOPPING,
    WEBSOCKET_STATE_STOPPED
)
from moonraker_api.websockets.websocketclient import (
    ClientNotAuthenticatedError,
)
import logging
import asyncio
from asyncua import Server, ua
from asyncua.common.methods import uamethod
import json

HOST = "localhost"
PORT = 7125

logging.basicConfig(
    level=logging.WARNING, format="%(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("moonraker_api").setLevel(logging.DEBUG)
logging.getLogger(__name__).setLevel(logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

@uamethod
def func(parent, value):
    return value * 2

async def increment_coro(value):
    while True:
        await asyncio.sleep(1)
        value+=0.1

class OpcuaConnector(MoonrakerListener):
    def __init__(self, endpoint, uri):
        self.running = False
        self.client = MoonrakerClient(
            self,
            HOST,
            PORT,
        )
        self._logger = _LOGGER
        # setup our opc server
        self.server = Server()
        self.endpoint=endpoint
        self.uri=uri

        # append the opcua server to the event loop


    async def setup_address_space(self):
        await self.server.init()
        self.server.set_endpoint(self.endpoint)

        # set up our own namespace, not really necessary but should as spec
        self.idx = await self.server.register_namespace(self.uri)
        # populating our address space
        # server.nodes, contains links to very common nodes like objects and root
        printerObj = await self.server.nodes.objects.add_object(self.idx, "Printer")
        printerInfoObj = await printerObj.add_object(self.idx, "Info")
        self.printer_name = await printerInfoObj.add_property(self.idx, "name", ua.Variant("-", ua.VariantType.String))
        self.printer_state = await printerInfoObj.add_property(self.idx, "status", ua.Variant("Unknown", ua.VariantType.String))
        self.myvar = await printerObj.add_variable(self.idx, "MyVariable", 6.7)
        # Set MyVariable to be writable by clients
        await self.myvar.set_writable()
        # add a method
        await printerObj.add_method(
            ua.NodeId("ServerMethod", self.idx),
            ua.QualifiedName("ServerMethod", self.idx),
            func,
            [ua.VariantType.Int64],
            [ua.VariantType.Int64],
        )

    async def start(self) -> None:
        """Start the websocket connection."""
        self.running = True
        return await self.client.connect()

    async def stop(self) -> None:
        """Stop the websocket connection."""
        self.running = False
        await self.client.disconnect()
    

    async def state_changed(self, state: str) -> None:
        """Notifies of changing websocket state."""
        self._logger.debug("Stated changed to %s", state)
        if state == WEBSOCKET_STATE_CONNECTING:
            pass
        elif state == WEBSOCKET_STATE_CONNECTED:
            pass
        elif state == WEBSOCKET_STATE_STOPPING:
            pass
        elif state == WEBSOCKET_STATE_STOPPED:
            pass

    async def on_exception(self, exception: BaseException) -> None:
        """Notifies of exceptions from the websocket run loop."""
        self._logger.debug("Received exception from API websocket %s", str(exception))
        if isinstance(exception, ClientNotAuthenticatedError):
            self.entry.async_start_reauth(self.hass)
        else:
            raise exception

    async def on_notification(self, method: str, data: any) -> None:
        """Notifies of state updates."""
        self._logger.debug("Received notification %s -> %s", method, data)

        # Subscription notifications
        if method == "notify_status_update":
            message = data[0]
            timestamp = data[1]
            self._logger.debug("Received status update notnificatio %s -> %s", timestamp, message)

async def main():
    listener = OpcuaConnector("opc.tcp://0.0.0.0:4840/freeopcua/server/", "http://automation.ceff.ch")
    client = listener.client
    await client.connect()

    # Setup the adress space
    await listener.setup_address_space()

    response = await client.call_method("printer.info")
    
    # Set the printer_info printer_name and printer_status
    my_node = listener.server.get_node("ns=2;i=3")
    await my_node.set_value(response["hostname"])
    my_node = listener.server.get_node("ns=2;i=4")
    await my_node.set_value(response["state"])


    response = await client.call_method("printer.objects.list")
    print(response)
    params = {"objects": 
              {"gcode_move": None,
               "toolhead": ["position", "status"]
               }
              }

    response = await client.call_method("printer.objects.query", **params)

    response = await client.call_method("printer.objects.subscribe", **params)
    
    async with listener.server:
        while True:
            await asyncio.sleep(1)
            my_node = listener.server.get_node("ns=2;i=5")
            new_val = await my_node.get_value() + 0.1
            listener._logger.info("Set value of %s to %.1f", my_node, new_val)
            await my_node.write_value(new_val)



if __name__ == "__main__":

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())