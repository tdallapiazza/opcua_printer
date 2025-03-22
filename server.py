
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
import spool_manager
import printing_plate_manager

HOST = "localhost"
PORT = 7125
PRINTER_INFO_FILE="printer_info.json"


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

        # add agregate managers
        self.spool_manager = spool_manager.SpoolManager()
        self.print_plate_manager = printing_plate_manager.Printing_plate_manager()

        # load additionnal printer data
        with open(PRINTER_INFO_FILE, 'r') as file:
            self.additional_printer_data = json.load(file)
        
        # set update period [s]
        self.update_period = 1


    async def setup_address_space(self):
        await self.server.init()
        self.server.set_endpoint(self.endpoint)

        # set up our own namespace, not really necessary but should as spec
        self.idx = await self.server.register_namespace(self.uri)
        # populating our address space
        # server.nodes, contains links to very common nodes like objects and root

        # printer object
        self.printerObj = await self.server.nodes.objects.add_object(self.idx, "Printer")
        #   info object
        printerInfoObj = await self.printerObj.add_object(self.idx, "Info")
        await printerInfoObj.add_property(self.idx, "Name", ua.Variant("", ua.VariantType.String)) # 3 
        await printerInfoObj.add_property(self.idx, "Manufacturer", ua.Variant(self.additional_printer_data["printer"]["Manufacturer"], ua.VariantType.String)) # 3
        await printerInfoObj.add_property(self.idx, "Model", ua.Variant(self.additional_printer_data["printer"]["Model"], ua.VariantType.String)) # 3
        await printerInfoObj.add_property(self.idx, "Idle power", self.additional_printer_data["printer"]["Idle power"]) # 3
        await printerInfoObj.add_property(self.idx, "Location", ua.Variant(self.additional_printer_data["printer"]["Location"], ua.VariantType.String))
        await printerInfoObj.add_variable(self.idx, "State", ua.Variant("", ua.VariantType.String)) # 4
        await printerInfoObj.add_variable(self.idx, "State message", ua.Variant("", ua.VariantType.String)) # 5
        await printerInfoObj.add_variable(self.idx, "Cumulated energy [J]", self.additional_printer_data["printer"]["Cumulated energy [J]"]) # 5
        await printerInfoObj.add_variable(self.idx, "Cumulated printing hours", self.additional_printer_data["printer"]["Cumulated printing hours"])


        #   systems object
        printerSystemObj = await self.printerObj.add_object(self.idx, "Systems")
        #      bed
        printerBedObj = await printerSystemObj.add_object(self.idx, "Bed")
        await printerBedObj.add_property(self.idx, "X dimension", self.additional_printer_data["printbed"]["X dimension"])
        await printerBedObj.add_property(self.idx, "Y dimension", self.additional_printer_data["printbed"]["Y dimension"])
        await printerBedObj.add_property(self.idx, "Rated power", self.additional_printer_data["printbed"]["Rated power"])
        await printerBedObj.add_variable(self.idx, "Temperature", 0.0)
        await printerBedObj.add_variable(self.idx, "Temperature set point", 0.0)
        await printerBedObj.add_variable(self.idx, "Power (PWM)", 0.0)
        await printerBedObj.add_variable(self.idx, "Power (computed [Watts])", 0.0)
        await printerBedObj.add_variable(self.idx, "Print plate present", ua.Variant(self.print_plate_manager.plate_present, ua.VariantType.Boolean))
        await printerBedObj.add_variable(self.idx, "Print plate ID", self.print_plate_manager.plate_id)

        #      hotend
        printerHotendObj = await printerSystemObj.add_object(self.idx, "Hotend")
        await printerHotendObj.add_property(self.idx, "Manufacturer", ua.Variant(self.additional_printer_data["hotend"]["Manufacturer"], ua.VariantType.String))
        await printerHotendObj.add_property(self.idx, "Model", ua.Variant(self.additional_printer_data["hotend"]["Model"], ua.VariantType.String))
        await printerHotendObj.add_property(self.idx, "Rated power", self.additional_printer_data["hotend"]["Rated power"])
        await printerHotendObj.add_property(self.idx, "Nozzle diameter", self.additional_printer_data["hotend"]["Nozzle diameter"])
        await printerHotendObj.add_variable(self.idx, "Nozzle printing hours", self.additional_printer_data["hotend"]["Nozzle printing hours"])
        await printerHotendObj.add_variable(self.idx, "Umblilical printing hours", self.additional_printer_data["hotend"]["Umblilical printing hours"])
        await printerHotendObj.add_variable(self.idx, "Temperature", 0.0)
        await printerHotendObj.add_variable(self.idx, "Temperature set point", 0.0)
        await printerHotendObj.add_variable(self.idx, "Power (PWM)", 0.0)
        await printerHotendObj.add_variable(self.idx, "Power (computed [Watts])", 0.0)
        await printerHotendObj.add_variable(self.idx, "X position", 0.0)
        await printerHotendObj.add_variable(self.idx, "Y position", 0.0)
        await printerHotendObj.add_variable(self.idx, "Z position", 0.0)
        await printerHotendObj.add_variable(self.idx, "E position", 0.0)
        await printerHotendObj.add_variable(self.idx, "Hot end fan ON", ua.Variant(False, ua.VariantType.Boolean))
        await printerHotendObj.add_variable(self.idx, "Piece cooling fan speed", 0.0)

        #      frame
        printerFrameObj = await printerSystemObj.add_object(self.idx, "Frame")
        await printerFrameObj.add_variable(self.idx, "Filament runout sensor ON", ua.Variant(False, ua.VariantType.Boolean))
        await printerFrameObj.add_variable(self.idx, "X endstop triggered", ua.Variant(False, ua.VariantType.Boolean))
        await printerFrameObj.add_variable(self.idx, "Y endstop triggered", ua.Variant(False, ua.VariantType.Boolean))
        await printerFrameObj.add_variable(self.idx, "Z endstop triggered", ua.Variant(False, ua.VariantType.Boolean))
        await printerFrameObj.add_variable(self.idx, "Chamber temperature", 0.0)

        #      spool
        printerSpoolObj = await printerSystemObj.add_object(self.idx, "Spool") # Structure from OpenTag spec. https://github.com/Bambu-Research-Group/RFID-Tag-Guide/blob/main/OpenTag.md
        await printerSpoolObj.add_property(self.idx, "Tag version", self.spool_manager.tag_data["Tag version"])
        await printerSpoolObj.add_property(self.idx, "Filament Manufacturer", ua.Variant(self.spool_manager.tag_data["Filament Manufacturer"], ua.VariantType.String))
        await printerSpoolObj.add_property(self.idx, "Material name", ua.Variant(self.spool_manager.tag_data["Material name"], ua.VariantType.String))
        await printerSpoolObj.add_property(self.idx, "Color Name", ua.Variant(self.spool_manager.tag_data["Color Name"], ua.VariantType.String))
        await printerSpoolObj.add_property(self.idx, "Diameter", self.spool_manager.tag_data["Diameter"])
        await printerSpoolObj.add_property(self.idx, "Weight (nominal)", self.spool_manager.tag_data["Weight (nominal)"])
        await printerSpoolObj.add_property(self.idx, "Print Temp (C)", self.spool_manager.tag_data["Print Temp (C)"])
        await printerSpoolObj.add_property(self.idx, "Bed Temp (C)", self.spool_manager.tag_data["Bed Temp (C)"])
        await printerSpoolObj.add_property(self.idx, "Density", self.spool_manager.tag_data["Density"])
        await printerSpoolObj.add_property(self.idx, "Color Hex", self.spool_manager.tag_data["Color Hex"])
        await printerSpoolObj.add_variable(self.idx, "Filament weight (measured)", self.spool_manager.tag_data["Filament weight (measured)"])
        await printerSpoolObj.add_variable(self.idx, "Filament length (measured)", self.spool_manager.tag_data["Filament length (measured)"])
        

        #   actions
        printerActionObj = await self.printerObj.add_object(self.idx, "Actions")

        # add a methods
        await printerActionObj.add_method(
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
            await self.stop()
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

        if method!= "notify_proc_stat_update":
            self._logger.debug("Received notification %s -> %s", method, data)

        # Subscription notifications
        if method == "notify_status_update":
            message = data[0]
            timestamp = data[1]
            self._logger.info("Received status update notnificatio %s -> %s", timestamp, message)

async def main():
    listener = OpcuaConnector("opc.tcp://0.0.0.0:4840/freeopcua/server/", "http://automation.ceff.ch")
    client = listener.client
    await listener.start()


    # Setup the adress space
    await listener.setup_address_space()

    response = await client.call_method("printer.info")
    
    # Set the printer_info printer_name and printer_status
    my_node = listener.server.get_node("ns=2;i=3")
    await my_node.set_value(response["hostname"])

    # Subscribe to printer object state changes
    
    async with listener.server:
        while listener.running:
            await asyncio.sleep(listener.update_period)

            # Querry the Moonraker-api and update nodes
            params = {"objects": 
              {"webhooks": ["state", "state_message"],
               "heater_bed": ["temperature", "target", "power"],
               "extruder": ["temperature", "target", "power"],
               "toolhead": ["position"],
               "fan": ["speed"],
               "filament_switch_sensor": ["filament_detected", "enabled"],
              }}
            response = await client.call_method("printer.objects.query", **params)
            # endstops = await client.call_method("printer.query_endstops.status")
            # update the ua nodes accordingly
            webhook = response.get("status", {}).get("webhooks", {})
            if webhook:
                my_node = await listener.printerObj.get_child(['2:Info', '2:State'])
                await my_node.set_value(webhook.get("state", "Unknown"))
                my_node = await listener.printerObj.get_child(['2:Info', '2:State message'])
                await my_node.set_value(webhook.get("state_message", "Unknown"))

            heaterbed = response.get("status", {}).get("heater_bed", {})
            bed_power = 0
            if heaterbed:
                my_node = await listener.printerObj.get_child(['2:Systems', '2:Bed', '2:Temperature'])
                await my_node.set_value(heaterbed.get("temperature", 0.0))
                my_node = await listener.printerObj.get_child(['2:Systems', '2:Bed', '2:Temperature set point'])
                await my_node.set_value(heaterbed.get("target", 0.0))
                my_node = await listener.printerObj.get_child(['2:Systems', '2:Bed', '2:Power (PWM)'])
                pow =heaterbed.get("power", 0.0)
                await my_node.set_value(pow)
                my_node = await listener.printerObj.get_child(['2:Systems', '2:Bed', '2:Power (computed [Watts])'])
                bed_power= listener.additional_printer_data["printbed"]["Rated power"]*pow
                await my_node.set_value(listener.additional_printer_data["printbed"]["Rated power"]*bed_power)


            extruder = response.get("status", {}).get("extruder", {})
            extruder_power=0
            if extruder:
                my_node = await listener.printerObj.get_child(['2:Systems', '2:Hotend', '2:Temperature'])
                await my_node.set_value(extruder.get("temperature", 0.0))
                my_node = await listener.printerObj.get_child(['2:Systems', '2:Hotend', '2:Temperature set point'])
                await my_node.set_value(extruder.get("target", 0.0))
                my_node = await listener.printerObj.get_child(['2:Systems', '2:Hotend', '2:Power (PWM)'])
                pow =extruder.get("power", 0.0)
                await my_node.set_value(pow)
                my_node = await listener.printerObj.get_child(['2:Systems', '2:Hotend', '2:Power (computed [Watts])'])
                extruder_power = listener.additional_printer_data["hotend"]["Rated power"]*pow
                await my_node.set_value(extruder_power)
            
            toolhead = response.get("status", {}).get("toolhead", {})
            if toolhead:
                position=toolhead.get("position", [0.0, 0.0, 0.0, 0.0])
                my_node = await listener.printerObj.get_child(['2:Systems', '2:Hotend', '2:X position'])
                await my_node.set_value(position[0])
                my_node = await listener.printerObj.get_child(['2:Systems', '2:Hotend', '2:Y position'])
                await my_node.set_value(position[1])
                my_node = await listener.printerObj.get_child(['2:Systems', '2:Hotend', '2:Z position'])
                await my_node.set_value(position[2])
                my_node = await listener.printerObj.get_child(['2:Systems', '2:Hotend', '2:E position'])
                await my_node.set_value(position[3])
            fan = response.get("status", {}).get("fan", {})
            if fan:
                my_node = await listener.printerObj.get_child(['2:Systems', '2:Hotend', '2:Piece cooling fan speed'])
                await my_node.set_value(fan.get("speed", 0.0))

            # Update energy
            energy_to_add = (listener.additional_printer_data["printer"]["Idle power"]+bed_power+extruder_power)*listener.update_period
            my_node = await listener.printerObj.get_child(['2:Info', '2:Cumulated energy [J]'])
            energy = await my_node.get_value() + energy_to_add
            await my_node.write_value(energy)




if __name__ == "__main__":

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())