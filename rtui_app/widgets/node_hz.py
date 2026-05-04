from __future__ import annotations

from enum import auto, Enum

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import DataTable, Input, Static

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
        Binding("ctrl+f", "focus_search", show=False),
        Binding("f", "cycle_filter", "Filter", show=True),
    ]

    DEFAULT_CSS = """
    NodeHzPanel {
        layout: vertical;
    }
    NodeHzPanel > Input {
        height: 3;
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
    _all_rows: list[tuple[str, str, str]]
    _filter: _Filter
    _search_text: str = ""

    def __init__(self, ros: RosClient, *, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(id=id, classes=classes)
        self._ros = ros
        self._all_rows = []
        self._filter = _Filter.SUB

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search topics... (Enter: apply, Esc: clear)", id="hz-search")
        yield Static(" Hz Overview", id="hz-status")
        table: DataTable = DataTable(id="hz-table")
        table.add_columns("Dir", "Topic", "Type", "Hz")
        table.cursor_type = "row"
        yield table

    def on_mount(self) -> None:
        self.set_interval(1.0, self._refresh_hz)

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #

    def action_focus_search(self) -> None:
        try:
            self.query_one("#hz-search", Input).focus()
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "hz-search":
            return
        self._search_text = event.value.strip().lower()
        self._redraw()
        try:
            self.query_one("#hz-table", DataTable).focus()
        except Exception:
            pass

    def on_key(self, event) -> None:
        try:
            search = self.query_one("#hz-search", Input)
        except Exception:
            return
        if search.has_focus and event.key == "escape":
            search.clear()
            self._search_text = ""
            self._redraw()
            try:
                self.query_one("#hz-table", DataTable).focus()
            except Exception:
                pass
            event.prevent_default()
            event.stop()

    # ------------------------------------------------------------------ #
    # Node / monitor management
    # ------------------------------------------------------------------ #

    def set_node(self, node_name: str) -> None:
        self._stop_all_monitors()
        self._node_name = node_name
        self._all_rows = []
        self._search_text = ""
        try:
            self.query_one("#hz-search", Input).clear()
        except Exception:
            pass
        self._build_rows()
        self._start_monitors()
        self._redraw()

    def stop(self) -> None:
        self._stop_all_monitors()

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

    # ------------------------------------------------------------------ #
    # Filtering: Dir filter AND search text (AND combination)
    # ------------------------------------------------------------------ #

    def _visible_rows(self) -> list[tuple[str, str, str]]:
        rows = self._all_rows
        if self._filter != _Filter.ALL:
            target = "Sub" if self._filter == _Filter.SUB else "Pub"
            rows = [r for r in rows if r[0] == target]
        if self._search_text:
            rows = [r for r in rows if self._search_text in r[1].lower()]
        return rows

    def _status_text(self, count: int) -> str:
        parts = [f"[{self._filter.label()}]"]
        if self._search_text:
            parts.append(f'"{self._search_text}"')
        parts.append(f"({count} topics)")
        return f" Hz Overview  {'  '.join(parts)}  f: filter"

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #

    def _refresh_hz(self) -> None:
        if self._node_name is None:
            return
        try:
            table = self.query_one("#hz-table", DataTable)
            status = self.query_one("#hz-status", Static)
        except Exception:
            return

        visible = self._visible_rows()
        if table.row_count != len(visible):
            self._redraw()
            return

        for i, (_dir, topic, _type) in enumerate(visible):
            hz = self._ros.get_topic_hz(topic)
            table.update_cell_at((i, 3), f"{hz:.1f}" if hz is not None else "--")

        status.update(self._status_text(len(visible)))

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
            table.add_row(dir_, topic, type_, f"{hz:.1f}" if hz is not None else "--")

        status.update(self._status_text(len(visible)))

    def action_cycle_filter(self) -> None:
        self._filter = self._filter.next()
        self._redraw()
