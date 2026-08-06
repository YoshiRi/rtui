from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import Input, Static

from ._search_input import SearchInput

from ..event import RosEntitySelected
from ..ros import RosClient, RosEntity
from ..ros.entity import InfoLink
from ..ros.exception import RosMasterException

_HELP = "[dim]↑↓: navigate  Enter: jump[/dim]"


class _InfoContent(Static):
    """Focusable content area inside RosEntityInteractivePanel."""
    can_focus = True


class RosEntityInteractivePanel(Widget):
    """Keyboard-navigable info panel with per-panel Ctrl+F search."""

    BINDINGS = [
        Binding("ctrl+f",  "focus_search", "Search", show=True),
        Binding("escape",  "clear_search", "Clear",  show=True),
    ]

    DEFAULT_CSS = """
    RosEntityInteractivePanel {
        layout: vertical;
        height: auto;
    }
    RosEntityInteractivePanel > SearchInput {
        height: 3;
    }
    RosEntityInteractivePanel > #info-content {
        height: auto;
        padding: 1 2;
    }
    """

    _ros: RosClient
    _entity: RosEntity | None = None
    _links: list[InfoLink]
    _filtered: list[InfoLink]
    _cursor: int = 0
    _filter_text: str = ""

    def __init__(
        self,
        ros: RosClient,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._ros = ros
        self._links = []
        self._filtered = []

    def compose(self) -> ComposeResult:
        yield SearchInput(
            placeholder="Search links... (Enter: apply, Esc: clear)",
            id="info-search",
        )
        yield _InfoContent("", id="info-content")

    def on_mount(self) -> None:
        self.set_interval(5.0, self._refresh)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def set_entity(self, entity: RosEntity) -> None:
        self._entity = entity
        self._cursor = 0
        self._filter_text = ""
        try:
            self.query_one("#info-search", Input).clear()
        except Exception:
            pass
        self._refresh()

    def focus_content(self) -> None:
        try:
            self.query_one("#info-content", _InfoContent).focus()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Actions and key handling
    # ------------------------------------------------------------------ #

    def action_focus_search(self) -> None:
        try:
            self.query_one("#info-search", Input).focus()
        except Exception:
            pass

    def action_clear_search(self) -> None:
        try:
            search = self.query_one("#info-search", Input)
            if search.has_focus:
                search.clear()
                self._set_filter("")
                self._render()
                self.focus_content()
        except Exception:
            pass

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action == "clear_search":
            try:
                return self.query_one("#info-search", Input).has_focus
            except Exception:
                return False
        return None

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "info-search":
            return
        self._set_filter(event.value.strip().lower())
        self._render()
        self.focus_content()

    def on_key(self, event) -> None:
        try:
            content = self.query_one("#info-content", _InfoContent)
        except Exception:
            return

        if content.has_focus:
            if event.key == "up":
                self._move(-1)
                event.stop()
            elif event.key == "down":
                self._move(1)
                event.stop()
            elif event.key == "enter":
                self._select()
                event.stop()

    # ------------------------------------------------------------------ #
    # Data and filtering
    # ------------------------------------------------------------------ #

    def _refresh(self) -> None:
        if self._entity is None:
            self._links = []
            self._reapply_filter()
            self._render()
            return

        try:
            info = self._ros.get_entity_info(self._entity)
            self._links = info.to_link_list()
        except RosMasterException:
            try:
                self.query_one("#info-content", _InfoContent).update(
                    "[b][red]Fail to communicate to master[/][/]"
                )
            except Exception:
                pass
            return
        except Exception as e:
            try:
                self.query_one("#info-content", _InfoContent).update(
                    f"[b][red]Error: {e}[/][/]"
                )
            except Exception:
                pass
            return

        self._reapply_filter()
        self._render()

    def _set_filter(self, text: str) -> None:
        """Set new filter and reset cursor."""
        self._filter_text = text
        self._reapply_filter()
        self._cursor = 0

    def _reapply_filter(self) -> None:
        """Reapply current filter, preserving cursor position (clamped)."""
        if not self._filter_text:
            self._filtered = self._links[:]
        else:
            self._filtered = [
                l for l in self._links if self._filter_text in l.label.lower()
            ]
        if self._cursor >= len(self._filtered):
            self._cursor = max(0, len(self._filtered) - 1)

    # ------------------------------------------------------------------ #
    # Rendering and scrolling
    # ------------------------------------------------------------------ #

    def _render(self) -> None:
        try:
            content = self.query_one("#info-content", _InfoContent)
        except Exception:
            return

        if not self._filtered:
            if self._filter_text:
                msg = f"[dim](no matches for '{self._filter_text}')[/dim]"
            else:
                msg = "[dim](no navigable links)[/dim]"
            content.update(f"{_HELP}\n\n{msg}")
            return

        lines: list[str] = [_HELP, ""]
        current_section: str | None = None
        for idx, link in enumerate(self._filtered):
            if link.section != current_section:
                if current_section is not None:
                    lines.append("")
                lines.append(f"[b]{link.section}:[/b]")
                current_section = link.section
            if idx == self._cursor:
                lines.append(f"  [reverse] > {link.label} [/reverse]")
            else:
                lines.append(f"     {link.label}")

        content.update("\n".join(lines))
        self._scroll_to_cursor()

    def _cursor_line(self) -> int:
        line = 2  # _HELP + blank line
        current_section: str | None = None
        for idx, link in enumerate(self._filtered):
            if link.section != current_section:
                if current_section is not None:
                    line += 1
                line += 1
                current_section = link.section
            if idx == self._cursor:
                return line
            line += 1
        return line

    def _scroll_to_cursor(self) -> None:
        container = self.parent
        if container is None:
            return
        try:
            cursor_line = self._cursor_line()
            # Add Input height (3 rows) since content starts below it
            absolute_line = cursor_line + 3
            visible_height = container.size.height
            if visible_height == 0:
                return
            scroll_y = int(container.scroll_y)
            if absolute_line < scroll_y:
                container.scroll_to(y=absolute_line, animate=False)
            elif absolute_line >= scroll_y + visible_height - 1:
                container.scroll_to(y=max(0, absolute_line - visible_height + 2), animate=False)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #

    def _move(self, delta: int) -> None:
        if not self._filtered:
            return
        self._cursor = (self._cursor + delta) % len(self._filtered)
        self._render()

    def _select(self) -> None:
        if not self._filtered or self._cursor >= len(self._filtered):
            return
        entity = self._filtered[self._cursor].entity
        self.post_message(RosEntitySelected(entity.type, entity.name))
