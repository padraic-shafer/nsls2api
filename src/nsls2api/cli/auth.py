import getpass

import httpx
import typer
from rich.panel import Panel
from rich.table import Table

from nsls2api.cli.settings import get_base_url, get_token, remove_token, set_token
from nsls2api.cli.utils.cli_helpers import auto_help_if_no_command
from nsls2api.cli.utils.console import console

app = typer.Typer(invoke_without_command=True)


@app.callback()
@auto_help_if_no_command()
def auth_callback(ctx: typer.Context):
    pass  # No need to call anything manually


def verify_token(token: str) -> tuple[bool, str | None]:
    """
    Verify if a token is valid by making an API call.
    Returns a tuple of (is_valid, username or error_message)
    """
    url = f"{get_base_url()}/v1/person/me"
    try:
        with httpx.Client() as client:
            headers = {"Authorization": f"{token}"}
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return True, response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            return False, "Invalid API token"
        elif exc.response.status_code == 403:
            return False, "Access denied"
        else:
            return False, f"An error occurred: {exc}"
    except httpx.RequestError as exc:
        return False, f"An error occurred while trying to contact the API: {exc}"


def create_status_table(username: str, api_url: str) -> Table:
    """Create a rich table for status display"""
    table = Table(show_header=False, box=None)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Status", "✓ Authenticated")
    table.add_row("Username", username)
    table.add_row("API URL", api_url)
    return table


@app.command()
def status():
    """Show the current authentication status"""
    with console.status("[cyan]Checking authentication status...", spinner="dots"):
        token = get_token()

        if token is None:
            panel = Panel(
                "[warning]Not currently logged in\n[info]Use [bold]nsls2api auth login[/bold] to authenticate",
                title="Authentication Status",
                border_style="yellow",
            )
            console.print(panel)
            return

        is_valid, result = verify_token(token)

        if is_valid:
            table = create_status_table(result, get_base_url())
            panel = Panel(table, title="Authentication Status", border_style="green")
            console.print(panel)
        else:
            panel = Panel(
                f"[error]{result}\n[info]Use [bold]nsls2api auth login[/bold] to reauthenticate",
                title="Authentication Error",
                border_style="red",
            )
            console.print(panel)


@app.command()
def login():
    """Log in to the NSLS-II API"""
    token = get_token()
    read_token_from_file = True

    if token is None:
        read_token_from_file = False
        console.print("[info]No API token found")
        token = getpass.getpass(prompt="Please enter your API token: ")
        if len(token) == 0:
            # logged_in_username: SpecialUsers = SpecialUsers.anonymous
            console.print("[warning]Authenticated as anonymous")
            return

    with console.status("[cyan]Verifying credentials...", spinner="dots"):
        is_valid, result = verify_token(token)

    if is_valid:
        if not read_token_from_file:
            set_token(token)
            console.print(
                Panel(
                    f"[success]Successfully authenticated as {result}\n[info]Token saved to config file",
                    title="Login Successful",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel(
                    f"[success]Successfully authenticated as {result}",
                    title="Login Successful",
                    border_style="green",
                )
            )
    else:
        console.print(
            Panel(f"[error]{result}", title="Login Failed", border_style="red")
        )


@app.command()
def logout():
    """Log out and remove stored credentials"""
    with console.status("[cyan]Logging out...", spinner="dots"):
        remove_token()

    panel = Panel(
        "[success]Successfully logged out", title="Logout", border_style="green"
    )
    console.print(panel)
