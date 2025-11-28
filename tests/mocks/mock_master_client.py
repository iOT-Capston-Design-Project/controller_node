"""Mock master node client for testing."""

from typing import Callable, Awaitable, List

from src.interfaces.communication import IMasterNodeClient
from src.domain.models import ControlSignal


class MockMasterNodeClient(IMasterNodeClient):
    """Mock implementation of master node client for testing."""

    def __init__(self):
        self._connected = False
        self._running = False
        self._signal_handler: Callable[[ControlSignal], Awaitable[None]] = None
        self._received_acks: List[bool] = []

    async def start(self) -> None:
        """Start the mock server."""
        self._running = True

    async def stop(self) -> None:
        """Stop the mock server."""
        self._running = False
        self._connected = False

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    def set_signal_handler(
        self, handler: Callable[[ControlSignal], Awaitable[None]]
    ) -> None:
        """Set signal handler."""
        self._signal_handler = handler

    async def send_ack(self) -> None:
        """Record ACK was sent."""
        self._received_acks.append(True)

    # Test helper methods
    def simulate_connect(self) -> None:
        """Simulate master node connection."""
        self._connected = True

    def simulate_disconnect(self) -> None:
        """Simulate master node disconnection."""
        self._connected = False

    async def simulate_signal(self, signal: ControlSignal) -> None:
        """Simulate receiving a control signal."""
        if self._signal_handler:
            await self._signal_handler(signal)

    def get_ack_count(self) -> int:
        """Get number of ACKs sent."""
        return len(self._received_acks)
