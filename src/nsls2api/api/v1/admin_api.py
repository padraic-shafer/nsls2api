from typing import Annotated

import fastapi
from fastapi import Depends, HTTPException, Query
from starlette.responses import Response

from nsls2api.api.models.facility_model import FacilityName
from nsls2api.api.models.proposal_model import (
    LockedProposalsList,
    ProposalChangeResultsList,
    ProposalsToChangeList,
    SingleProposal,
)
from nsls2api.infrastructure import config
from nsls2api.infrastructure.security import (
    generate_api_key,
    validate_admin_role,
)
from nsls2api.models.apikeys import (
    ApiUser,
    ApiUserResponseModel,
    ApiUserRole,
    ApiUserType,
)
from nsls2api.services import beamline_service, facility_service, proposal_service

router = fastapi.APIRouter(
    dependencies=[Depends(validate_admin_role)], include_in_schema=True, tags=["admin"]
)


@router.get("/admin/settings")
async def info(settings: Annotated[config.Settings, Depends(config.get_settings)]):
    return settings


@router.get("/admin/validate", response_model=str)
async def check_admin_validation(
    admin_user: Annotated[ApiUser, Depends(validate_admin_role)] = None,
):
    """
    :return: str - The username of the validated admin user.
    """

    if admin_user is None:
        raise HTTPException(
            status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin API key",
        )

    return admin_user.username


@router.post("/admin/generate-api-key/{username}")
async def generate_user_apikey(username: str, usertype: ApiUserType = ApiUserType.user):
    """
    Generate an API key for a given username.

    :param username: The username for which to generate the API key.
    :param usertype: The type of API key to generate.
    :return: The generated API key.
    """
    return await generate_api_key(username, usertype=usertype)


@router.post("/admin/proposal/generate-test")
async def generate_fake_proposal(
    add_specific_user: str | None = None,
) -> SingleProposal | None:
    proposal = await proposal_service.generate_fake_test_proposal(
        FacilityName.nsls2, add_specific_user
    )

    if proposal is None:
        raise HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate a fake test proposal",
        )

    return SingleProposal(proposal=proposal)


@router.put("/admin/user/{username}/role/{role}")
async def update_user_role(username: str, role: ApiUserRole) -> ApiUserResponseModel:
    """
    Update the role of a user.

    :param username: The username of the user to update.
    :param role: The new role for the user.
    :return: The updated user object.
    """
    user = await ApiUser.find_one(ApiUser.username == username)
    if user is None:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"User {username} not found",
        )

    user.role = role
    await user.save()

    response = ApiUserResponseModel(
        id=user.id,
        username=user.username,
        type=user.type,
        role=user.role,
        created_on=user.created_on,
        last_updated=user.last_updated,
    )

    return response


@router.put(
    "/admin/proposals/cycle/lock/{cycle_name}/{facility}",
    response_model=ProposalChangeResultsList,
)
async def lock_cycle(cycle_name: str, facility: str):
    cycle = await facility_service.cycle_exists(
        cycle_name=cycle_name, facility=facility
    )
    if not cycle:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"Cycle {cycle_name} not found",
        )
    page, page_size = 1, 100
    count = page_size
    proposals_to_change = []
    while count == page_size:
        proposals_at_cycle = await proposal_service.fetch_proposals(
            cycle=[cycle_name], facility=[facility], page=page, page_size=page_size
        )
        proposals_to_change.extend(
            [proposal.proposal_id for proposal in proposals_at_cycle]
        )
        count = len(proposals_at_cycle)
        page += 1

    proposal_list = ProposalsToChangeList(proposals_to_change=proposals_to_change)
    locked_info = await proposal_service.lock(proposal_list)
    return locked_info


@router.put(
    "/admin/proposals/cycle/unlock/{cycle_name}/{facility}",
    response_model=ProposalChangeResultsList,
)
async def unlock_cycle(cycle_name: str, facility: str):
    cycle = await facility_service.cycle_exists(
        cycle_name=cycle_name, facility=facility
    )
    if not cycle:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"Cycle {cycle_name} not found",
        )
    page, page_size = 1, 100
    count = page_size
    proposals_to_change = []
    while count == page_size:
        proposals_at_cycle = await proposal_service.fetch_proposals(
            cycle=[cycle_name], facility=[facility], page=page, page_size=page_size
        )
        proposals_to_change.extend(
            [proposal.proposal_id for proposal in proposals_at_cycle]
        )
        count = len(proposals_at_cycle)
        page += 1

    proposal_list = ProposalsToChangeList(proposals_to_change=proposals_to_change)
    unlocked_info = await proposal_service.unlock(proposal_list)
    return unlocked_info


