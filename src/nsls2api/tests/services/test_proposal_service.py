import pytest
from httpx import ASGITransport, AsyncClient

from nsls2api.main import app

from nsls2api.models.proposals import Proposal
from nsls2api.services import proposal_service

test_proposal_id = "314159"
test_beamline_name = "ZZZ"
test_beamline_name_lower = "zzz"
test_cycle_name = "1999-1"

PAGE = 1
PAGE_SIZE = 10


@pytest.mark.anyio
async def test_get_beamline_specific_slack_channel_for_proposal():
    slack_channels = (
        await proposal_service.get_beamline_specific_slack_channel_for_proposal(
            proposal_id=test_proposal_id
        )
    )
    # For a single beamline proposal we should only have 1 channel
    assert len(slack_channels) == 1
    assert slack_channels[0] == f"pass-{test_proposal_id}-zzz"


@pytest.mark.anyio
async def test_proposal_by_id():
    proposal: Proposal = await proposal_service.proposal_by_id(test_proposal_id)
    assert proposal is not None
    assert proposal.proposal_id == test_proposal_id


@pytest.mark.anyio
async def test_proposal_type_description_from_pass_type_id():
    test_proposal_type_id = 999999
    description = await proposal_service.proposal_type_description_from_pass_type_id(
        test_proposal_type_id
    )
    assert description is not None
    assert description == "Proposal Type X"


@pytest.mark.anyio
async def test_proposal_type_description_from_nonexistent_pass_type_id():
    test_proposal_type_id = 999991  # non-existent proposal type_id
    try:
        await proposal_service.proposal_type_description_from_pass_type_id(
            test_proposal_type_id
        )
        # If we get past the above line without an exception then something's wrong
        assert False
    except LookupError:
        # If we threw a LookupError for the non-existent type_id
        # then all is good.
        assert True


@pytest.mark.anyio
async def test_data_session_for_proposal():
    data_session = await proposal_service.data_session_for_proposal(
        proposal_id=test_proposal_id
    )
    assert data_session is not None
    assert data_session == f"pass-{test_proposal_id}"


@pytest.mark.anyio
async def test_beamlines_for_proposal():
    beamlines = await proposal_service.beamlines_for_proposal(
        proposal_id=test_proposal_id
    )
    assert beamlines is not None
    assert len(beamlines) == 1
    assert beamlines[0] == "ZZZ"


@pytest.mark.anyio
async def test_cycles_for_proposal():
    cycles = await proposal_service.cycles_for_proposal(proposal_id=test_proposal_id)
    assert cycles is not None
    assert len(cycles) == 1
    assert cycles[0] == "1999-1"


@pytest.mark.anyio
async def test_is_commissioning():
    proposal = await proposal_service.proposal_by_id(test_proposal_id)
    assert await proposal_service.is_commissioning(proposal) is False


@pytest.mark.anyio
async def test_case_sensitivity_fetch_proposals():
    proposal_objects_upper = await proposal_service.fetch_proposals(
        beamline=[test_beamline_name]
    )
    proposal_objects_lower = await proposal_service.fetch_proposals(
        beamline=[test_beamline_name_lower]
    )

    assert proposal_objects_upper == proposal_objects_lower
    assert proposal_objects_lower[0].proposal_id == test_proposal_id


@pytest.mark.anyio
async def test_data_sessions_endpoint(admin_api_key):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": admin_api_key["key"]},  # Use the api_key fixture here
    ) as ac:
        resp = await ac.get(
            "/v1/proposals/data-sessions",
            params={
                "beamline": test_beamline_name,
                "cycle": test_cycle_name,
                "facility": "nsls2",
                "page": PAGE,
                "page_size": PAGE_SIZE,
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    print(resp.json())
    assert "proposals" in body
    assert "count" in body
    assert "page_size" in body
    assert "page" in body
    assert body["count"] == len(body["proposals"])
    assert body["page_size"] == PAGE_SIZE
    assert body["page"] == PAGE
    assert body["count"] >= 1
    first = body["proposals"][0]
    assert set(first.keys()) == {"proposal_id", "data_session"}
    assert first["proposal_id"] == test_proposal_id
    assert first["data_session"] == f"pass-{test_proposal_id}"


@pytest.mark.anyio
async def test_data_sessions_pagination(admin_api_key):
    small_page_size = 2
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": admin_api_key["key"]},  # Use the api_key fixture here
    ) as ac:
        resp = await ac.get(
            "/v1/proposals/data-sessions",
            params={
                "beamline": test_beamline_name,
                "cycle": test_cycle_name,
                "facility": "nsls2",
                "page": 1,
                "page_size": small_page_size,
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    print(resp.json())
    assert body["page_size"] == small_page_size
    assert body["page"] == 1
    assert len(body["proposals"]) <= small_page_size
    for p in body["proposals"]:
        assert "proposal_id" in p
        assert "data_session" in p


@pytest.mark.anyio
async def test_data_sessions_invalid_beamline(admin_api_key):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": admin_api_key["key"]},  # Use the api_key fixture here
    ) as ac:
        resp = await ac.get(
            "/v1/proposals/data-sessions",
            params={
                "beamline": "INVALID",
                "cycle": test_cycle_name,
                "facility": "nsls2",
                "page": PAGE,
                "page_size": PAGE_SIZE,
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["proposals"] == []

@pytest.mark.anyio
async def test_fetch_proposals_by_username_exists():
    """Test filtering proposals by username that exists in test data"""
    proposal = await proposal_service.proposal_by_id(test_proposal_id)
    if proposal.users and len(proposal.users) > 0:
        test_username = proposal.users[0].username
        
        results = await proposal_service.fetch_proposals(username=test_username)
        
        assert len(results) > 0

        for p in results:
            usernames = [u.username for u in p.users]
            assert test_username in usernames


@pytest.mark.anyio
async def test_fetch_proposals_by_username_not_exists():
    """Test filtering by username that doesn't exist"""
    results = await proposal_service.fetch_proposals(username="nonexistent_user_xyz")
    
    assert len(results) == 0


@pytest.mark.anyio
async def test_fetch_proposals_username_whitespace():
    """Test username filtering with whitespace edge cases"""
    results_whitespace = await proposal_service.fetch_proposals(username="   ")
    
    results_no_filter = await proposal_service.fetch_proposals()
    
    assert len(results_whitespace) == len(results_no_filter)


@pytest.mark.anyio
async def test_fetch_proposals_username_with_pagination():
    """Test username filter works correctly with pagination"""
    proposal = await proposal_service.proposal_by_id(test_proposal_id)
    if proposal.users and len(proposal.users) > 0:
        test_username = proposal.users[0].username
        
        page_1 = await proposal_service.fetch_proposals(
            username=test_username,
            page_size=5,
            page=1
        )

        assert len(page_1) > 0

        for p in page_1:
            usernames = [u.username for u in p.users]
            assert test_username in usernames
