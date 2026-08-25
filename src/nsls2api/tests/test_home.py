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


@pytest.mark.anyio
async def test_proposal_search_htmx_request():
    """Test that HTMX requests to /search/proposals return HTML partial."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get(
            "/search/proposals",
            headers={"HX-Request": "true"}
        )
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


@pytest.mark.anyio
async def test_proposal_details_page():
    """Test that the proposal details page renders successfully.
    
    Note: This test uses a dummy proposal ID. In a real integration test,
    this would be seeded with actual proposal data from the database.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/proposal-details/314159")
    # Should return 200 or 404 depending on database state, but either way
    # should render HTML (not a 500 error from TemplateResponse signature issue)
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        assert "text/html" in response.headers.get("content-type", "")
