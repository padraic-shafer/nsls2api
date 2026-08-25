import pytest
from httpx import ASGITransport, AsyncClient

from nsls2api.main import app


@pytest.mark.anyio
async def test_healthy_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/healthy")
    assert response.status_code == 200
    assert response.text == "OK"


@pytest.mark.anyio
async def test_home_page():
    """Test that the home page (/) renders successfully with HTML content."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


@pytest.mark.anyio
async def test_favicon_redirect():
    """Test that favicon requests redirect to static assets."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/favicon.ico", follow_redirects=False)
    assert response.status_code == 307
    assert "/static/images/favicon.ico" in response.headers.get("location", "")


@pytest.mark.anyio
async def test_proposal_search_page():
    """Test that the proposal search page renders successfully."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/search/proposals")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
