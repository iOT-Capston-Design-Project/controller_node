"""Console display implementation using Rich library."""

import logging
from collections import deque
from datetime import datetime
from typing import List, Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..interfaces.presentation import IDisplay
from ..domain.models import ControlSignal, DeviceCommand, SystemStatus
from ..domain.enums import ConnectionState

logger = logging.getLogger(__name__)


class ConsoleDisplay(IDisplay):
    """TUI dashboard using Rich library."""

    def __init__(self, max_log_lines: int = 10):
        """Initialize console display.

        Args:
            max_log_lines: Maximum number of log lines to display.
        """
        self._console = Console()
        self._live: Optional[Live] = None
        self._max_log_lines = max_log_lines

        # State
        self._status: Optional[SystemStatus] = None
        self._last_signal: Optional[ControlSignal] = None
        self._last_commands: List[DeviceCommand] = []
        self._log_messages: deque = deque(maxlen=max_log_lines)
        self._error_message: Optional[str] = None

    def start(self) -> None:
        """Start the display."""
        self._live = Live(
            self._generate_layout(),
            console=self._console,
            refresh_per_second=4,
            screen=True,
        )
        self._live.start()
        logger.info("Console display started")

    def stop(self) -> None:
        """Stop the display."""
        if self._live:
            self._live.stop()
            self._live = None
        logger.info("Console display stopped")

    def _refresh(self) -> None:
        """Refresh the display."""
        if self._live:
            self._live.update(self._generate_layout())

    def _generate_layout(self) -> Layout:
        """Generate the display layout."""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=self._max_log_lines + 2),
        )

        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=2),
        )

        # Header
        layout["header"].update(
            Panel(
                Text("Controller Node", style="bold white", justify="center"),
                style="blue",
            )
        )

        # Left panel - Status
        layout["left"].update(self._generate_status_panel())

        # Right panel - Signals and Commands
        layout["right"].update(self._generate_main_panel())

        # Footer - Logs
        layout["footer"].update(self._generate_log_panel())

        return layout

    def _generate_status_panel(self) -> Panel:
        """Generate status panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Key", style="cyan")
        table.add_column("Value")

        if self._status:
            # Device ID
            table.add_row("Device ID", str(self._status.device_id))

            # Master connection
            master_style = (
                "green" if self._status.master_connection == ConnectionState.CONNECTED
                else "red"
            )
            table.add_row(
                "Master Node",
                Text(self._status.master_connection.name, style=master_style),
            )

            # Serial connection
            serial_style = (
                "green" if self._status.serial_connection == ConnectionState.CONNECTED
                else "yellow"
            )
            table.add_row(
                "Serial Device",
                Text(self._status.serial_connection.name, style=serial_style),
            )

            table.add_row("", "")

            # Statistics
            table.add_row("Commands Executed", str(self._status.commands_executed))
            table.add_row("Errors", str(self._status.errors_count))

            # Last signal time
            if self._status.last_signal_received:
                time_str = self._status.last_signal_received.strftime("%H:%M:%S")
                table.add_row("Last Signal", time_str)

        else:
            table.add_row("Status", "Initializing...")

        return Panel(table, title="Status", border_style="blue")

    def _generate_main_panel(self) -> Panel:
        """Generate main panel with signal and command info."""
        layout = Layout()
        layout.split_column(
            Layout(name="signal", ratio=1),
            Layout(name="commands", ratio=2),
        )

        # Signal info
        signal_table = Table(show_header=True, box=None, padding=(0, 1))
        signal_table.add_column("Field", style="cyan")
        signal_table.add_column("Value")

        if self._last_signal:
            signal_table.add_row(
                "Target Zones",
                ", ".join(map(str, self._last_signal.target_zones)) or "None",
            )
            action_style = (
                "green" if self._last_signal.action.value == "inflate"
                else "yellow" if self._last_signal.action.value == "deflate"
                else "dim"
            )
            signal_table.add_row(
                "Action",
                Text(self._last_signal.action.value, style=action_style),
            )
            signal_table.add_row("Intensity", f"{self._last_signal.intensity}%")
        else:
            signal_table.add_row("", "Waiting for signal...")

        layout["signal"].update(
            Panel(signal_table, title="Last Signal", border_style="cyan")
        )

        # Commands info
        cmd_table = Table(show_header=True, box=None, padding=(0, 1))
        cmd_table.add_column("Zone", style="cyan", width=8)
        cmd_table.add_column("Action", width=10)
        cmd_table.add_column("Intensity", width=10)
        cmd_table.add_column("Time", width=10)

        if self._last_commands:
            for cmd in self._last_commands[-5:]:  # Show last 5 commands
                action_style = (
                    "green" if cmd.action.value == "inflate"
                    else "yellow" if cmd.action.value == "deflate"
                    else "dim"
                )
                cmd_table.add_row(
                    str(cmd.zone.value),
                    Text(cmd.action.value, style=action_style),
                    f"{cmd.intensity}%",
                    cmd.timestamp.strftime("%H:%M:%S"),
                )
        else:
            cmd_table.add_row("", "No commands yet", "", "")

        layout["commands"].update(
            Panel(cmd_table, title="Recent Commands", border_style="green")
        )

        return Panel(layout, title="Control", border_style="blue")

    def _generate_log_panel(self) -> Panel:
        """Generate log panel."""
        log_text = Text()

        for timestamp, level, message in self._log_messages:
            time_str = timestamp.strftime("%H:%M:%S")
            level_style = {
                "info": "blue",
                "warning": "yellow",
                "error": "red",
            }.get(level, "white")

            log_text.append(f"[{time_str}] ", style="dim")
            log_text.append(f"[{level.upper()}] ", style=level_style)
            log_text.append(f"{message}\n")

        if self._error_message:
            log_text.append(f"\nERROR: {self._error_message}", style="bold red")

        return Panel(log_text, title="Logs", border_style="dim")

    def update_status(self, status: SystemStatus) -> None:
        """Update system status display.

        Args:
            status: Current system status.
        """
        self._status = status
        self._refresh()

    def show_signal_received(self, signal: ControlSignal) -> None:
        """Display received control signal.

        Args:
            signal: The received control signal.
        """
        self._last_signal = signal
        self._add_log(
            f"Signal received: zones={signal.target_zones}, "
            f"action={signal.action.value}, intensity={signal.intensity}%",
            "info",
        )
        self._refresh()

    def show_commands_executed(self, commands: List[DeviceCommand]) -> None:
        """Display executed device commands.

        Args:
            commands: List of executed commands.
        """
        self._last_commands = commands
        self._add_log(f"Executed {len(commands)} command(s)", "info")
        self._refresh()

    def log_message(self, message: str, level: str = "info") -> None:
        """Log a message to display.

        Args:
            message: Message to display.
            level: Log level (info, warning, error).
        """
        self._add_log(message, level)
        self._refresh()

    def show_error(self, error: str) -> None:
        """Display an error message.

        Args:
            error: Error message to display.
        """
        self._error_message = error
        self._add_log(error, "error")
        self._refresh()

    def _add_log(self, message: str, level: str) -> None:
        """Add log message to buffer.

        Args:
            message: Log message.
            level: Log level.
        """
        self._log_messages.append((datetime.now(), level, message))
