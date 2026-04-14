from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum, auto


class RosVersion(Enum):
    ROS1 = auto()
    ROS2 = auto()


class RosInterface(ABC):
    @abstractmethod
    def terminate(self) -> None:
        ...

    @classmethod
    @abstractmethod
    def version(cls) -> RosVersion:
        ...

    @abstractmethod
    def get_node_publishers(self, node_name: str) -> list[tuple[str, str | None]]:
        ...

    @abstractmethod
    def get_node_subscribers(self, node_name: str) -> list[tuple[str, str | None]]:
        ...

    @abstractmethod
    def get_node_service_servers(self, node_name: str) -> list[tuple[str, str | None]]:
        ...

    @abstractmethod
    def get_node_service_clients(
        self, node_name: str
    ) -> list[tuple[str, str | None]] | None:
        ...

    @abstractmethod
    def get_node_action_servers(
        self, node_name: str
    ) -> list[tuple[str, str | None]] | None:
        ...

    @abstractmethod
    def get_node_action_clients(
        self, node_name: str
    ) -> list[tuple[str, str | None]] | None:
        ...

    @abstractmethod
    def get_topic_types(self, topic_name: str) -> list[str]:
        ...

    @abstractmethod
    def get_topic_publishers(self, topic_name: str) -> list[tuple[str, str | None]]:
        ...

    @abstractmethod
    def get_topic_subscribers(self, topic_name: str) -> list[tuple[str, str | None]]:
        ...

    @abstractmethod
    def get_service_types(self, service_name: str) -> list[str]:
        ...

    @abstractmethod
    def get_service_servers(self, service_name: str) -> list[tuple[str, str | None]]:
        ...

    @abstractmethod
    def get_action_types(self, action_name: str) -> list[str]:
        ...

    @abstractmethod
    def get_action_servers(self, action_name: str) -> list[tuple[str, str]]:
        ...

    @abstractmethod
    def get_action_clients(self, action_name: str) -> list[tuple[str, str]]:
        ...

    @abstractmethod
    def get_msg_definition(self, msg_type: str) -> str:
        ...

    @abstractmethod
    def get_srv_definition(self, srv_type: str) -> str:
        ...

    @abstractmethod
    def get_action_definition(self, action_type: str) -> str:
        ...

    @abstractmethod
    def list_nodes(self) -> list[str]:
        ...

    @abstractmethod
    def list_topics(self, type: str | None) -> list[str]:
        ...

    @abstractmethod
    def list_services(self, type: str | None) -> list[str]:
        ...

    @abstractmethod
    def list_actions(self, type: str | None) -> list[str]:
        ...

    @abstractmethod
    def list_msg_types(self) -> list[str]:
        ...

    @abstractmethod
    def list_srv_types(self) -> list[str]:
        ...

    @abstractmethod
    def list_action_types(self) -> list[str]:
        ...

    # --- Topic monitoring (Hz / Echo) ---
    # Default implementations return no-op / empty so ROS1 needs no changes.

    def start_topic_monitor(self, topic_name: str) -> bool:
        return False

    def stop_topic_monitor(self, topic_name: str) -> None:
        pass

    def get_topic_hz(self, topic_name: str) -> float | None:
        return None

    def get_topic_echo(self, topic_name: str) -> list[str]:
        return []

    def set_topic_echo(self, topic_name: str, enabled: bool) -> None:
        pass

    # --- Node parameters (ROS2 only) ---

    def list_node_params(self, node_name: str) -> dict[str, str] | None:
        return None
