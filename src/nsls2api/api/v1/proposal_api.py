import datetime
from typing import Annotated

import fastapi
from fastapi import Depends, HTTPException, Query

from nsls2api.api.models.facility_model import FacilityName
from nsls2api.api.models.proposal_model import (
    CommissioningProposalsList,
    ProposalDirectoriesList,
    ProposalFullDetailsList,
    ProposalUser,
    ProposalUserList,
    RecentProposal,
    RecentProposalsList,
    SingleProposal,
    UsernamesList,
    ProposalIdDataSessionList
)
from nsls2api.infrastructure.logging import logger
from nsls2api.infrastructure.security import get_current_user, validate_admin_role
from nsls2api.models.slack_models import (
    ProposalSlackChannel,
    SlackChannel,
    SlackConversation,
)
from nsls2api.services import (
    proposal_service,
    slack_service,
    facility_service
)
from nsls2api.services.slack_service import get_conversation_details

router = fastapi.APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/proposals/recent/{count}", response_model=RecentProposalsList)
async def get_recent_proposals(count: int, beamline: str | None = None):
    count = max(1, count)

    proposals = await proposal_service.recently_updated(count, beamline=beamline)

    proposal_models = [
        RecentProposal(
            proposal_id=p.proposal_id,
            title=p.title,
            updated=p.last_updated,
            instruments=p.instruments,
        )
        for p in proposals
    ]
    model = RecentProposalsList(count=len(proposal_models), proposals=proposal_models)

    return model


@router.get("/proposals/commissioning", response_model=CommissioningProposalsList)
async def get_commissioning_proposals(
    beamline: str | None = None, facility: FacilityName | None = None
):
    """
    Get a list of commissioning proposals.  If a beamline is provided, only proposals
    for that beamline will be returned and the facility will be ignored.

    Args:
        beamline (str optional): The beamline to filter proposals by.
        facility (FacilityName optional): The facility to filter proposals by.

    Returns:
        CommissioningProposalsList: A list of commissioning proposals.

    Raises:
        HTTPException: If no commissioning proposals are found or an error occurs.
    """
    try:
        proposals = await proposal_service.commissioning_proposals(
            beamline=beamline, facility=facility
        )
        if proposals is None:
            raise HTTPException(
                status_code=fastapi.status.HTTP_404_NOT_FOUND,
                detail="No commissioning proposals found",
            )
    except LookupError as e:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND, detail=e.args[0]
        )
    except Exception as e:
        raise HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {e}",
        )

    return proposals


@router.get(
    "/proposals/",
    response_model=ProposalFullDetailsList,
    dependencies=[Depends(validate_admin_role)],
    description="Not fully functional yet.",
)
async def get_proposals(
    proposal_id: Annotated[list[str], Query()] = [],
    beamline: Annotated[list[str], Query()] = [],
    cycle: Annotated[list[str], Query()] = [],
    facility: Annotated[list[FacilityName], Query()] = [FacilityName.nsls2],
    page_size: int = Query(10, ge=1, le=200),
    page: int = Query(1, ge=1),
    include_directories: bool = False,
    #--- optional filters -----
    username: str | None = Query(None, description="Filter proposals by username (must be in proposal users)"),
    current_cycle_only: bool = Query(False, description="Restrict to current operating cycle"),
    saf_status: list[str] = Query(default=[] , description="Filter SAFs by status e.g. approved, expired"),
    
):
    current_cycle = None
    if current_cycle_only:
        
        current_cycle = await facility_service.current_operating_cycle(FacilityName.nsls2)
        if not current_cycle:
            raise HTTPException(status_code=404, detail="No current operating cycle found")
        cycle = [current_cycle]


    proposal_list = await proposal_service.fetch_proposals(
        proposal_id=proposal_id,
        beamline=beamline,
        cycle=cycle,
        facility=facility,
        page_size=page_size,
        page=page,
        include_directories=include_directories,
        username=username,
    )
    
    # Post-filter block runs if optional params are provided
    if username or current_cycle_only or saf_status:
    
        allowed_statuses = {s.strip().lower() for s in saf_status}
        allowed_instruments = {i.upper() for i in beamline}
        filtered = []

        for proposal in proposal_list:
            # Current cycle strict display
            if current_cycle_only:
                proposal.cycles = [current_cycle]

            # SAF filter
            if allowed_statuses or allowed_instruments:
                proposal.safs = [
                    s for s in (proposal.safs or [])
                    if s.saf_id
                    and (not allowed_statuses or (s.status or "").strip().lower() in allowed_statuses)
                    and (not allowed_instruments or any(
                        i.upper() in allowed_instruments for i in (s.instruments or [])
                    ))
                ]

            filtered.append(proposal)
        
        proposal_list = filtered

    response_model = {
        "proposals": proposal_list,
        "page_size": page_size,
        "page": page,
        "count": len(proposal_list),
    }

    return response_model



@router.get(
    "/proposals/data-sessions",
    response_model=ProposalIdDataSessionList,
    dependencies=[Depends(validate_admin_role)],
    description="Return proposal_ids and their data_sessions for matching proposals.",
)
async def get_proposals_data_sessions(
    proposal_id: Annotated[list[str], Query()] = [],
    beamline: Annotated[list[str], Query()] = [],
    cycle: Annotated[list[str], Query()] = [],
    facility: Annotated[list[FacilityName], Query()] = [FacilityName.nsls2],
    page_size: int = Query(10, ge=1, le=200),
    page: int = Query(1, ge=1),
):
    proposals = await proposal_service.fetch_data_sessions(
        proposal_id=proposal_id,
        beamline=beamline,
        cycle=cycle,
        facility=facility,
        page_size=page_size,
        page=page
    )

    response_model = {
        "proposals": proposals,
        "page_size": page_size,
        "page": page,
        "count": len(proposals),
    }
    return response_model


