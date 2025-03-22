import asyncio
import logging

logger = logging.getLogger(__name__)

class Printing_plate_manager():
    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.plate_present=False
        self.plate_id=None
        
    async def load(self):
        logger.info("Loading plate")
        await asyncio.sleep(5)
        self.plate_id=0x17a8bc34e20104e0 #RFID tag UID 64bit
        self.plate_present=True
        logger.info("Plate loaded")
    
    async def unload(self):
        logger.info("Unloading plate")
        await asyncio.sleep(5)
        self.plate_id=None #RFID tag UID 64bit
        self.plate_present=False
        logger.info("Plate unloaded")