@router.put(
    "/admin/proposals/beamline/unlock/{beamline_name}",
    response_model=ProposalChangeResultsList,
)
async def unlock_beamline(beamline_name: str):
    beamline = await beamline_service.beamline_by_name(beamline_name)
    if beamline is None:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"Beamline {beamline_name} not found",
        )
    page, page_size = 1, 100
    count = page_size
    proposals_to_change = []
    while count == page_size:
        proposals_at_beamline = await proposal_service.fetch_proposals(
            beamline=[beamline_name], page=page, page_size=page_size
        )
        proposals_to_change.extend(
            [proposal.proposal_id for proposal in proposals_at_beamline]
        )
        count = len(proposals_at_beamline)
        page += 1

    proposal_list = ProposalsToChangeList(proposals_to_change=proposals_to_change)
    unlocked_info = await proposal_service.unlock(proposal_list)
    return unlocked_info


@router.put(
    "/admin/proposals/beamline/lock/{beamline_name}",
    response_model=ProposalChangeResultsList,
)
async def lock_beamline(beamline_name: str):
    beamline = await beamline_service.beamline_by_name(beamline_name)
    if beamline is None:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"Beamline {beamline_name} not found",
        )
    page, page_size = 1, 100
    count = page_size
    proposals_to_change = []
    while count == page_size:
        proposals_at_beamline = await proposal_service.fetch_proposals(
            beamline=[beamline_name], page=page, page_size=page_size
        )
        proposals_to_change.extend(
            [proposal.proposal_id for proposal in proposals_at_beamline]
        )
        count = len(proposals_at_beamline)
        page += 1

    proposal_list = ProposalsToChangeList(proposals_to_change=proposals_to_change)
    locked_info = await proposal_service.lock(proposal_list)
    return locked_info


@router.put(
    "/admin/proposals/lock",
    response_model=ProposalChangeResultsList,
)
async def lock(proposal_list: ProposalsToChangeList, response: Response):
    unknown_proposals = [
        proposal
        for proposal in proposal_list.proposals_to_change
        if not await proposal_service.exists(proposal)
    ]
    if unknown_proposals:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"Proposals {unknown_proposals} not found. No action taken.",
        )
    locked_info = await proposal_service.lock(proposal_list)
    if locked_info.failed_proposals:
        response.status_code = fastapi.status.HTTP_422_UNPROCESSABLE_ENTITY
    return locked_info


@router.get("/admin/proposals/locked", response_model=LockedProposalsList)
async def gather_locked_proposals(
    facility: str,
    beamline: Annotated[list[str], Query()] = [],
    cycle: Annotated[list[str], Query()] = [],
    page_size: int = Query(10, ge=1, le=200),
    page: int = Query(1, ge=1),
):
    for beamline_name in beamline:
        beamline_info = await beamline_service.beamline_by_name(beamline_name)
        if beamline_info is None:
            raise HTTPException(
                status_code=fastapi.status.HTTP_404_NOT_FOUND,
                detail=f"Beamline {beamline_name} not found",
            )
    for cycle_name in cycle:
        if not await facility_service.cycle_exists(
            cycle_name=cycle_name, facility=facility
        ):
            raise HTTPException(
                status_code=fastapi.status.HTTP_404_NOT_FOUND,
                detail=f"Cycle {cycle_name} not found",
            )
    locked_proposals = await proposal_service.get_locked_proposals(
        cycles=cycle, beamlines=beamline, page=page, page_size=page_size
    )
    locked_proposals_list = locked_proposals.locked_proposals
    if locked_proposals_list is None:
        raise HTTPException(
            status_code=fastapi.status.HTTP_204_NO_CONTENT,
            detail="No locked proposals found",
        )
    return locked_proposals


@router.put(
    "/admin/proposals/unlock",
    response_model=ProposalChangeResultsList,
)
async def unlock(proposal_list: ProposalsToChangeList, response: Response):
    unknown_proposals = [
        proposal
        for proposal in proposal_list.proposals_to_change
        if not await proposal_service.exists(proposal)
    ]
    if unknown_proposals:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"Proposals {unknown_proposals} not found. No action taken.",
        )
    unlocked_info = await proposal_service.unlock(proposal_list)
    if unlocked_info.failed_proposals:
        response.status_code = fastapi.status.HTTP_422_UNPROCESSABLE_ENTITY
    return unlocked_info
