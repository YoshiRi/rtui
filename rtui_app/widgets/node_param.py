from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import DataTable, Input, Static

from ._search_input import SearchInput

from ..ros import RosClient


class NodeParamPanel(Widget):
    """Shows ROS2 parameters for a selected node in a DataTable."""

    BINDINGS = [
        Binding("ctrl+f",  "focus_search", "Search", show=True),
        Binding("escape",  "clear_search", "Clear",  show=True),
    ]

    DEFAULT_CSS = """
    NodeParamPanel {
        layout: vertical;
    }
    NodeParamPanel > SearchInput {
        height: 3;
    }
    NodeParamPanel > #param-status {
        height: 1;
        padding: 0 2;
        background: $panel-darken-1;
    }
    NodeParamPanel > DataTable {
        height: 1fr;
    }
    """

    _ros: RosClient
    _node_name: str | None
    _search_text: str = ""
    _all_params: dict[str, str]

    def __init__(self, ros: RosClient, *, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(id=id, classes=classes)
        self._ros = ros
        self._node_name = None
        self._all_params = {}

    def compose(self) -> ComposeResult:
        yield SearchInput(placeholder="Search params... (Enter: apply, Esc: clear)", id="param-search")
        yield Static(" Parameters", id="param-status")
        table: DataTable = DataTable(id="param-table")
        table.add_columns("Parameter", "Value")
        table.cursor_type = "row"
        yield table

    def action_focus_search(self) -> None:
        try:
            self.query_one("#param-search", Input).focus()
        except Exception:
            pass

    def action_clear_search(self) -> None:
        try:
            search = self.query_one("#param-search", Input)
            if search.has_focus:
                search.clear()
                self._search_text = ""
                self._redraw()
                self.query_one("#param-table", DataTable).focus()
        except Exception:
            pass

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action == "clear_search":
            try:
                return self.query_one("#param-search", Input).has_focus
            except Exception:
                return False
        return None

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "param-search":
            return
        self._search_text = event.value.strip().lower()
        self._redraw()
        try:
            self.query_one("#param-table", DataTable).focus()
        except Exception:
            pass

    def set_node(self, node_name: str) -> None:
        self._node_name = node_name
        self._search_text = ""
        self._all_params = {}
        try:
            self.query_one("#param-search", Input).clear()
        except Exception:
            pass
        self.refresh_params()

    def refresh_params(self) -> None:
        if self._node_name is None:
            return

        try:
            status = self.query_one("#param-status", Static)
        except Exception:
            return

        status.update(" Parameters  (loading...)")

        params = self._ros.get_node_params(self._node_name)

        if params is None:
            self._all_params = {}
            try:
                self.query_one("#param-table", DataTable).clear()
            except Exception:
                pass
            status.update(" Parameters  [dim](not available)[/dim]")
            return

        self._all_params = params
        self._redraw()

    def _redraw(self) -> None:
        try:
            status = self.query_one("#param-status", Static)
            table = self.query_one("#param-table", DataTable)
        except Exception:
            return

        if not self._all_params:
            status.update(" Parameters  [dim](none)[/dim]")
            return

        if self._search_text:
            visible = {
                k: v for k, v in self._all_params.items()
                if self._search_text in k.lower() or self._search_text in v.lower()
            }
        else:
            visible = self._all_params

        table.clear()
        for name, value in visible.items():
            table.add_row(name, value)

        count = len(visible)
        total = len(self._all_params)
        filter_info = f' "{self._search_text}"' if self._search_text else ""
        count_info = f"({count}/{total})" if self._search_text else f"({count} entries)"
        status.update(f" Parameters{filter_info}  {count_info}  r: reload  x: export")
