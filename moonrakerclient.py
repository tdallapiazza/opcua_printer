import asyncio
from moonraker_api import MoonrakerListener, MoonrakerClient


HOST = "localhost"
PORT = 7125


class APIConnector(MoonrakerListener):
    def __init__(self):
        self.running = False
        self.client = MoonrakerClient(
            self,
            HOST,
            PORT,
        )

    async def start(self) -> None:
        """Start the websocket connection."""
        self.running = True
        return await self.client.connect()

    async def stop(self) -> None:
        """Stop the websocket connection."""
        self.running = False
        await self.client.disconnect()