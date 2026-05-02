from __future__ import annotations

from textual.widgets import Static

from ..event import RosEntitySelected
from ..ros import RosClient, RosEntity
from ..ros.entity import InfoLink
from ..ros.exception import RosMasterException

_HELP = "[dim]↑↓: navigate  Enter: jump  i: exit[/dim]"


class RosEntityInteractivePanel(Static):
    """Keyboard-navigable version of the info panel.

    Links are displayed as a list; ↑↓ moves the cursor, Enter follows the link.
    """

    can_focus = True

    DEFAULT_CSS = """
    RosEntityInteractivePanel {
        padding: 1 2;
    }
    """

    _ros: RosClient
    _entity: RosEntity | None = None
    _links: list[InfoLink]
    _cursor: int = 0

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

    def set_entity(self, entity: RosEntity) -> None:
        self._entity = entity
        self._refresh()

    def _refresh(self) -> None:
        if self._entity is None:
            self._links = []
            self._cursor = 0
            self.update("")
            return

        try:
            info = self._ros.get_entity_info(self._entity)
            new_links = info.to_link_list()
        except RosMasterException:
            self.update("[b][red]Fail to communicate to master[/][/]")
            return
        except Exception as e:
            self.update(f"[b][red]Error: {e}[/][/]")
            return

        # Preserve cursor position when link count changes
        self._links = new_links
        if self._cursor >= len(self._links):
            self._cursor = max(0, len(self._links) - 1)

        self._render()

    def _render(self) -> None:
        if not self._links:
            entity_label = f"{self._entity.type.name}: {self._entity.name}" if self._entity else ""
            self.update(f"{entity_label}\n\n{_HELP}\n\n[dim](no navigable links)[/dim]")
            return

        lines: list[str] = []
        lines.append(_HELP)
        lines.append("")

        current_section: str | None = None
        link_idx = 0
        for link in self._links:
            if link.section != current_section:
                if current_section is not None:
                    lines.append("")
                lines.append(f"[b]{link.section}:[/b]")
                current_section = link.section

            if link_idx == self._cursor:
                lines.append(f"  [reverse] > {link.label} [/reverse]")
            else:
                lines.append(f"     {link.label}")
            link_idx += 1

        self.update("\n".join(lines))
        self._scroll_to_cursor()

    def _cursor_line(self) -> int:
        """Return the line offset (0-indexed) of the cursor item in the rendered output."""
        line = 2  # _HELP + empty line
        current_section: str | None = None
        for idx, link in enumerate(self._links):
            if link.section != current_section:
                if current_section is not None:
                    line += 1  # blank line between sections
                line += 1  # section header
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
            visible_height = container.size.height
            if visible_height == 0:
                return
            scroll_y = int(container.scroll_y)
            if cursor_line < scroll_y:
                container.scroll_to(y=cursor_line, animate=False)
            elif cursor_line >= scroll_y + visible_height - 1:
                container.scroll_to(y=cursor_line - visible_height + 2, animate=False)
        except Exception:
            pass

    def on_key(self, event) -> None:
        if event.key == "up":
            self._move(-1)
            event.stop()
        elif event.key == "down":
            self._move(1)
            event.stop()
        elif event.key == "enter":
            self._select()
            event.stop()

    def _move(self, delta: int) -> None:
        if not self._links:
            return
        self._cursor = (self._cursor + delta) % len(self._links)
        self._render()

    def _select(self) -> None:
        if not self._links or self._cursor >= len(self._links):
            return
        entity = self._links[self._cursor].entity
        self.post_message(RosEntitySelected(entity.type, entity.name))
