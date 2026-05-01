from __future__ import annotations

import subprocess
import threading
import time
import typing as t
from collections import deque
from pathlib import Path
from threading import Thread
from time import sleep

import rclpy
import ros2action.api
import ros2node.api
import ros2service.api
import ros2topic.api
from rclpy.action import (
    get_action_client_names_and_types_by_node,
    get_action_names_and_types,
    get_action_server_names_and_types_by_node,
)
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rosidl_runtime_py import (
    get_action_interfaces,
    get_interface_path,
    get_message_interfaces,
    get_service_interfaces,
)

from .base import RosInterface, RosVersion


def _get_full_path(namespace: str, name: str) -> str:
    if namespace == "/":
        return f"/{name}"
    else:
        return f"{namespace}/{name}"


def _flatten_node_info(
    entities: list[tuple[t.Any]],
) -> t.Generator[tuple[str, str | None]]:
    for entity in entities:
        if not entity.types:
            yield entity.name, None
        for type_ in entity.types:
            yield entity.name, type_


def _flatten_name_types(
    name_types: tuple[str, list[str]]
) -> t.Generator[tuple[str, str], None, None]:
    for name, types in name_types:
        if not types:
            yield name, None
        else:
            for type_ in types:
                yield name, type_


class _TopicMonitor:
    """rclpy subscription wrapper that tracks Hz and recent messages."""

    # Prevent huge messages (e.g. PointCloud2) from eating RAM.
    _MAX_MSG_CHARS = 4000
    # Keep only a handful of echo messages in memory.
    _MAX_ECHO_MSGS = 5

    def __init__(self) -> None:
        self._timestamps: deque[float] = deque(maxlen=100)
        self._messages: deque[str] = deque(maxlen=self._MAX_ECHO_MSGS)
        self._lock = threading.Lock()
        self.subscription = None
        # Echo is disabled by default; YAML conversion is skipped when False.
        self.echo_active: bool = False

    def callback(self, msg: t.Any) -> None:
        now = time.time()
        with self._lock:
            self._timestamps.append(now)

        # Only pay the cost of serialisation when echo is actually on.
        if not self.echo_active:
            return

        try:
            from rosidl_runtime_py.convert import message_to_yaml

            msg_str = message_to_yaml(msg)
        except Exception:
            msg_str = str(msg)

        # Truncate so that huge binary payloads (PointCloud2, Image, …)
        # never blow up memory or the TUI renderer.
        if len(msg_str) > self._MAX_MSG_CHARS:
            msg_str = msg_str[: self._MAX_MSG_CHARS] + f"\n... (truncated, total {len(msg_str)} chars)"

        with self._lock:
            self._messages.append(msg_str)

    def get_hz(self) -> float | None:
        with self._lock:
            ts = list(self._timestamps)
        now = time.time()
        recent = [t for t in ts if now - t < 5.0]
        if len(recent) < 2:
            return None
        window = recent[-1] - recent[0]
        if window < 1e-6:
            return None
        return (len(recent) - 1) / window

    def set_echo(self, enabled: bool) -> None:
        """Enable or disable YAML serialisation in callbacks.

        Disabling also clears the message buffer so stale data is not shown
        when echo is re-enabled later.
        """
        with self._lock:
            self.echo_active = enabled
            if not enabled:
                self._messages.clear()

    def get_messages(self) -> list[str]:
        """Return recent messages oldest-first."""
        with self._lock:
            return list(self._messages)


def _flatten_params(params: dict, prefix: str = "") -> dict[str, str]:
    """Recursively flatten nested param dict into dotted-key strings."""
    result: dict[str, str] = {}
    for k, v in params.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten_params(v, full_key))
        else:
            result[full_key] = str(v)
    return result


def _list_types_common(interfaces: dict[str, list[str]]) -> list[str]:
    full_types = []
    for package, type_names in interfaces.items():
        for type_name in type_names:
            full_types.append(f"{package}/{type_name}")

    return sorted(full_types)


