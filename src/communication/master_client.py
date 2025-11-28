"""Master node communication implementation.

Controller node acts as a TCP server, listening for control signals
from the master node via LAN connection.
"""

import asyncio
import json
import logging
from typing import Optional, Callable, Awaitable

from ..interfaces.communication import IMasterNodeClient
from ..domain.models import ControlSignal
from ..config.settings import settings

logger = logging.getLogger(__name__)


class MasterNodeClient(IMasterNodeClient):
    """TCP server implementation for master node communication.

    Listens for incoming connections from master node and processes
    control signals received via JSON messages.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: Optional[int] = None,
    ):
        """Initialize the master node client.

        Args:
            host: Host address to bind to (default: all interfaces).
            port: Port to listen on (default: from settings).
        """
        self._host = host
        self._port = port or settings.master_node_port
        self._server: Optional[asyncio.Server] = None
        self._client_writer: Optional[asyncio.StreamWriter] = None
        self._client_reader: Optional[asyncio.StreamReader] = None
        self._signal_handler: Optional[Callable[[ControlSignal], Awaitable[None]]] = None
        self._connected = False
        self._running = False

    async def start(self) -> None:
        """Start the TCP server to listen for master node connections."""
        self._running = True
        self._server = await asyncio.start_server(
            self._handle_connection,
            self._host,
            self._port,
        )
        addr = self._server.sockets[0].getsockname()
        logger.info(f"TCP server started on {addr[0]}:{addr[1]}")

        # Start serving in background
        asyncio.create_task(self._serve())

    async def _serve(self) -> None:
        """Background task to serve connections."""
        if self._server:
            async with self._server:
                await self._server.serve_forever()

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle incoming connection from master node.

        Args:
            reader: Stream reader for incoming data.
            writer: Stream writer for outgoing data.
        """
        addr = writer.get_extra_info("peername")
        logger.info(f"Master node connected from {addr}")

        # Close existing connection if any
        if self._client_writer:
            await self._close_client()

        self._client_reader = reader
        self._client_writer = writer
        self._connected = True

        try:
            await self._read_loop()
        except asyncio.CancelledError:
            logger.info("Connection handler cancelled")
        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            self._connected = False
            logger.info(f"Master node disconnected from {addr}")

    async def _read_loop(self) -> None:
        """Continuously read and process messages from master node."""
        while self._running and self._client_reader:
            try:
                # Read until newline (JSON message delimiter)
                data = await self._client_reader.readline()
                if not data:
                    break

                message = data.decode().strip()
                if not message:
                    continue

                logger.debug(f"Received: {message}")

                # Parse JSON message
                try:
                    signal_data = json.loads(message)
                    signal = ControlSignal.from_dict(signal_data)

                    # Call signal handler if set
                    if self._signal_handler:
                        await self._signal_handler(signal)

                    # Send acknowledgment
                    await self.send_ack()

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")

            except asyncio.IncompleteReadError:
                break
            except ConnectionResetError:
                break

    async def _close_client(self) -> None:
        """Close current client connection."""
        if self._client_writer:
            try:
                self._client_writer.close()
                await self._client_writer.wait_closed()
            except Exception as e:
                logger.error(f"Error closing client: {e}")
            finally:
                self._client_writer = None
                self._client_reader = None
                self._connected = False

    async def stop(self) -> None:
        """Stop the TCP server and close connections."""
        self._running = False

        await self._close_client()

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        logger.info("TCP server stopped")

    def is_connected(self) -> bool:
        """Check if master node is currently connected."""
        return self._connected

    def set_signal_handler(
        self, handler: Callable[[ControlSignal], Awaitable[None]]
    ) -> None:
        """Set the callback handler for received control signals.

        Args:
            handler: Async function to call when a signal is received.
        """
        self._signal_handler = handler

    async def send_ack(self) -> None:
        """Send acknowledgment to master node after processing signal."""
        if self._client_writer:
            try:
                self._client_writer.write(b"ACK\n")
                await self._client_writer.drain()
                logger.debug("ACK sent to master node")
            except Exception as e:
                logger.error(f"Failed to send ACK: {e}")
