
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
from asyncua.common.xmlexporter import XmlExporter

HOST = "localhost"
PORT = 7125
PRINTER_INFO_FILE="printer_info.json"
MAPPINGS_FILE = "mappings.json"

logging.basicConfig(
    level=logging.WARNING, format="%(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("moonraker_api").setLevel(logging.DEBUG)
logging.getLogger(__name__).setLevel(logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


@uamethod
async def homeXYZ(parent):
    params = {"script": "G28"}
    res = await listener.client.call_method("printer.gcode.script", **params)
    return res

@uamethod
async def set_extruder_temperature(parent, temp):
    params = {"script": f'SET_HEATER_TEMPERATURE HEATER=extruder TARGET={temp}'}
    res = await listener.client.call_method("printer.gcode.script", **params)
    return res

@uamethod
async def set_bed_temperature(parent, temp):
    params = {"script": f'SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET={temp}'}
    res = await listener.client.call_method("printer.gcode.script", **params)
    return res

@uamethod
async def start_job(parent, file):
    params = {"filename": file}
    res = await listener.client.call_method("printer.print.start", **params)
    return res

@uamethod
async def pause_job(parent):
    res = await listener.client.call_method("printer.print.pause")
    return res

@uamethod
async def resume_job(parent):
    res = await listener.client.call_method("printer.print.resume")
    return res

@uamethod
async def cancel_job(parent):
    res = await listener.client.call_method("printer.print.cancel")
    return res

@uamethod
async def firmware_restart(parent):
    res = await listener.client.call_method("printer.firmware_restart")
    return res

@uamethod
async def reboot(parent):
    res = await listener.client.call_method("machine.reboot")
    return res

@uamethod
async def shutdown(parent):
    res = await listener.client.call_method("machine.shutdown")
    return res

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
        self.node_list=[]

        # add agregate managers
        self.spool_manager = spool_manager.SpoolManager()
        self.print_plate_manager = printing_plate_manager.Printing_plate_manager()

        # load additionnal printer data
        with open(PRINTER_INFO_FILE, 'r') as file:
            self.additional_printer_data = json.load(file)

        # load additionnal printer data
        with open(MAPPINGS_FILE, 'r') as file:
            self.mappings = json.load(file)
        
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
        self.node_list.append(self.printerObj)
        #   info object
        printerInfoObj = await self.printerObj.add_object(self.idx, "Info")
        self.node_list.append(printerInfoObj)
        obj=await printerInfoObj.add_property(self.idx, "Name", ua.Variant("", ua.VariantType.String)) # 3 
        self.node_list.append(obj)
        obj=await printerInfoObj.add_property(self.idx, "Manufacturer", ua.Variant(self.additional_printer_data["printer"]["Manufacturer"], ua.VariantType.String)) # 3
        self.node_list.append(obj)
        obj=await printerInfoObj.add_property(self.idx, "Model", ua.Variant(self.additional_printer_data["printer"]["Model"], ua.VariantType.String)) # 3
        self.node_list.append(obj)
        obj=await printerInfoObj.add_property(self.idx, "Idle power", self.additional_printer_data["printer"]["Idle power"]) # 3
        self.node_list.append(obj)
        obj=await printerInfoObj.add_property(self.idx, "Location", ua.Variant(self.additional_printer_data["printer"]["Location"], ua.VariantType.String))
        self.node_list.append(obj)
        obj=await printerInfoObj.add_variable(self.idx, "State", ua.Variant("", ua.VariantType.String)) # 4
        self.node_list.append(obj)
        obj=await printerInfoObj.add_variable(self.idx, "State message", ua.Variant("", ua.VariantType.String)) # 5
        self.node_list.append(obj)
        obj=await printerInfoObj.add_variable(self.idx, "Cumulated energy [J]", self.additional_printer_data["printer"]["Cumulated energy [J]"]) # 5
        self.node_list.append(obj)
        obj=await printerInfoObj.add_variable(self.idx, "Cumulated printing hours", 0.0)
        self.node_list.append(obj)

        #   systems object
        printerSystemObj = await self.printerObj.add_object(self.idx, "Systems")
        self.node_list.append(printerSystemObj)
        #      bed
        printerBedObj = await printerSystemObj.add_object(self.idx, "Bed")
        self.node_list.append(printerBedObj)
        obj=await printerBedObj.add_property(self.idx, "X dimension", self.additional_printer_data["printbed"]["X dimension"])
        self.node_list.append(obj)
        obj=await printerBedObj.add_property(self.idx, "Y dimension", self.additional_printer_data["printbed"]["Y dimension"])
        self.node_list.append(obj)
        obj=await printerBedObj.add_property(self.idx, "Rated power", self.additional_printer_data["printbed"]["Rated power"])
        self.node_list.append(obj)
        obj=await printerBedObj.add_variable(self.idx, "Temperature", 0.0)
        self.node_list.append(obj)
        obj=await printerBedObj.add_variable(self.idx, "Temperature set point", 0.0)
        self.node_list.append(obj)
        obj=await printerBedObj.add_variable(self.idx, "Power (PWM)", 0.0)
        self.node_list.append(obj)
        obj=await printerBedObj.add_variable(self.idx, "Power (computed [Watts])", 0.0)
        self.node_list.append(obj)
        obj=await printerBedObj.add_variable(self.idx, "Print plate present", ua.Variant(self.print_plate_manager.plate_present, ua.VariantType.Boolean))
        self.node_list.append(obj)
        obj=await printerBedObj.add_variable(self.idx, "Print plate ID", self.print_plate_manager.plate_id)
        self.node_list.append(obj)

        #      hotend
        printerHotendObj = await printerSystemObj.add_object(self.idx, "Hotend")
        self.node_list.append(printerHotendObj)
        obj=await printerHotendObj.add_property(self.idx, "Manufacturer", ua.Variant(self.additional_printer_data["hotend"]["Manufacturer"], ua.VariantType.String))
        self.node_list.append(obj)
        obj=await printerHotendObj.add_property(self.idx, "Model", ua.Variant(self.additional_printer_data["hotend"]["Model"], ua.VariantType.String))
        self.node_list.append(obj)
        obj=await printerHotendObj.add_property(self.idx, "Rated power", self.additional_printer_data["hotend"]["Rated power"])
        self.node_list.append(obj)
        obj=await printerHotendObj.add_property(self.idx, "Nozzle diameter", self.additional_printer_data["hotend"]["Nozzle diameter"])
        self.node_list.append(obj)
        obj=await printerHotendObj.add_variable(self.idx, "Nozzle printing hours", self.additional_printer_data["hotend"]["Nozzle printing hours"])
        self.node_list.append(obj)
        obj=await printerHotendObj.add_variable(self.idx, "Umblilical printing hours", self.additional_printer_data["hotend"]["Umblilical printing hours"])
        self.node_list.append(obj)
        obj=await printerHotendObj.add_variable(self.idx, "Temperature", 0.0)
        self.node_list.append(obj)
        obj=await printerHotendObj.add_variable(self.idx, "Temperature set point", 0.0)
        self.node_list.append(obj)
        obj=await printerHotendObj.add_variable(self.idx, "Power (PWM)", 0.0)
        self.node_list.append(obj)
        obj=await printerHotendObj.add_variable(self.idx, "Power (computed [Watts])", 0.0)
        self.node_list.append(obj)
        obj=await printerHotendObj.add_variable(self.idx, "Hot end fan ON", ua.Variant(False, ua.VariantType.Boolean))
        self.node_list.append(obj)
        obj=await printerHotendObj.add_variable(self.idx, "Piece cooling fan speed", 0.0)
        self.node_list.append(obj)

        #      frame
        printerFrameObj = await printerSystemObj.add_object(self.idx, "Frame")
        self.node_list.append(printerFrameObj)
        obj=await printerFrameObj.add_variable(self.idx, "Filament present", ua.Variant(False, ua.VariantType.Boolean))
        self.node_list.append(obj)
        obj=await printerFrameObj.add_variable(self.idx, "X endstop triggered", ua.Variant(False, ua.VariantType.Boolean))
        self.node_list.append(obj)
        obj=await printerFrameObj.add_variable(self.idx, "Y endstop triggered", ua.Variant(False, ua.VariantType.Boolean))
        self.node_list.append(obj)
        obj=await printerFrameObj.add_variable(self.idx, "Z endstop triggered", ua.Variant(False, ua.VariantType.Boolean))
        self.node_list.append(obj)
        obj=await printerFrameObj.add_variable(self.idx, "Chamber temperature", 0.0)
        self.node_list.append(obj)

        #      spool
        printerSpoolObj = await printerSystemObj.add_object(self.idx, "Spool") # Structure from OpenTag spec. https://github.com/Bambu-Research-Group/RFID-Tag-Guide/blob/main/OpenTag.md
        self.node_list.append(printerSpoolObj)
        obj=await printerSpoolObj.add_property(self.idx, "Tag version", self.spool_manager.tag_data["Tag version"])
        self.node_list.append(obj)
        obj=await printerSpoolObj.add_property(self.idx, "Filament Manufacturer", ua.Variant(self.spool_manager.tag_data["Filament Manufacturer"], ua.VariantType.String))
        self.node_list.append(obj)
        obj=await printerSpoolObj.add_property(self.idx, "Material name", ua.Variant(self.spool_manager.tag_data["Material name"], ua.VariantType.String))
        self.node_list.append(obj)
        obj=await printerSpoolObj.add_property(self.idx, "Color Name", ua.Variant(self.spool_manager.tag_data["Color Name"], ua.VariantType.String))
        self.node_list.append(obj)
        obj=await printerSpoolObj.add_property(self.idx, "Diameter", self.spool_manager.tag_data["Diameter"])
        self.node_list.append(obj)
        obj=await printerSpoolObj.add_property(self.idx, "Weight (nominal)", self.spool_manager.tag_data["Weight (nominal)"])
        self.node_list.append(obj)
        obj=await printerSpoolObj.add_property(self.idx, "Print Temp (C)", self.spool_manager.tag_data["Print Temp (C)"])
        self.node_list.append(obj)
        obj=await printerSpoolObj.add_property(self.idx, "Bed Temp (C)", self.spool_manager.tag_data["Bed Temp (C)"])
        self.node_list.append(obj)
        obj=await printerSpoolObj.add_property(self.idx, "Density", self.spool_manager.tag_data["Density"])
        self.node_list.append(obj)
        obj=await printerSpoolObj.add_property(self.idx, "Color Hex", self.spool_manager.tag_data["Color Hex"])
        self.node_list.append(obj)
        obj=await printerSpoolObj.add_variable(self.idx, "Filament weight (measured)", self.spool_manager.tag_data["Filament weight (measured)"])
        self.node_list.append(obj)
        obj=await printerSpoolObj.add_variable(self.idx, "Filament length (measured)", self.spool_manager.tag_data["Filament length (measured)"])
        self.node_list.append(obj)
        
        #   job object
        printerJobObj = await self.printerObj.add_object(self.idx, "Job")
        self.node_list.append(printerJobObj)
        obj=await printerJobObj.add_variable(self.idx, "State", ua.Variant("", ua.VariantType.String))
        self.node_list.append(obj)
        obj=await printerJobObj.add_variable(self.idx, "State message", ua.Variant("", ua.VariantType.String))
        self.node_list.append(obj)
        obj=await printerJobObj.add_variable(self.idx, "Total job duration [s]", 0.0)
        self.node_list.append(obj)
        obj=await printerJobObj.add_variable(self.idx, "Job print time spent [s]", 0.0)
        self.node_list.append(obj)

        #   actions
        printerActionObj = await self.printerObj.add_object(self.idx, "Actions")
        self.node_list.append(printerActionObj)

        # add a methods
        obj=await printerActionObj.add_method(
            ua.NodeId("Home all axis", self.idx),
            ua.QualifiedName("Home all axis", self.idx),
            homeXYZ,
            [],
            [ua.VariantType.String]
        )
        self.node_list.append(obj)

        obj=await printerActionObj.add_method(
            ua.NodeId("Set extruder tempertature", self.idx),
            ua.QualifiedName("Set extruder tempertature", self.idx),
            set_extruder_temperature,
            [ua.VariantType.Int64],
            [ua.VariantType.String]
        )
        self.node_list.append(obj)

        obj=await printerActionObj.add_method(
            ua.NodeId("Set bed tempertature", self.idx),
            ua.QualifiedName("Set bed tempertature", self.idx),
            set_bed_temperature,
            [ua.VariantType.Int64],
            [ua.VariantType.String]
        )
        self.node_list.append(obj)

        obj=await printerActionObj.add_method(
            ua.NodeId("Start job", self.idx),
            ua.QualifiedName("Start job", self.idx),
            start_job,
            [ua.VariantType.String],
            [ua.VariantType.String]
        )
        self.node_list.append(obj)

        obj=await printerActionObj.add_method(
            ua.NodeId("Pause job", self.idx),
            ua.QualifiedName("Pause job", self.idx),
            pause_job,
            [],
            [ua.VariantType.String]
        )
        self.node_list.append(obj)

        obj=await printerActionObj.add_method(
            ua.NodeId("Resume job", self.idx),
            ua.QualifiedName("Resume job", self.idx),
            resume_job,
            [],
            [ua.VariantType.String]
        )
        self.node_list.append(obj)

        obj=await printerActionObj.add_method(
            ua.NodeId("Cancel job", self.idx),
            ua.QualifiedName("Cancel job", self.idx),
            cancel_job,
            [],
            [ua.VariantType.String]
        )
        self.node_list.append(obj)

        obj=await printerActionObj.add_method(
            ua.NodeId("Firmware restart", self.idx),
            ua.QualifiedName("Firmware restart", self.idx),
            firmware_restart,
            [],
            [ua.VariantType.String]
        )
        self.node_list.append(obj)

        obj=await printerActionObj.add_method(
            ua.NodeId("Reboot", self.idx),
            ua.QualifiedName("Reboot", self.idx),
            reboot,
            [],
            [ua.VariantType.String]
        )
        self.node_list.append(obj)

        obj=await printerActionObj.add_method(
            ua.NodeId("Shutdown", self.idx),
            ua.QualifiedName("Shutdown", self.idx),
            shutdown,
            [],
            [ua.VariantType.String]
        )
        self.node_list.append(obj)

        

    async def update_databank(self, mapping, message):
        # go over all keys in message dict
        for key in message.keys():
            # try to find the corresponding opcua_key in mapping
            opcua_key=mapping.get(key,None)
            if opcua_key is not None:
                # Get the opc_ua node
                my_node = await self.printerObj.get_child(opcua_key)
                val = message[key]
                # Check that the value is not None
                # TODO better would be the check if the type is the one expected by the opc_ua node
                if val is not None:
                    # Update the value
                    await my_node.set_value(message[key])

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
    global listener
    listener = OpcuaConnector("opc.tcp://0.0.0.0:4840/freeopcua/server/", "http://automation.ceff.ch")


    client = listener.client
    await listener.start()


    # Setup the adress space
    await listener.setup_address_space()

    # Export to xml
    exporter = XmlExporter(listener.server)
    await exporter.build_etree(listener.node_list)
    await exporter.write_xml("ua-export.xml")

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
               "fan": ["speed"],
               "heater_fan hotend_fan": ["speed"],
               "filament_switch_sensor Filament_Runout_Sensor": ["filament_detected"],
               "print_stats": ["total_duration", "print_duration", "state", "message"]
              }}
            response = await client.call_method("printer.objects.query", **params)

            # update the ua nodes accordingly
            # webhook
            webhook = response.get("status", {}).get("webhooks", {})
            if bool(webhook):
                await listener.update_databank(listener.mappings["webhooks"], webhook)

            # heater_bed
            heaterbed = response.get("status", {}).get("heater_bed", {})
            bed_power = 0
            if bool(heaterbed):
                await listener.update_databank(listener.mappings["heater_bed"], heaterbed)
                pow =heaterbed.get("power", 0.0)
                my_node = await listener.printerObj.get_child(['2:Systems', '2:Bed', '2:Power (computed [Watts])'])
                bed_power= listener.additional_printer_data["printbed"]["Rated power"]*pow
                await my_node.set_value(bed_power)

            # extruder
            extruder = response.get("status", {}).get("extruder", {})
            extruder_power=0
            if bool(extruder):
                await listener.update_databank(listener.mappings["extruder"], extruder)
                pow =extruder.get("power", 0.0)
                my_node = await listener.printerObj.get_child(['2:Systems', '2:Hotend', '2:Power (computed [Watts])'])
                extruder_power = listener.additional_printer_data["hotend"]["Rated power"]*pow
                await my_node.set_value(extruder_power)
            
            # fan
            fan = response.get("status", {}).get("fan", {})
            if bool(fan):
                await listener.update_databank(listener.mappings["fan"], fan)

            # heater_fan
            heater_fan = response.get("status", {}).get("heater_fan hotend_fan", {})
            if bool(heater_fan):
                key = listener.mappings["heater_fan"]["speed"]
                my_node = await listener.printerObj.get_child(key)
                speed =  heater_fan.get("speed", 0)
                if speed is not None:
                    if speed>0:
                        await my_node.set_value(True)
                    else:
                        await my_node.set_value(False)

            # filament_switch_sensor
            filament_switch_sensor=response.get("status", {}).get("filament_switch_sensor Filament_Runout_Sensor", {})
            if bool(filament_switch_sensor):
                await listener.update_databank(listener.mappings["filament_switch_sensor"], filament_switch_sensor)

            print_stats = response.get("status", {}).get("print_stats", {})
            if bool(print_stats):
                await listener.update_databank(listener.mappings["print_stats"], print_stats)
            
            # Get other non-printer objects

            response = await client.call_method("server.history.totals")
            job_totals = response.get("job_totals",{})
            if bool(job_totals):
                await listener.update_databank(listener.mappings["job_totals"], job_totals)

            # Update energy
            energy_to_add = (listener.additional_printer_data["printer"]["Idle power"]+bed_power+extruder_power)*listener.update_period
            my_node = await listener.printerObj.get_child(['2:Info', '2:Cumulated energy [J]'])
            energy = await my_node.get_value() + energy_to_add
            await my_node.write_value(energy)




if __name__ == "__main__":

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())