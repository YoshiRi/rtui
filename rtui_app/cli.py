import os
import sys
from os import environ

import click

from .app import InspectApp
from .ros import RosClient, RosEntityType


def is_ros2() -> bool:
    return environ.get("ROS_VERSION") == "2"


def inspect_common(target: RosEntityType) -> None:
    # Redirect OS-level stderr (fd 2) to a log file so that ROS2 rcutils
    # C-layer log messages don't corrupt the Textual TUI display.
    log_path = os.path.join(environ.get("TMPDIR", "/tmp"), "rtui.log")
    saved_fd2 = os.dup(2)
    log_fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    os.dup2(log_fd, 2)
    os.close(log_fd)
    saved_stderr = sys.stderr
    sys.stderr = open(log_path, "a", buffering=1)

    try:
        ros = RosClient()
        app = InspectApp(ros=ros, init_target=target)
        app.run()
    finally:
        ros.terminate()
        sys.stderr.close()
        sys.stderr = saved_stderr
        os.dup2(saved_fd2, 2)
        os.close(saved_fd2)


@click.command(help="Inspect ROS nodes (default)")
def node() -> None:
    inspect_common(RosEntityType.Node)


@click.command(hidden=True)
def nodes() -> None:
    inspect_common(RosEntityType.Node)


@click.command(help="Inspect ROS topics")
def topic() -> None:
    inspect_common(RosEntityType.Topic)


@click.command(hidden=True)
def topics() -> None:
    inspect_common(RosEntityType.Topic)


@click.command(help="Inspect ROS services")
def service() -> None:
    inspect_common(RosEntityType.Service)


@click.command(hidden=True)
def services() -> None:
    inspect_common(RosEntityType.Service)


@click.command(help="Inspect ROS actions")
def action() -> None:
    inspect_common(RosEntityType.Action)


@click.command(hidden=True)
def actions() -> None:
    inspect_common(RosEntityType.Action)


@click.group(help="Inspect ROS types")
def type() -> None:
    ...


@click.command(name="msg", help="Inspect ROS message types")
def type_msg() -> None:
    inspect_common(RosEntityType.MsgType)


@click.command(name="srv", help="Inspect ROS service types")
def type_srv() -> None:
    inspect_common(RosEntityType.SrvType)


@click.command(name="action", help="Inspect ROS action types")
def type_action() -> None:
    inspect_common(RosEntityType.ActionType)


@click.group(help="Terminal User Interface for ROS User", invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        ctx.invoke(node)


def main() -> None:
    cli.add_command(node)
    cli.add_command(topic)
    cli.add_command(service)
    cli.add_command(type)
    type.add_command(type_msg)
    type.add_command(type_srv)

    # old
    cli.add_command(nodes)
    cli.add_command(topics)
    cli.add_command(services)

    if is_ros2():
        cli.add_command(action)
        type.add_command(type_action)

        # old
        cli.add_command(actions)

    cli()


if __name__ == "__main__":
    main()
