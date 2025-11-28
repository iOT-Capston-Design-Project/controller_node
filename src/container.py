"""Dependency injection container for Controller Node."""

from dataclasses import dataclass

from .interfaces.communication import IMasterNodeClient
from .interfaces.device import ISerialDevice
from .interfaces.service import IControlService, IServiceFacade
from .interfaces.presentation import IDisplay

from .communication.master_client import MasterNodeClient
from .communication.serial_device import SerialDevice
from .service.control_service import ControlService
from .service.service_facade import ServiceFacade
from .presentation.console_display import ConsoleDisplay


@dataclass
class Container:
    """Dependency injection container.

    Holds all service instances for the application.
    """

    master_client: IMasterNodeClient
    serial_device: ISerialDevice
    control_service: IControlService
    display: IDisplay
    service_facade: IServiceFacade


def create_container() -> Container:
    """Create production container with all dependencies.

    Returns:
        Container with all production service implementations.
    """
    # Communication
    master_client = MasterNodeClient()
    serial_device = SerialDevice()

    # Services
    control_service = ControlService()

    # Presentation
    display = ConsoleDisplay()

    # Facade (orchestrates everything)
    service_facade = ServiceFacade(
        master_client=master_client,
        serial_device=serial_device,
        control_service=control_service,
        display=display,
    )

    return Container(
        master_client=master_client,
        serial_device=serial_device,
        control_service=control_service,
        display=display,
        service_facade=service_facade,
    )


def create_test_container(
    master_client: IMasterNodeClient = None,
    serial_device: ISerialDevice = None,
    control_service: IControlService = None,
    display: IDisplay = None,
) -> Container:
    """Create test container with mock dependencies.

    Args:
        master_client: Mock master client (optional).
        serial_device: Mock serial device (optional).
        control_service: Mock control service (optional).
        display: Mock display (optional).

    Returns:
        Container with mock or production implementations.
    """
    _master_client = master_client or MasterNodeClient()
    _serial_device = serial_device or SerialDevice()
    _control_service = control_service or ControlService()
    _display = display or ConsoleDisplay()

    service_facade = ServiceFacade(
        master_client=_master_client,
        serial_device=_serial_device,
        control_service=_control_service,
        display=_display,
    )

    return Container(
        master_client=_master_client,
        serial_device=_serial_device,
        control_service=_control_service,
        display=_display,
        service_facade=service_facade,
    )
