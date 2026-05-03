from __future__ import annotations

from enum import auto, Enum

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import DataTable, Static

from ..ros import RosClient


class _Filter(Enum):
    ALL = auto()
    SUB = auto()
    PUB = auto()

    def next(self) -> "_Filter":
        order = [_Filter.ALL, _Filter.SUB, _Filter.PUB]
        return order[(order.index(self) + 1) % len(order)]

    def label(self) -> str:
        return {_Filter.ALL: "All", _Filter.SUB: "Sub only", _Filter.PUB: "Pub only"}[self]


_MAX_MONITORS = 20


class NodeHzPanel(Widget):
    """Shows real-time Hz for all pub/sub topics of a selected node."""

    BINDINGS = [
        Binding("f", "cycle_filter", "Filter", show=True),
    ]

    DEFAULT_CSS = """
    NodeHzPanel {
        layout: vertical;
    }
    NodeHzPanel > #hz-status {
        height: 1;
        padding: 0 2;
        background: $panel-darken-1;
    }
    NodeHzPanel > DataTable {
        height: 1fr;
    }
    """

    _ros: RosClient
    _node_name: str | None = None
    # (direction, topic, type_) for ALL directions — filter applied on render
    _all_rows: list[tuple[str, str, str]]
    _filter: _Filter

    def __init__(self, ros: RosClient, *, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(id=id, classes=classes)
        self._ros = ros
        self._all_rows = []
        self._filter = _Filter.SUB  # default: sub-only (most common use-case)

    def compose(self) -> ComposeResult:
        yield Static(" Hz Overview", id="hz-status")
        table: DataTable = DataTable(id="hz-table")
        table.add_columns("Dir", "Topic", "Type", "Hz")
        table.cursor_type = "row"
        yield table

    def on_mount(self) -> None:
        self.set_interval(1.0, self._refresh_hz)

    def set_node(self, node_name: str) -> None:
        self._stop_all_monitors()
        self._node_name = node_name
        self._all_rows = []
        self._build_rows()
        self._start_monitors()
        self._redraw()

    def stop(self) -> None:
        """Call when this panel is hidden to release monitors."""
        self._stop_all_monitors()

    # ------------------------------------------------------------------ #

    def _build_rows(self) -> None:
        if self._node_name is None:
            return
        try:
            info = self._ros.get_node_info(self._node_name)
        except Exception:
            return

        rows: list[tuple[str, str, str]] = []
        for topic, type_ in info.publishers:
            rows.append(("Pub", topic, type_ or ""))
        for topic, type_ in info.subscribers:
            rows.append(("Sub", topic, type_ or ""))
        self._all_rows = rows

    def _start_monitors(self) -> None:
        started = 0
        for _dir, topic, _type in self._all_rows:
            if started >= _MAX_MONITORS:
                break
            if self._ros.start_topic_monitor(topic):
                started += 1

    def _stop_all_monitors(self) -> None:
        for _dir, topic, _type in self._all_rows:
            self._ros.stop_topic_monitor(topic)

    def _visible_rows(self) -> list[tuple[str, str, str]]:
        if self._filter == _Filter.ALL:
            return self._all_rows
        target = "Sub" if self._filter == _Filter.SUB else "Pub"
        return [r for r in self._all_rows if r[0] == target]

    def _refresh_hz(self) -> None:
        if self._node_name is None:
            return
        try:
            table = self.query_one("#hz-table", DataTable)
            status = self.query_one("#hz-status", Static)
        except Exception:
            return

        visible = self._visible_rows()
        # Update Hz column in-place (avoid full clear to reduce flicker)
        if table.row_count != len(visible):
            self._redraw()
            return

        for i, (_dir, topic, _type) in enumerate(visible):
            hz = self._ros.get_topic_hz(topic)
            hz_str = f"{hz:.1f}" if hz is not None else "--"
            table.update_cell_at((i, 3), hz_str)

        count = len(visible)
        status.update(
            f" Hz Overview  [{self._filter.label()}]  f: filter  ({count} topics)"
        )

    def _redraw(self) -> None:
        try:
            table = self.query_one("#hz-table", DataTable)
            status = self.query_one("#hz-status", Static)
        except Exception:
            return

        table.clear()
        visible = self._visible_rows()
        for dir_, topic, type_ in visible:
            hz = self._ros.get_topic_hz(topic)
            hz_str = f"{hz:.1f}" if hz is not None else "--"
            table.add_row(dir_, topic, type_, hz_str)

        count = len(visible)
        label = self._filter.label()
        status.update(f" Hz Overview  [{label}]  f: filter  ({count} topics)")

    def action_cycle_filter(self) -> None:
        self._filter = self._filter.next()
        self._redraw()
