
import httpx
from rich.panel import Panel

from nsls2api.cli.settings import get_base_url, get_token
from nsls2api.cli.utils.console import console


def call_nsls2api_endpoint(
    endpoint: str, method: str = "GET", data: dict | None = None
) -> httpx.Response | None:
    """
    Call the NSLS-II API endpoint and return the response.
    """
    url = f"{get_base_url()}/{endpoint}"
    try:
        with httpx.Client() as client:
            token = get_token()
            headers = {"Authorization": f"{token}"} if token else {}
            if method == "GET":
                response = client.get(url, headers=headers)
            elif method == "POST":
                response = client.post(url, json=data, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            panel = Panel(
                "[error]Invalid API token",
                title="NSLS-II API Error",
                border_style="red",
            )
            console.print(panel)
            return None
        elif exc.response.status_code == 403:
            panel = Panel(
                "[error]Access denied: You do not have permission to access this resource",
                title="NSLS-II API Error",
                border_style="red",
            )
            console.print(panel)
            return None
        elif exc.response.status_code == 404:
            panel = Panel(
                f"[error]Not found: The requested resource '{url}' could not be found",
                title="NSLS-II API Error",
                border_style="red",
            )
            console.print(panel)
            return None
        else:
            panel = Panel(
                f"[error]An unexpected status error was returned when trying to contact the NSLS-II API: {exc}",
                title="NSLS-II API Error",
                border_style="red",
            )
            console.print(panel)
            return None
    except httpx.RequestError as exc:
        panel = Panel(
            f"[error]An error occurred while trying to contact the API: {exc}",
            title="NSLS-II API Request Error",
            border_style="red",
        )
        console.print(panel)
        return None
    return response
