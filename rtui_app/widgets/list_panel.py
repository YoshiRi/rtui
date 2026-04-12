from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Input, Static, Tree

from ..event import RosEntitySelected
from ..ros import RosClient, RosEntityType
from ..ros.entity import TreeKey


class RosEntityListPanel(Static):
    DEFAULT_CSS = """
    RosEntityListPanel {
        layout: vertical;
    }
    RosEntityListPanel > Input {
        height: 3;
    }
    RosEntityListPanel > Tree {
        height: 1fr;
    }
    """

    _ros: RosClient
    _entity_type: RosEntityType
    _tree: Tree[str]
    _all_entities: list[TreeKey]

    def __init__(
        self,
        ros: RosClient,
        entity_type: RosEntityType,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )

        self._ros = ros
        self._entity_type = entity_type
        self._tree = Tree(entity_type.name)
        self._tree.auto_expand = True
        self._all_entities = []
        self.update_items()

    def _render_tree(self) -> None:
        self._tree.clear()

        filter_text = ""
        try:
            filter_text = self.query_one("#search-input", Input).value.strip().lower()
        except Exception:
            pass

        if filter_text:
            entities = [e for e in self._all_entities if filter_text in e.full_name.lower()]
        else:
            entities = self._all_entities

        groups = {e.group for e in entities if e.group is not None}
        parents = {None: self._tree.root}

        for group in sorted(groups):
            parents[group] = self._tree.root.add(group)

        for entity in entities:
            parents[entity.group].add_leaf(entity.name, entity.full_name)

    def update_items(self) -> None:
        self._all_entities = self._ros.list_entities(self._entity_type)
        self._render_tree()

    def focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search... (Enter: tree, Esc: clear)", id="search-input")
        yield self._tree

    def on_input_changed(self, event: Input.Changed) -> None:
        self._render_tree()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._tree.focus()

    def on_key(self, event) -> None:
        if event.key == "escape":
            try:
                search_input = self.query_one("#search-input", Input)
                if search_input.has_focus:
                    search_input.clear()
                    self._tree.focus()
                    event.prevent_default()
                    event.stop()
            except Exception:
                pass

    def on_tree_node_selected(self, e: Tree.NodeSelected[str]) -> None:
        if e.node.is_root or e.node.data is None:
            return
        self.post_message(RosEntitySelected(self._entity_type, e.node.data))
