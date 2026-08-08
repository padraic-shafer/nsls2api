import click
import httpx
import httpx_socks
from httpx import Response

from nsls2api.infrastructure import config
from nsls2api.infrastructure.logging import logger

settings = config.get_settings()


class HTTPXClientWrapper:
    async_client = None

    def start(self):
        transport = None
        if settings.use_socks_proxy:
            transport = httpx_socks.AsyncProxyTransport.from_url(settings.socks_proxy)
        timeouts = httpx.Timeout(
            None, connect=30.0
        )  # 30s timeout on connect, no other timeouts.
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        self.async_client = httpx.AsyncClient(
            limits=limits, timeout=timeouts, transport=transport
        )
        logger.info(
            f"HTTPXClientWrapper [{click.style(str(id(self.async_client)), fg='cyan')}] started."
        )

    async def stop(self):
        logger.info(
            f"HTTPXClientWrapper [{click.style(str(id(self.async_client)), fg='cyan')}] stopped."
        )
        await self.async_client.aclose()
        self.async_client = None

    def __call__(self):
        # logger.info(f"HTTPXClientWrapper called. {id(self.async_client)}")
        return self.async_client


async def _call_async_webservice(
    url: str,
    auth: tuple | None = None,
    headers: dict | None = None,
) -> Response:
    transport = None

    if settings.use_socks_proxy:
        transport = httpx_socks.AsyncProxyTransport.from_url(settings.socks_proxy)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(None, connect=30.0),
        transport=transport,
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=5),
        auth=auth,
        headers=headers,
    ) as client:
        logger.debug(f"Calling {url} using unshared client.")
        resp: Response = await client.get(url)
        resp.raise_for_status()
        # if resp.status_code != 200:
        #      raise ValidationError(resp.text, status_code=resp.status_code)
    results = resp.json()
    return results


async def _call_async_webservice_with_client(
    url: str, auth: tuple | None = None, headers: dict | None = None, client: httpx.AsyncClient = None
) -> Response:
    if client is None:
        # Then just use the general method that creates a client each time
        return await _call_async_webservice(url, auth, headers)
    else:
        resp: Response = await client.get(url, timeout=90.0, auth=auth, headers=headers)
        resp.raise_for_status()
        results = resp.json()
        return results


httpx_client_wrapper = HTTPXClientWrapper()
