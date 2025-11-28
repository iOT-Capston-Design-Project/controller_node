"""Control service implementation.

Processes control signals from master node and converts them
into device commands.
"""

import logging
from datetime import datetime
from typing import List

from ..interfaces.service import IControlService
from ..domain.models import ControlSignal, DeviceCommand
from ..domain.enums import DeviceZone, ControlAction

logger = logging.getLogger(__name__)


class ControlService(IControlService):
    """Service for processing control signals into device commands."""

    # Mapping from zone number to DeviceZone enum
    ZONE_MAP = {
        1: DeviceZone.ZONE_1,
        2: DeviceZone.ZONE_2,
        3: DeviceZone.ZONE_3,
        4: DeviceZone.ZONE_4,
        5: DeviceZone.ZONE_5,
        6: DeviceZone.ZONE_6,
        7: DeviceZone.ZONE_7,
    }

    def process_signal(self, signal: ControlSignal) -> List[DeviceCommand]:
        """Convert a control signal into device commands.

        Args:
            signal: Control signal from master node.

        Returns:
            List of device commands to execute.
        """
        commands: List[DeviceCommand] = []

        # Skip if no action or no target zones
        if signal.action == ControlAction.NONE or not signal.target_zones:
            logger.debug("No action required from signal")
            return commands

        timestamp = datetime.now()

        for zone_num in signal.target_zones:
            # Validate zone number
            if zone_num not in self.ZONE_MAP:
                logger.warning(f"Invalid zone number: {zone_num}")
                continue

            zone = self.ZONE_MAP[zone_num]

            command = DeviceCommand(
                zone=zone,
                action=signal.action,
                intensity=signal.intensity,
                timestamp=timestamp,
            )

            commands.append(command)
            logger.debug(f"Generated command: {command}")

        logger.info(f"Processed signal: {len(commands)} commands generated")
        return commands
