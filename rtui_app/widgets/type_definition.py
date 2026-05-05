from __future__ import annotations

import re

from rich.markup import escape as rich_escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import Input, Static

from ..ros import RosClient, RosEntity


class RosTypeDefinitionPanel(Widget):
    BINDINGS = [
        Binding("ctrl+f",  "focus_search", "Search", show=True),
        Binding("escape",  "clear_search", "Clear",  show=True),
    ]

    DEFAULT_CSS = """
    RosTypeDefinitionPanel {
        layout: vertical;
    }
    RosTypeDefinitionPanel > Input {
        height: 3;
    }
    RosTypeDefinitionPanel > #typedef-status {
        height: 1;
        padding: 0 2;
        background: $panel-darken-1;
        display: none;
    }
    RosTypeDefinitionPanel > #typedef-content {
        padding: 1 2;
    }
    """

    _ros: RosClient
    _entity: RosEntity | None = None
    _raw_text: str = ""
    _search_text: str = ""

    def __init__(
        self,
        ros: RosClient,
        entity: RosEntity | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._ros = ros
        self._entity = entity

    def compose(self) -> ComposeResult:
        yield Input(
            placeholder="Search... (Enter: highlight, Esc: clear)",
            id="typedef-search",
        )
        yield Static("", id="typedef-status")
        yield Static("", id="typedef-content")

    def on_mount(self) -> None:
        self.update_content()

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #

    def action_focus_search(self) -> None:
        try:
            self.query_one("#typedef-search", Input).focus()
        except Exception:
            pass

    def action_clear_search(self) -> None:
        try:
            search = self.query_one("#typedef-search", Input)
            if search.has_focus:
                search.clear()
                self._search_text = ""
                self._redraw()
                if self.parent:
                    self.parent.focus()
        except Exception:
            pass

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action == "clear_search":
            try:
                return self.query_one("#typedef-search", Input).has_focus
            except Exception:
                return False
        return None

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "typedef-search":
            return
        self._search_text = event.value.strip().lower()
        self._redraw()
        if self.parent:
            self.parent.focus()

    # ------------------------------------------------------------------ #
    # Content
    # ------------------------------------------------------------------ #

    def set_entity(self, entity: RosEntity) -> None:
        if entity != self._entity:
            self._entity = entity
            self._search_text = ""
            self._raw_text = ""
            try:
                self.query_one("#typedef-search", Input).clear()
            except Exception:
                pass
            self.update_content()

    def update_content(self) -> None:
        if self._entity is None or not self._entity.type.has_definition():
            self._raw_text = ""
        else:
            self._raw_text = self._ros.get_type_definition(self._entity)
        self._redraw()

    def _redraw(self) -> None:
        try:
            content = self.query_one("#typedef-content", Static)
            status = self.query_one("#typedef-status", Static)
        except Exception:
            return

        if not self._raw_text:
            content.update("")
            status.display = False
            return

        if not self._search_text:
            content.update(rich_escape(self._raw_text))
            status.display = False
            return

        # Split on search term (case-insensitive), escape non-match parts
        parts = re.split(f"({re.escape(self._search_text)})", self._raw_text, flags=re.IGNORECASE)
        result: list[str] = []
        match_count = 0
        for i, part in enumerate(parts):
            if i % 2 == 1:
                result.append(f"[on yellow]{part}[/on yellow]")
                match_count += 1
            else:
                result.append(rich_escape(part))
        content.update("".join(result))

        status.update(f' Search: "{self._search_text}"  ({match_count} matches)')
        status.display = True
