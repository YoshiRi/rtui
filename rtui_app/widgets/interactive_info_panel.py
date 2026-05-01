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