class Ros2(RosInterface):
    node: Node

    def __init__(self, start_parameter_services: bool = False) -> None:
        rclpy.init()
        self.node = rclpy.create_node(
            "_rtui",
            enable_rosout=False,
            start_parameter_services=start_parameter_services,
            parameter_overrides=[],
        )

        Node.get_action_names_and_types = get_action_names_and_types
        Node.get_action_server_names_and_types_by_node = (
            get_action_server_names_and_types_by_node
        )
        Node.get_action_client_names_and_types_by_node = (
            get_action_client_names_and_types_by_node
        )

        executor = MultiThreadedExecutor()
        executor.add_node(self.node)
        self.thread = Thread(target=executor.spin, daemon=True)
        self.thread.start()

        sleep(0.01)

        self._monitors: dict[str, _TopicMonitor] = {}

        super().__init__()

    def terminate(self) -> None:
        for topic_name in list(self._monitors.keys()):
            self.stop_topic_monitor(topic_name)
        rclpy.shutdown()
        self.thread.join()

    @classmethod
    def version(_cls) -> RosVersion:
        return RosVersion.ROS2

    def get_node_publishers(self, node_name: str) -> list[tuple[str, str | None]]:
        return list(
            _flatten_node_info(
                ros2node.api.get_publisher_info(
                    node=self.node, remote_node_name=node_name
                )
            )
        )

    def get_node_subscribers(self, node_name: str) -> list[tuple[str, str | None]]:
        return list(
            _flatten_node_info(
                ros2node.api.get_subscriber_info(
                    node=self.node, remote_node_name=node_name
                )
            )
        )

    def get_node_service_servers(self, node_name: str) -> list[tuple[str, str | None]]:
        return list(
            _flatten_node_info(
                ros2node.api.get_service_server_info(
                    node=self.node, remote_node_name=node_name
                )
            )
        )

    def get_node_service_clients(self, node_name: str) -> list[tuple[str, str | None]]:
        return list(
            _flatten_node_info(
                ros2node.api.get_service_client_info(
                    node=self.node, remote_node_name=node_name
                )
            )
        )

    def get_node_action_servers(self, node_name: str) -> list[tuple[str, str | None]]:
        return list(
            _flatten_node_info(
                ros2node.api.get_action_server_info(
                    node=self.node, remote_node_name=node_name
                )
            )
        )

    def get_node_action_clients(self, node_name: str) -> list[tuple[str, str | None]]:
        return list(
            _flatten_node_info(
                ros2node.api.get_action_client_info(
                    node=self.node, remote_node_name=node_name
                )
            )
        )

    def get_topic_types(self, topic_name: str) -> list[str]:
        names_and_types: list[
            tuple[str, list[str]]
        ] = ros2topic.api.get_topic_names_and_types(
            node=self.node, include_hidden_topics=True
        )
        for name, types in names_and_types:
            if name == topic_name:
                return types

        return []

    def get_topic_publishers(self, topic_name: str) -> list[tuple[str, str]]:
        pubs = self.node.get_publishers_info_by_topic(topic_name)
        return list(
            (_get_full_path(comm.node_namespace, comm.node_name), comm.topic_type)
            for comm in pubs
        )

    def get_topic_subscribers(self, topic_name: str) -> list[tuple[str, str]]:
        subs = self.node.get_subscriptions_info_by_topic(topic_name)

        return list(
            (_get_full_path(comm.node_namespace, comm.node_name), comm.topic_type)
            for comm in subs
        )

    def get_service_types(self, service_name: str) -> list[str]:
        names_and_types = ros2service.api.get_service_names_and_types(
            node=self.node, include_hidden_services=True
        )
        for name, types in names_and_types:
            if name == service_name:
                return types

        return []

    def get_service_servers(self, service_name: str) -> None:
        """
        Unsupported for ROS2 because of the lack of API.
        """
        return None

    def get_action_types(self, action_name: str) -> list[str]:
        names_and_types = ros2action.api.get_action_names_and_types(node=self.node)
        for name, types in names_and_types:
            if name == action_name:
                return types

        return []

    def get_action_servers(self, action_name: str) -> list[str]:
        _, servers = ros2action.api.get_action_clients_and_servers(
            node=self.node, action_name=action_name
        )
        return list(_flatten_name_types(servers))

    def get_action_clients(self, action_name: str) -> list[str]:
        clients, _ = ros2action.api.get_action_clients_and_servers(
            node=self.node, action_name=action_name
        )
        return list(_flatten_name_types(clients))

    @staticmethod
    def __common_get_type_definition(type: str) -> str:
        return Path(get_interface_path(type)).read_text()

    def get_msg_definition(self, msg_type: str) -> str:
        return self.__common_get_type_definition(msg_type)

    def get_srv_definition(self, msg_type: str) -> str:
        return self.__common_get_type_definition(msg_type)

    def get_action_definition(self, msg_type: str) -> str:
        return self.__common_get_type_definition(msg_type)

    def list_nodes(self) -> list[str]:
        nodes = ros2node.api.get_node_names(node=self.node)
        return sorted({node.full_name for node in nodes})

    def list_topics(self, type: str | None = None) -> list[str]:
        topics = ros2topic.api.get_topic_names_and_types(node=self.node)
        return sorted({name for name, types in topics if type is None or type in types})

    def list_services(self, type: str | None = None) -> list[str]:
        services = ros2service.api.get_service_names_and_types(node=self.node)
        names = sorted(
            {name for name, types in services if type is None or type in types}
        )
        return names

    def list_actions(self, type: str | None = None) -> list[str]:
        actions = ros2action.api.get_action_names_and_types(node=self.node)
        names = sorted(
            {name for name, types in actions if type is None or type in types}
        )
        return names

    def list_msg_types(self) -> list[str]:
        return _list_types_common(get_message_interfaces())

    def list_srv_types(self) -> list[str]:
        return _list_types_common(get_service_interfaces())

    def list_action_types(self) -> list[str]:
        return _list_types_common(get_action_interfaces())

    # --- Topic monitoring ---

    def start_topic_monitor(self, topic_name: str) -> bool:
        if topic_name in self._monitors:
            return True
        try:
            msg_class = ros2topic.api.get_msg_class(
                self.node, topic_name, blocking=False, include_hidden_topics=True
            )
            if msg_class is None:
                return False
            monitor = _TopicMonitor()
            monitor.subscription = self.node.create_subscription(
                msg_class, topic_name, monitor.callback, 10
            )
            self._monitors[topic_name] = monitor
            return True
        except Exception:
            return False

    def stop_topic_monitor(self, topic_name: str) -> None:
        monitor = self._monitors.pop(topic_name, None)
        if monitor and monitor.subscription is not None:
            try:
                self.node.destroy_subscription(monitor.subscription)
            except Exception:
                pass

    def get_topic_hz(self, topic_name: str) -> float | None:
        monitor = self._monitors.get(topic_name)
        return monitor.get_hz() if monitor else None

    def get_topic_echo(self, topic_name: str) -> list[str]:
        monitor = self._monitors.get(topic_name)
        return monitor.get_messages() if monitor else []

    def set_topic_echo(self, topic_name: str, enabled: bool) -> None:
        monitor = self._monitors.get(topic_name)
        if monitor:
            monitor.set_echo(enabled)

    # --- Node parameters ---

    def list_node_params(self, node_name: str) -> dict[str, str] | None:
        try:
            result = subprocess.run(
                ["ros2", "param", "dump", node_name],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if result.returncode != 0:
                return None

            import yaml

            data = yaml.safe_load(result.stdout)
            if not isinstance(data, dict):
                return None

            # Key may be "/node_name" or "node_name"
            node_key = next(
                (k for k in data if k == node_name or k == node_name.lstrip("/")),
                None,
            )
            if node_key is None:
                return {}

            ros_params = data[node_key].get("ros__parameters", {})
            return dict(sorted(_flatten_params(ros_params).items()))
        except Exception:
            return None
