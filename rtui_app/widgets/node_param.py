from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Static


from ..ros import RosClient


class NodeParamPanel(Widget):
    """Shows ROS2 parameters for a selected node in a DataTable."""

    DEFAULT_CSS = """
    NodeParamPanel {
        layout: vertical;
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

    def __init__(self, ros: RosClient, *, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(id=id, classes=classes)
        self._ros = ros
        self._node_name = None

    def compose(self) -> ComposeResult:
        yield Static(" Parameters", id="param-status")
        table: DataTable = DataTable(id="param-table")
        table.add_columns("Parameter", "Value")
        table.cursor_type = "row"
        yield table

    def set_node(self, node_name: str) -> None:
        self._node_name = node_name
        self.refresh_params()

    def refresh_params(self) -> None:
        if self._node_name is None:
            return

        try:
            status = self.query_one("#param-status", Static)
            table = self.query_one("#param-table", DataTable)
        except Exception:
            return

        status.update(f" Parameters  (loading...)")
        table.clear()

        params = self._ros.get_node_params(self._node_name)

        if params is None:
            status.update(" Parameters  [dim](not available)[/dim]")
            return

        if not params:
            status.update(" Parameters  [dim](none)[/dim]")
            return

        for name, value in params.items():
            table.add_row(name, value)

        status.update(f" Parameters  ({len(params)} entries)  r: reload  x: export")
