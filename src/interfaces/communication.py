"""Communication interfaces for Controller Node."""

from abc import ABC, abstractmethod
from typing import Optional, Callable, Awaitable

from ..domain.models import ControlSignal


class IMasterNodeClient(ABC):
    """Interface for communication with master node via LAN.

    Controller node acts as a TCP server, waiting for connections
    from master node and receiving control signals.
    """

    @abstractmethod
    async def start(self) -> None:
        """Start the TCP server to listen for master node connections."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the TCP server and close connections."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if master node is currently connected."""
        pass

    @abstractmethod
    def set_signal_handler(
        self, handler: Callable[[ControlSignal], Awaitable[None]]
    ) -> None:
        """Set the callback handler for received control signals.

        Args:
            handler: Async function to call when a signal is received.
        """
        pass

    @abstractmethod
    async def send_ack(self) -> None:
        """Send acknowledgment to master node after processing signal."""
        pass