@router.get("/proposal/saf/{saf_id}", response_model=SingleProposal)
async def get_proposal_by_saf(saf_id: str):
    try:
        proposal = await proposal_service.proposal_by_saf_id(saf_id)
    except LookupError as e:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND, detail=e.args[0]
        )
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while fetching proposal by Proposal ID: {e}"
        )
        raise HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred.",
        )

    response_model = SingleProposal(proposal=proposal)
    return response_model


@router.get("/proposal/{proposal_id}", response_model=SingleProposal)
async def get_proposal(proposal_id: str):
    try:
        proposal = await proposal_service.proposal_by_id(proposal_id)
    except LookupError as e:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND, detail=e.args[0]
        )
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while fetching proposal by SAF ID: {e}"
        )
        raise HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred.",
        )

    response_model = SingleProposal(proposal=proposal)
    return response_model


@router.get("/proposal/{proposal_id}/users", response_model=ProposalUserList)
async def get_proposals_users(proposal_id: str):
    try:
        users = await proposal_service.fetch_users_on_proposal(proposal_id)
        if users is None:
            raise HTTPException(
                fastapi.status.HTTP_404_NOT_FOUND,
                detail=f"Users not found for proposal {proposal_id}",
            )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=e.args[0])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

    response_model = ProposalUserList(
        proposal_id=str(proposal_id), users=users, count=len(users)
    )
    return response_model


@router.get(
    "/proposal/{proposal_id}/principal-investigator", response_model=ProposalUser
)
async def get_proposal_principal_investigator(proposal_id: str):
    try:
        principal_investigator = await proposal_service.pi_from_proposal(proposal_id)
        if len(principal_investigator) == 0:
            # We need a PI for every proposal
            raise HTTPException(
                status_code=fastapi.status.HTTP_404_NOT_FOUND,
                detail=f"PI not found for proposal {proposal_id}",
            )
        elif len(principal_investigator) > 1:
            # We should only have 1 PI
            raise HTTPException(
                status_code=fastapi.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Proposal {proposal_id} contains more than one PI",
            )
    except LookupError as e:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND, detail=e.args[0]
        )
    except Exception as e:
        raise HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {e}",
        )

    response_model = ProposalUser(
        proposal_id=str(proposal_id), user=principal_investigator[0]
    )
    return response_model


@router.get("/proposal/{proposal_id}/usernames", response_model=UsernamesList)
async def get_proposal_usernames(proposal_id: str):
    try:
        # Check to see if proposal exists
        if not await proposal_service.exists(proposal_id):
            raise HTTPException(
                status_code=fastapi.status.HTTP_404_NOT_FOUND,
                detail=f"Proposal {proposal_id} not found",
            )
    except LookupError as e:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND, detail=e.args[0]
        )
    except Exception as e:
        raise HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {e}",
        )

    proposal_usernames = await proposal_service.fetch_usernames_from_proposal(
        proposal_id
    )

    proposal_groupname = proposal_service.generate_data_session_for_proposal(
        proposal_id
    )

    response_model = UsernamesList(
        usernames=proposal_usernames,
        groupname=proposal_groupname,
        proposal_id=str(proposal_id),
        count=len(proposal_usernames),
    )
    return response_model


@router.get("/proposal/{proposal_id}/directories")
async def get_proposal_directories(proposal_id: str) -> ProposalDirectoriesList:
    try:
        directories = await proposal_service.directories(proposal_id)
        if directories is None:
            raise HTTPException(
                status_code=fastapi.status.HTTP_404_NOT_FOUND,
                detail=f"Directories not found for proposal {proposal_id}",
            )
    except LookupError as e:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND, detail=e.args[0]
        )
    except Exception as e:
        raise HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {e}",
        )

    response_model = ProposalDirectoriesList(
        directories=directories,
        directory_count=len(directories),
    )
    return response_model


@router.get("/proposal/{proposal_id}/slack-channels")
async def get_slack_channels_for_proposal(
    proposal_id: str,
) -> list[SlackConversation]:
    try:
        channels = await proposal_service.slack_channels_for_proposal(proposal_id)
        if channels is None:
            raise HTTPException(
                status_code=fastapi.status.HTTP_404_NOT_FOUND,
                detail=f"Slack channels not found for proposal {proposal_id}",
            )
    except LookupError as e:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND, detail=e.args[0]
        )
    except Exception as e:
        raise HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {e}",
        )

    logger.info(f"Slack conversations for proposal {channels}")

    conversations = [
        get_conversation_details(channel.channel_id) for channel in channels
    ]

    logger.info(conversations)
    return conversations


@router.post(
    "/proposal/{proposal_id}/slack-channels",
    dependencies=[Depends(validate_admin_role)],
)
async def create_slack_channels_for_proposal(
    proposal_id: str,
) -> list[ProposalSlackChannel]:
    # Let's check that the proposal actually exists first
    proposal = await proposal_service.proposal_by_id(proposal_id)
    if proposal is None:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"Proposal {proposal_id} not found",
        )

    channels = await slack_service.create_proposal_channels(proposal_id)

    slack_channels = [
        SlackChannel(
            channel_id=proposal_channel.channel_id,
            channel_name=proposal_channel.channel_name,
        )
        for proposal_channel in channels
    ]
    proposal.slack_channels = slack_channels
    proposal.last_updated = datetime.datetime.now()
    await proposal.save()  # noqa - we don't need to specify any args here

    return channels
