import sys

import typer
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from nsls2api.cli import admin, api, auth, beamline, environment, facility, proposal
from nsls2api.version import get_version

# Remove no_args_is_help and add invoke_without_command to allow a version option without subcommand.
app = typer.Typer(
    help="NSLS-II API Command Line Interface", invoke_without_command=True
)

# Register sub-commands
app.add_typer(admin.app, name="admin", help="Administrative commands")
app.add_typer(api.app, name="api", help="API status and metrics")
app.add_typer(auth.app, name="auth", help="Authentication management")
app.add_typer(beamline.app, name="beamline", help="Beamline operations")
app.add_typer(environment.app, name="env", help="Environment management")
app.add_typer(facility.app, name="facility", help="Facility operations")
app.add_typer(proposal.app, name="proposal", help="Proposal management")

console = Console(
    theme=Theme(
        {
            "info": "cyan",
            "warning": "yellow",
            "error": "red bold",
            "success": "green bold",
            "command": "magenta bold",
            "subcommand": "cyan",
            "description": "white",
            "heading": "yellow bold",
        }
    )
)


def create_command_panel(command_name: str, commands: dict) -> Panel:
    """Create a panel for a command group"""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Command", style="subcommand")
    table.add_column("Description", style="description")

    for cmd, desc in commands.items():
        table.add_row(cmd, desc)

    return Panel(
        table,
        title=f"[heading]{command_name} Commands",
        border_style="blue",
        box=box.ROUNDED,
    )


def show_welcome():
    """Display welcome message and version information"""
    version = get_version()

    welcome_panel = Panel(
        Text("Welcome to the NSLS-II API Command Line Interface", style="info"),
        subtitle=f"Version: {version}",
        border_style="cyan",
        box=box.DOUBLE,
    )
    console.print(welcome_panel)


def show_available_commands():
    """Display available commands in an organized layout"""
    command_groups = {
        "Authentication": {
            "auth login": "Log in to the NSLS-II API",
            "auth logout": "Log out and remove stored credentials",
            "auth status": "Show current authentication status",
        },
        "Environment": {
            "env show": "Show current API environment",
            "env switch": "Switch between environments (prod/dev/local)",
        },
        "API": {"api status": "Show API status", "api metrics": "Show API metrics"},
        "Resources": {
            "beamline": "Manage beamline operations",
            "facility": "Manage facility operations",
            "proposal": "Manage proposals",
        },
        "Administration": {"admin": "Administrative commands"},
    }

    panels = []
    for group, commands in command_groups.items():
        panels.append(create_command_panel(group, commands))

    console.print(Columns(panels, equal=True, expand=True))


def show_usage_tips():
    """Display usage tips"""
    tips_panel = Panel(
        "[info]Tips:\n"
        "• Use [command]-h[/command] or [command]--help[/command] with any command to see detailed usage\n"
        "• Set environment with [command]env switch[/command] before using other commands\n"
        "• Always [command]auth login[/command] before accessing protected resources",
        title="Usage Tips",
        border_style="green",
        box=box.ROUNDED,
    )
    console.print(tips_panel)


@app.callback()
def main(
    ctx: typer.Context,
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        help="Show version and exit",
        is_eager=True,
    ),
):
    """
    NSLS-II API Command Line Interface
    """
    if version:
        version = get_version()
        console.print(f"[info]NSLS-II API CLI version: {version}")
        raise typer.Exit()

    # Only show a welcome message and commands if no subcommand is specified
    if ctx.invoked_subcommand is None:
        show_welcome()
        console.print()
        show_available_commands()
        console.print()
        show_usage_tips()


def run():
    try:
        app()
    except Exception as e:
        console.print(f"[error]Error: {e!s}")
        sys.exit(1)


if __name__ == "__main__":
    run()
