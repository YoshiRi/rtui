from __future__ import annotations

import datetime
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, RichLog, Tree

from .ros import RosClient, RosEntity, RosEntityType
from .widgets import (
    NodeParamPanel,
    RosEntityInteractivePanel,
    RosEntityListPanel,
    RosTypeDefinitionPanel,
    TopicMonitorPanel,
)


class RosEntityInspection(Screen):
    _entity_type: RosEntityType
    _entity_name: str | None
    _list_panel: RosEntityListPanel
    _info_panel: RosEntityInteractivePanel
    _definition_panel: RosTypeDefinitionPanel | None = None
    _monitor_panel: TopicMonitorPanel | None = None
    _param_panel: NodeParamPanel | None = None

    BINDINGS = [
        Binding("ctrl+f",    "focus_search",  "Search",   show=True),
        Binding("ctrl+left", "focus_left",    "◀ List",   show=True),
        Binding("ctrl+right","focus_info",    "Info ▶",   show=True),
        Binding("ctrl+down", "focus_bottom",  "▼ Detail", show=False),
        Binding("ctrl+up",   "focus_info",    "▲ Info",   show=False),
        Binding("e",         "toggle_echo",   "Echo",     show=False),
        Binding("x",         "export",        "Export",   show=True),
    ]

    DEFAULT_CSS = """
    .container {
        height: 100%;
        background: $panel;
    }

    RosEntityListPanel {
        padding-left: 2;
        width: 30%;
    }

    #main {
        border-left: inner $primary;
    }

    /* height classes */
    .main-upper {
        height: 40%;
        border-bottom: inner $primary;
    }
    .main-lower {
        height: 60%;
    }
    .main-half {
        height: 50%;
    }
    .main-half-top {
        height: 50%;
        border-bottom: inner $primary;
    }

    /* focus highlight: active panel gets an accent border */
    RosEntityListPanel:focus-within {
        border-right: outer $accent;
    }
    #info-scroll:focus-within {
        border: outer $accent;
    }
    #bottom-scroll:focus-within {
        border: outer $accent;
    }
    TopicMonitorPanel:focus-within {
        border: outer $accent;
    }
    """

    def __init__(self, ros: RosClient, entity_type: RosEntityType) -> None:
        super().__init__()
        self._entity_type = entity_type
        self._entity_name = None
        self._list_panel = RosEntityListPanel(ros, entity_type)
        self._info_panel = RosEntityInteractivePanel(ros)

        if entity_type == RosEntityType.Topic:
            self._monitor_panel = TopicMonitorPanel(ros)
        elif entity_type == RosEntityType.Node:
            self._param_panel = NodeParamPanel(ros)
        elif entity_type.has_definition():
            self._definition_panel = RosTypeDefinitionPanel(ros)

    def set_entity_name(self, name: str) -> None:
        self._entity_name = name
        entity = RosEntity(type=self._entity_type, name=name)
        self._info_panel.set_entity(entity)

        if self._monitor_panel is not None:
            self._monitor_panel.set_topic(name)
        if self._param_panel is not None:
            self._param_panel.set_node(name)
        if self._definition_panel is not None:
            self._definition_panel.set_entity(entity)

    def force_update(self) -> None:
        self._list_panel.update_items()
        if self._param_panel is not None and self._entity_name is not None:
            self._param_panel.refresh_params()

    # ------------------------------------------------------------------ #
    # Panel focus actions
    # ------------------------------------------------------------------ #

    def action_focus_left(self) -> None:
        """Focus the entity list tree (left panel)."""
        try:
            self._list_panel.query_one(Tree).focus()
        except Exception:
            pass

    def action_focus_info(self) -> None:
        """Focus the info panel (right top)."""
        try:
            self._info_panel.focus()
        except Exception:
            pass

    def action_focus_bottom(self) -> None:
        """Focus the bottom panel (Hz/Echo, params, or type definition)."""
        try:
            if self._monitor_panel is not None:
                self._monitor_panel.query_one(RichLog).focus()
            elif self._param_panel is not None:
                self._param_panel.query_one(DataTable).focus()
            elif self._definition_panel is not None:
                self.query_one("#bottom-scroll").focus()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Other actions
    # ------------------------------------------------------------------ #

    def action_focus_search(self) -> None:
        self._list_panel.focus_search()

    def action_toggle_echo(self) -> None:
        if self._monitor_panel is not None:
            self._monitor_panel.toggle_echo()

    def action_export(self) -> None:
        if self._entity_name is None:
            self.notify("Nothing to export (select an entity first)", severity="warning")
            return
        self._do_export()

    def _do_export(self) -> None:
        import yaml

        entity = RosEntity(type=self._entity_type, name=self._entity_name)  # type: ignore[arg-type]
        data: dict = {
            "entity_type": self._entity_type.name,
            "name": self._entity_name,
        }

        try:
            info = self._info_panel._ros.get_entity_info(entity)
            data["info"] = info.__dict__
        except Exception as e:
            data["info_error"] = str(e)

        if self._monitor_panel is not None:
            hz = self._info_panel._ros.get_topic_hz(self._entity_name)  # type: ignore[arg-type]
            data["hz"] = round(hz, 3) if hz is not None else None
            if self._monitor_panel.echo_enabled:
                data["recent_messages"] = self._info_panel._ros.get_topic_echo(self._entity_name)  # type: ignore[arg-type]

        if self._param_panel is not None:
            params = self._info_panel._ros.get_node_params(self._entity_name)  # type: ignore[arg-type]
            data["parameters"] = params

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = (self._entity_name or "unknown").replace("/", "_").strip("_")
        filename = Path.cwd() / f"rtui_export_{safe_name}_{timestamp}.yaml"

        try:
            filename.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False))
            self.notify(f"Exported to {filename.name}", severity="information")
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #

    def compose(self) -> ComposeResult:
        yield Footer()
        with Horizontal(classes="container"):
            yield self._list_panel
            with Vertical(id="main"):
                if self._monitor_panel is not None:
                    # Topic: info (40%) + Hz/Echo monitor (60%)
                    with ScrollableContainer(id="info-scroll", classes="main-upper"):
                        yield self._info_panel
                    yield self._monitor_panel
                elif self._param_panel is not None:
                    # Node: info (40%) + param table (60%)
                    with ScrollableContainer(id="info-scroll", classes="main-upper"):
                        yield self._info_panel
                    with ScrollableContainer(id="bottom-scroll", classes="main-lower"):
                        yield self._param_panel
                elif self._definition_panel is not None:
                    # Type entities: info (50%) + type definition (50%)
                    with ScrollableContainer(id="info-scroll", classes="main-half-top"):
                        yield self._info_panel
                    with ScrollableContainer(id="bottom-scroll", classes="main-half"):
                        yield self._definition_panel
                else:
                    # Service / Action: info only
                    with ScrollableContainer(id="info-scroll"):
                        yield self._info_panel
