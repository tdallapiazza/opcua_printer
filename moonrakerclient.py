
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
        self._logger = logging.getLogger(__name__)

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