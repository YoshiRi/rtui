from textual.widgets import Input


class SearchInput(Input):
    """Input that is excluded from the Tab focus cycle.

    allow_focus() controls focus_chain (Tab).
    can_focus controls set_focus (programmatic .focus()).
    These are independent, so setting allow_focus()=False keeps
    Ctrl+F-driven programmatic focus working while hiding from Tab.
    """

    def allow_focus(self) -> bool:
        return False
