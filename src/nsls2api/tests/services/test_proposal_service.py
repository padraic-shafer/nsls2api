import pytest
from httpx import ASGITransport, AsyncClient

from nsls2api.main import app

from nsls2api.models.proposals import Proposal, User, SafetyForm
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
async def test_fetch_proposals_filter_username_positive():
    """Username filter positive - target username A vs control username B."""
    target_proposal = Proposal(
        proposal_id="1001",
        data_session="pass-1001",
        cycles=["2025-1"],
        instruments=["TEST"],
        users=[
            User(
                first_name="Target",
                last_name="User",
                email="target@example.com",
                username="alice",
            )
        ],
        safs=[],
    )
    await target_proposal.insert()

    control_proposal = Proposal(
        proposal_id="1002",
        data_session="pass-1002",
        cycles=["2025-1"],
        instruments=["TEST"],
        users=[
            User(
                first_name="Control",
                last_name="User",
                email="control@example.com",
                username="bob",
            )
        ],
        safs=[],
    )
    await control_proposal.insert()

    results = await proposal_service.fetch_proposals(username="alice")

    result_ids = {p.proposal_id for p in results}
    assert "1001" in result_ids
    assert "1002" not in result_ids


@pytest.mark.anyio
async def test_fetch_proposals_filter_username_negative():
    """Username filter negative - nonexistent username returns empty."""
    results = await proposal_service.fetch_proposals(username="nonexistent_user_xyz")

    assert len(results) == 0


@pytest.mark.anyio
async def test_fetch_proposals_filter_saf_status_positive():
    """SAF status positive - APPROVED proposal vs EXPIRED proposal."""
    target_proposal = Proposal(
        proposal_id="2001",
        data_session="pass-2001",
        cycles=["2025-1"],
        instruments=["TEST"],
        users=[User(first_name="Test", last_name="User", email="test@example.com")],
        safs=[SafetyForm(saf_id="SAF001", status="APPROVED", instruments=["TEST"])],
    )
    await target_proposal.insert()

    control_proposal = Proposal(
        proposal_id="2002",
        data_session="pass-2002",
        cycles=["2025-1"],
        instruments=["TEST"],
        users=[User(first_name="Test", last_name="User", email="test@example.com")],
        safs=[SafetyForm(saf_id="SAF002", status="EXPIRED", instruments=["TEST"])],
    )
    await control_proposal.insert()

    results = await proposal_service.fetch_proposals(saf_status=["APPROVED"])

    result_ids = {p.proposal_id for p in results}
    assert "2001" in result_ids
    assert "2002" not in result_ids


@pytest.mark.anyio
async def test_fetch_proposals_filter_saf_status_multiple():
    """SAF status multiple - find only proposals and SAFs with specified statuses."""
    target_proposal = Proposal(
        proposal_id="3001",
        data_session="pass-3001",
        cycles=["2025-1"],
        instruments=["TEST"],
        users=[User(first_name="Test", last_name="User", email="test@example.com")],
        safs=[
            SafetyForm(saf_id="SAF001", status="APPROVED", instruments=["TEST"]),
            SafetyForm(saf_id="SAF002", status="EXPIRED", instruments=["TEST"]),
            SafetyForm(saf_id="SAF003", status="DRAFT", instruments=["TEST"]),
        ],
    )
    await target_proposal.insert()

    control_proposal = Proposal(
        proposal_id="3002",
        data_session="pass-3002",
        cycles=["2025-1"],
        instruments=["TEST"],
        users=[User(first_name="Test", last_name="User", email="test@example.com")],
        safs=[
            SafetyForm(saf_id="SAF004", status="CLOSED", instruments=["TEST"]),
            SafetyForm(saf_id="SAF005", status="EXPIRED", instruments=["TEST"]),
            SafetyForm(saf_id="SAF006", status="HOLD", instruments=["TEST"]),
        ],
    )
    await control_proposal.insert()

    results = await proposal_service.fetch_proposals(saf_status=["APPROVED", "DRAFT"])

    result_ids = {p.proposal_id for p in results}
    assert "3001" in result_ids
    assert "3002" not in result_ids

    safs = next(p.safs for p in results)
    saf_statuses = {saf.status for saf in safs}
    assert "APPROVED" in saf_statuses
    assert "DRAFT" in saf_statuses
    assert "EXPIRED" not in saf_statuses


@pytest.mark.anyio
async def test_fetch_proposals_filter_combined_all_filters():
    """Combined filters - username + cycle + beamline + saf_status all required."""
    matching = Proposal(
        proposal_id="4001",
        data_session="pass-4001",
        cycles=["2025-combined"],
        instruments=["COMBO-BL"],
        users=[
            User(
                first_name="Test",
                last_name="User",
                email="test@example.com",
                username="combo_user",
            )
        ],
        safs=[SafetyForm(saf_id="SAF-C1", status="APPROVED", instruments=["COMBO-BL"])],
    )
    await matching.insert()

    nonmatching_user = Proposal(
        proposal_id="4002",
        data_session="pass-4002",
        cycles=["2025-combined"],
        instruments=["COMBO-BL"],
        users=[
            User(
                first_name="Other",
                last_name="User",
                email="other@example.com",
                username="other_user",
            )
        ],
        safs=[SafetyForm(saf_id="SAF-C2", status="APPROVED", instruments=["COMBO-BL"])],
    )
    await nonmatching_user.insert()

    nonmatching_cycle = Proposal(
        proposal_id="4003",
        data_session="pass-4003",
        cycles=["2025-other"],
        instruments=["COMBO-BL"],
        users=[
            User(
                first_name="Test",
                last_name="User",
                email="test@example.com",
                username="combo_user",
            )
        ],
        safs=[SafetyForm(saf_id="SAF-C3", status="APPROVED", instruments=["COMBO-BL"])],
    )
    await nonmatching_cycle.insert()

    nonmatching_beamline = Proposal(
        proposal_id="4004",
        data_session="pass-4004",
        cycles=["2025-combined"],
        instruments=["OTHER-BL"],
        users=[
            User(
                first_name="Test",
                last_name="User",
                email="test@example.com",
                username="combo_user",
            )
        ],
        safs=[SafetyForm(saf_id="SAF-C4", status="APPROVED", instruments=["OTHER-BL"])],
    )
    await nonmatching_beamline.insert()

    nonmatching_saf_status = Proposal(
        proposal_id="4005",
        data_session="pass-4005",
        cycles=["2025-combined"],
        instruments=["COMBO-BL"],
        users=[
            User(
                first_name="Test",
                last_name="User",
                email="test@example.com",
                username="combo_user",
            )
        ],
        safs=[SafetyForm(saf_id="SAF-C5", status="DRAFT", instruments=["COMBO-BL"])],
    )
    await nonmatching_saf_status.insert()

    results = await proposal_service.fetch_proposals(
        username="combo_user",
        cycle=["2025-combined"],
        beamline=["COMBO-BL"],
        saf_status=["APPROVED"],
    )

    result_ids = {p.proposal_id for p in results}
    assert "4001" in result_ids
    assert "4002" not in result_ids
    assert "4003" not in result_ids
    assert "4004" not in result_ids
    assert "4005" not in result_ids
