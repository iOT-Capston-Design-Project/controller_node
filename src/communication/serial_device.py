"""Serial device communication implementation.

This module provides serial communication with the Arduino control device.
"""

import asyncio
import logging
import threading
from datetime import datetime
from typing import List, Optional
from queue import Queue, Empty

import serial

from ..interfaces.device import ISerialDevice, IDeviceProtocol
from ..domain.models import DeviceCommand, DeviceStatus, SensorData
from ..domain.enums import DeviceZone, ControlAction
from ..config.settings import settings

logger = logging.getLogger(__name__)


class ArduinoProtocol(IDeviceProtocol):
    """Arduino protocol implementation.

    Commands:
    - S: Start/Run pattern
    - P: Pause/Stop pattern
    - Z<zone>:<action>: Zone control command (on/off only)
    """

    def encode_command(self, command: DeviceCommand) -> bytes:
        """Encode a command to bytes for serial transmission.

        Format: "Z<zone>:<action>\n"
        Example: "Z1:inflate\n"
        """
        return f"Z{command.zone.value}:{command.action.value}\n".encode()

    def decode_response(self, data: bytes) -> dict:
        """Decode response from device.

        Expects "OK", "ERR:<message>", or log messages from Arduino.
        """
        try:
            response = data.decode("utf-8", errors="ignore").strip()
            if not response:
                return {"success": True, "message": ""}
            if response == "OK":
                return {"success": True, "message": "OK"}
            elif response.startswith("ERR:"):
                return {"success": False, "error": response[4:]}
            else:
                # Arduino log message
                return {"success": True, "message": response, "is_log": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def encode_status_request(self) -> bytes:
        """Encode a status query request."""
        return b"STATUS\n"

    def encode_emergency_stop(self) -> bytes:
        """Encode emergency stop command."""
        return b"P"  # Pause command for Arduino

    def encode_start(self) -> bytes:
        """Encode start command."""
        return b"S"

    def encode_pause(self) -> bytes:
        """Encode pause command."""
        return b"P"


class SerialDevice(ISerialDevice):
    """Serial device implementation for Arduino communication."""

    def __init__(
        self,
        port: Optional[str] = None,
        baudrate: Optional[int] = None,
        protocol: Optional[IDeviceProtocol] = None,
    ):
        """Initialize serial device.

        Args:
            port: Serial port path (default: from settings).
            baudrate: Baud rate (default: from settings).
            protocol: Protocol implementation for encoding/decoding.
        """
        self._port = port or settings.serial_port
        self._baudrate = baudrate or settings.serial_baudrate
        self._protocol = protocol or ArduinoProtocol()
        self._connected = False
        self._serial: Optional[serial.Serial] = None

        # Device state
        self._zone_states: dict = {zone.value: 0 for zone in DeviceZone}
        self._last_command_success = True
        self._error_message: Optional[str] = None

        # Reader thread for Arduino logs
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_reader = threading.Event()
        self._response_queue: Queue = Queue()
        self._log_queue: Queue = Queue()
        self._sensor_data_queue: Queue = Queue()  # 센서 데이터 큐

    def _reader_loop(self) -> None:
        """Background thread to read Arduino serial output."""
        while not self._stop_reader.is_set():
            try:
                if self._serial and self._serial.is_open:
                    line = self._serial.readline()
                    if line:
                        decoded = line.decode("utf-8", errors="ignore").strip()
                        if decoded:
                            logger.info(f"[Arduino] {decoded}")

                            # 센서 데이터 형식 확인
                            # 형식 1: JSON {"inflated_zones": [1, 2, 3]}
                            # 형식 2: 간단한 리스트 "ZONES:1,2,3" 또는 "ZONES:"(빈 리스트)
                            if decoded.startswith("{") and "inflated_zones" in decoded:
                                try:
                                    import json
                                    sensor_json = json.loads(decoded)
                                    sensor_data = SensorData(
                                        inflated_zones=sensor_json.get("inflated_zones", [])
                                    )
                                    self._sensor_data_queue.put(sensor_data)
                                    logger.debug(f"Sensor data received: zones={sensor_data.inflated_zones}")
                                    continue
                                except json.JSONDecodeError:
                                    pass
                            elif decoded.startswith("ZONES:"):
                                zones_str = decoded[6:]  # "ZONES:" 이후 부분
                                if zones_str:
                                    inflated_zones = [int(z.strip()) for z in zones_str.split(",") if z.strip()]
                                else:
                                    inflated_zones = []
                                sensor_data = SensorData(inflated_zones=inflated_zones)
                                self._sensor_data_queue.put(sensor_data)
                                logger.debug(f"Sensor data received: zones={sensor_data.inflated_zones}")
                                continue

                            # Parse response
                            result = self._protocol.decode_response(line)
                            if result.get("is_log"):
                                self._log_queue.put(decoded)
                            else:
                                self._response_queue.put(result)
            except serial.SerialException as e:
                logger.error(f"Serial read error: {e}")
                self._stop_reader.set()
                break
            except Exception as e:
                logger.error(f"Reader error: {e}")

    async def connect(self) -> bool:
        """Establish serial connection to the device.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                timeout=1.0,
            )

            # Wait for Arduino reset
            await asyncio.sleep(2.0)

            # Start reader thread
            self._stop_reader.clear()
            self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self._reader_thread.start()

            logger.info(f"Serial device connected on {self._port} @ {self._baudrate} baud")
            self._connected = True
            return True

        except serial.SerialException as e:
            logger.error(f"Failed to connect to serial device: {e}")
            self._error_message = str(e)
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"Failed to connect to serial device: {e}")
            self._error_message = str(e)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close serial connection."""
        # Stop reader thread
        self._stop_reader.set()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2.0)

        if self._serial and self._serial.is_open:
            self._serial.close()

        self._serial = None
        self._connected = False
        logger.info("Serial device disconnected")

    def is_connected(self) -> bool:
        """Check if device is currently connected."""
        return self._connected and self._serial is not None and self._serial.is_open

    async def send_command(self, command: DeviceCommand) -> bool:
        """Send a single command to the device.

        Args:
            command: The command to execute.

        Returns:
            True if command was acknowledged, False otherwise.
        """
        if not self.is_connected():
            logger.error("Cannot send command: device not connected")
            return False

        try:
            # Encode and send command
            data = self._protocol.encode_command(command)
            logger.debug(f"Sending command: {data.decode().strip()}")
            self._serial.write(data)

            # Wait for response with timeout
            try:
                response = self._response_queue.get(timeout=2.0)
                if response.get("success"):
                    # Update zone state (on/off only)
                    if command.action == ControlAction.INFLATE:
                        self._zone_states[command.zone.value] = 1  # on
                    elif command.action == ControlAction.DEFLATE:
                        self._zone_states[command.zone.value] = 0  # off

                    logger.info(f"Command executed: {command}")
                    self._last_command_success = True
                    return True
                else:
                    self._error_message = response.get("error", "Unknown error")
                    logger.error(f"Command failed: {self._error_message}")
                    self._last_command_success = False
                    return False
            except Empty:
                # No response, assume success for now (Arduino may not send OK)
                if command.action == ControlAction.INFLATE:
                    self._zone_states[command.zone.value] = 1  # on
                elif command.action == ControlAction.DEFLATE:
                    self._zone_states[command.zone.value] = 0  # off

                logger.info(f"Command sent (no ack): {command}")
                self._last_command_success = True
                return True

        except Exception as e:
            logger.error(f"Failed to send command: {e}")
            self._error_message = str(e)
            self._last_command_success = False
            return False

    async def send_commands(self, commands: List[DeviceCommand]) -> bool:
        """Send multiple commands to the device.

        Args:
            commands: List of commands to execute.

        Returns:
            True if all commands were acknowledged, False otherwise.
        """
        success = True
        for command in commands:
            if not await self.send_command(command):
                success = False
        return success

    async def send_raw(self, data: bytes) -> bool:
        """Send raw bytes to the device.

        Args:
            data: Raw bytes to send.

        Returns:
            True if sent successfully.
        """
        if not self.is_connected():
            logger.error("Cannot send raw data: device not connected")
            return False

        try:
            self._serial.write(data)
            logger.debug(f"Sent raw: {data}")
            return True
        except Exception as e:
            logger.error(f"Failed to send raw data: {e}")
            return False

    async def start_pattern(self) -> bool:
        """Send start command to Arduino."""
        if not self.is_connected():
            return False
        return await self.send_raw(self._protocol.encode_start())

    async def pause_pattern(self) -> bool:
        """Send pause command to Arduino."""
        if not self.is_connected():
            return False
        return await self.send_raw(self._protocol.encode_pause())

    async def get_status(self) -> DeviceStatus:
        """Query current device status.

        Returns:
            Current status of the device.
        """
        return DeviceStatus(
            zone_states=self._zone_states.copy(),
            is_operational=self.is_connected(),
            last_command_success=self._last_command_success,
            error_message=self._error_message,
            last_updated=datetime.now(),
        )

    async def emergency_stop(self) -> bool:
        """Emergency stop all device operations.

        Returns:
            True if stop command was acknowledged.
        """
        if not self.is_connected():
            return False

        try:
            # Send pause command
            data = self._protocol.encode_emergency_stop()
            self._serial.write(data)

            # Reset all zones
            self._zone_states = {zone.value: 0 for zone in DeviceZone}
            logger.warning("Emergency stop executed")
            return True

        except Exception as e:
            logger.error(f"Emergency stop failed: {e}")
            return False

    def get_recent_logs(self, max_count: int = 10) -> List[str]:
        """Get recent log messages from Arduino.

        Args:
            max_count: Maximum number of logs to return.

        Returns:
            List of recent log messages.
        """
        logs = []
        while not self._log_queue.empty() and len(logs) < max_count:
            try:
                logs.append(self._log_queue.get_nowait())
            except Empty:
                break
        return logs

    def get_sensor_data(self) -> Optional[SensorData]:
        """Get latest sensor data from Arduino.

        Returns:
            Latest sensor data or None if no data available.
        """
        latest_data = None
        while not self._sensor_data_queue.empty():
            try:
                latest_data = self._sensor_data_queue.get_nowait()
            except Empty:
                break
        return latest_data

    def has_sensor_data(self) -> bool:
        """Check if there is sensor data available.

        Returns:
            True if sensor data is available.
        """
        return not self._sensor_data_queue.empty()
