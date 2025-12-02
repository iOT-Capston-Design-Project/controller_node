"""Main entry point for Controller Node application."""

import argparse
import asyncio
import logging
import signal
import sys
from typing import Optional

from .container import create_container, create_test_container, Container
from .config.settings import settings


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Controller Node Application")
    parser.add_argument(
        "--test",
        action="store_true",
        help="테스트 모드로 실행 (임의 센서 데이터 생성 및 마스터 노드 전송)",
    )
    parser.add_argument(
        "--serial-test",
        action="store_true",
        help="시리얼 테스트 모드 (실제 아두이노에 테스트 명령 전송)",
    )
    parser.add_argument(
        "--test-interval",
        type=float,
        default=5.0,
        help="시리얼 테스트 명령 전송 주기 (초, 기본: 5.0)",
    )
    return parser.parse_args()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("controller_node.log"),
    ],
)

logger = logging.getLogger(__name__)


class Application:
    """Main application class for Controller Node."""

    def __init__(
        self,
        test_mode: bool = False,
        serial_test_mode: bool = False,
        test_interval: float = 5.0,
    ):
        """Initialize application.

        Args:
            test_mode: 테스트 모드 여부. True면 임의 센서 데이터 생성.
            serial_test_mode: 시리얼 테스트 모드. True면 실제 아두이노에 테스트 명령 전송.
            test_interval: 시리얼 테스트 명령 전송 주기 (초).
        """
        self._container: Optional[Container] = None
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._test_mode = test_mode
        self._serial_test_mode = serial_test_mode
        self._test_interval = test_interval

    async def start(self) -> None:
        """Start the application."""
        if self._serial_test_mode:
            mode_str = " (시리얼 테스트 모드)"
        elif self._test_mode:
            mode_str = " (테스트 모드)"
        else:
            mode_str = ""

        logger.info(f"Starting Controller Node{mode_str}...")
        logger.info(f"Device ID: {settings.device_id}")
        logger.info(f"Listening on port: {settings.master_node_port}")

        # Create container with dependencies
        if self._serial_test_mode:
            # 시리얼 테스트 모드: 실제 아두이노에 테스트 명령 전송
            from .communication.mock_serial_device import SerialTestDevice
            from .presentation.console_display import ConsoleDisplay

            # Display 먼저 생성
            display = ConsoleDisplay()

            # 시퀀스 전송 시 TUI에 표시하는 콜백
            def on_sequence_sent(zones):
                display.show_sequence_sent(zones)

            serial_device = SerialTestDevice(
                test_interval=self._test_interval,
                on_sequence_sent=on_sequence_sent,
            )
            self._container = create_test_container(
                serial_device=serial_device,
                display=display,
            )
            logger.info(f"시리얼 테스트 모드: {self._test_interval}초 간격으로 명령 전송")
        elif self._test_mode:
            # 테스트 모드: 임의 센서 데이터 생성 (시리얼 통신 없음)
            from .communication.mock_serial_device import MockSerialDeviceWithSensorData
            mock_serial = MockSerialDeviceWithSensorData()
            self._container = create_test_container(serial_device=mock_serial)
        else:
            self._container = create_container()

        # Setup signal handlers
        self._setup_signal_handlers()

        # Initialize services
        await self._container.service_facade.initialize()

        self._running = True
        logger.info("Controller Node started successfully")

        # Start status update loop
        asyncio.create_task(self._status_update_loop())

        # Wait for shutdown signal
        await self._shutdown_event.wait()

    async def _status_update_loop(self) -> None:
        """Periodically update display with current status."""
        while self._running and not self._shutdown_event.is_set():
            if self._container:
                status = self._container.service_facade.get_system_status()
                self._container.display.update_status(status)
            await asyncio.sleep(0.5)  # Update every 500ms

    async def stop(self) -> None:
        """Stop the application."""
        if not self._running:
            return

        logger.info("Stopping Controller Node...")
        self._running = False

        if self._container:
            await self._container.service_facade.shutdown()

        logger.info("Controller Node stopped")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(self._handle_signal()),
            )

    async def _handle_signal(self) -> None:
        """Handle shutdown signal."""
        logger.info("Shutdown signal received")
        self._shutdown_event.set()


async def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Set global test mode flag
    settings.test_mode = args.test or args.serial_test

    app = Application(
        test_mode=args.test,
        serial_test_mode=args.serial_test,
        test_interval=args.test_interval,
    )

    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
    finally:
        await app.stop()


def run() -> None:
    """Run the application."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
