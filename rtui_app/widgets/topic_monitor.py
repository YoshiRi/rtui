from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import RichLog, Static

from ..ros import RosClient


class TopicMonitorPanel(Widget):
    """Shows real-time Hz and optional message echo for a selected topic."""

    DEFAULT_CSS = """
    TopicMonitorPanel {
        layout: vertical;
    }
    TopicMonitorPanel > #hz-bar {
        height: 1;
        padding: 0 2;
        background: $panel-darken-1;
    }
    TopicMonitorPanel > RichLog {
        height: 1fr;
        padding: 0 1;
    }
    """

    _ros: RosClient
    _topic_name: str | None
    _echo_enabled: bool

    def __init__(self, ros: RosClient, *, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(id=id, classes=classes)
        self._ros = ros
        self._topic_name = None
        self._echo_enabled = False

    def compose(self) -> ComposeResult:
        yield Static("", id="hz-bar")
        yield RichLog(id="echo-log", markup=False, highlight=False, wrap=True)

    def on_mount(self) -> None:
        self.set_interval(1.0, self._refresh_hz)
        self.set_interval(0.5, self._refresh_echo)
        self._redraw_status_bar()

    def set_topic(self, topic_name: str) -> None:
        if self._topic_name and self._topic_name != topic_name:
            self._ros.stop_topic_monitor(self._topic_name)
        self._topic_name = topic_name
        self._ros.start_topic_monitor(topic_name)
        try:
            self.query_one("#echo-log", RichLog).clear()
        except Exception:
            pass
        self._redraw_status_bar()

    def toggle_echo(self) -> None:
        self._echo_enabled = not self._echo_enabled
        if not self._echo_enabled:
            try:
                self.query_one("#echo-log", RichLog).clear()
            except Exception:
                pass
        self._redraw_status_bar()

    @property
    def echo_enabled(self) -> bool:
        return self._echo_enabled

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _redraw_status_bar(self, hz_str: str | None = None) -> None:
        if hz_str is None:
            hz = self._ros.get_topic_hz(self._topic_name) if self._topic_name else None
            hz_str = f"{hz:.2f} Hz" if hz is not None else "--- Hz"
        echo_status = "ON  (press e to stop)" if self._echo_enabled else "OFF (press e to start)"
        try:
            self.query_one("#hz-bar", Static).update(
                f" Hz: {hz_str}   Echo: {echo_status}"
            )
        except Exception:
            pass

    def _refresh_hz(self) -> None:
        if self._topic_name:
            self._redraw_status_bar()

    def _refresh_echo(self) -> None:
        if not self._echo_enabled or not self._topic_name:
            return
        messages = self._ros.get_topic_echo(self._topic_name)
        if not messages:
            return
        try:
            log = self.query_one("#echo-log", RichLog)
            log.clear()
            for msg in messages:
                log.write("─" * 60)
                log.write(msg.strip())
        except Exception:
            pass
