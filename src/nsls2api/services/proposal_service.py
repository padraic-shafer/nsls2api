import datetime
import random
from pathlib import Path
from typing import Optional

from beanie.odm.operators.find.array import ElemMatch
from beanie.operators import And, In, Or, RegEx, Text
from faker import Faker
from faker.providers import date_time, python

from nsls2api.api.models.facility_model import FacilityName
from nsls2api.api.models.proposal_model import (
    CommissioningProposalsList,
    LockedProposalsList,
    ProposalChangeResultsList,
    ProposalDiagnostics,
    ProposalFullDetails,
    ProposalsToChangeList,
    ProposalIdDataSession
)
from nsls2api.infrastructure.logging import logger
from nsls2api.models.cycles import Cycle
from nsls2api.models.proposal_types import ProposalType
from nsls2api.models.proposals import Proposal, ProposalIdView, User
from nsls2api.models.slack_models import SlackChannel, SlackChannelToCreate
from nsls2api.services import (
    beamline_service,
    bnlpeople_service,
    facility_service,
    pass_service,
)


async def get_locked_proposals(
    cycles: list[str],
    beamlines: list[str],
    page_size: int = 10,
    page: int = 1,
) -> LockedProposalsList:
    locked_proposals = None
    uppercase_beamline = []
    if beamlines:
        uppercase_beamline = [beamline.upper() for beamline in beamlines]

    if cycles and beamlines:
        query = And(
            Proposal.locked == True,
            In(Proposal.instruments, uppercase_beamline),
            In(Proposal.cycles, cycles),
        )

    elif cycles:
        query = And(
            Proposal.locked == True,
            In(Proposal.cycles, cycles),
        )

    elif beamlines:
        query = And(
            Proposal.locked == True,
            In(Proposal.instruments, uppercase_beamline),
        )
    else:
        query = Proposal.locked == True

    locked_proposals = (
        await Proposal.find_many(query)
        .limit(page_size)
        .skip(page_size * (page - 1))
        .to_list()
    )
    locked_model = LockedProposalsList(
        count=len(locked_proposals),
        locked_proposals=locked_proposals,
        page_size=page_size,
        page=page,
    )

    return locked_model


async def lock(proposal_list: ProposalsToChangeList) -> ProposalChangeResultsList:
    successfully_locked_proposals = []
    failed_to_lock_proposals = []
    proposal_ids = proposal_list.proposals_to_change
    for proposal_id in proposal_ids:
        try:
            proposal_object = await proposal_by_id(proposal_id)
            proposal_object.locked = True
            await proposal_object.save()
            successfully_locked_proposals.append(proposal_id)
        except Exception as e:
            failed_to_lock_proposals.append(proposal_id)
            logger.info(f"Unexpected error when locking {proposal_id} {e}")

    locked_info = ProposalChangeResultsList(
        successful_count=len(successfully_locked_proposals),
        successful_proposals=successfully_locked_proposals,
        failed_proposals=failed_to_lock_proposals,
    )

    return locked_info


async def unlock(proposal_list: ProposalsToChangeList) -> ProposalChangeResultsList:
    successfully_unlocked_proposals = []
    failed_to_unlock_proposals = []
    proposal_ids = proposal_list.proposals_to_change
    for proposal_id in proposal_ids:
        try:
            proposal_object = await proposal_by_id(proposal_id)
            proposal_object.locked = False
            await proposal_object.save()
            successfully_unlocked_proposals.append(proposal_id)
        except Exception as e:
            failed_to_unlock_proposals.append(proposal_id)
            logger.info(f"Unexpected error when unlocking {proposal_id} {e}")

    unlocked_info = ProposalChangeResultsList(
        successful_count=len(successfully_unlocked_proposals),
        successful_proposals=successfully_unlocked_proposals,
        failed_proposals=failed_to_unlock_proposals,
    )

    return unlocked_info


async def exists(proposal_id: str) -> bool:
    proposal = await Proposal.find_one(Proposal.proposal_id == str(proposal_id))
    return False if proposal is None else True


async def proposal_count() -> int:
    return await Proposal.count()


async def recently_updated(count=5, beamline: str | None = None):
    """
    Function to fetch recently updated proposals.

    :param beamline:
    :param count: Specifies the number of recently updated proposals to fetch. Defaults to 5.
    :type count: int

    :return: List of recently updated proposals.
    :rtype: list[Proposal]

    Args:
        beamline: Optional beamline to restrict list of proposals for.
    """
    if beamline:
        # Ensure we match the case in the database for the beamline name
        beamline = beamline.upper()
        # print(f"Searching for proposals within {beamline}...")
        query = In(Proposal.instruments, [beamline])
        updated = (
            await Proposal.find_many(query)
            .sort(-Proposal.last_updated)
            .limit(count)
            .to_list()
        )
    else:
        updated = (
            await Proposal.find_many()
            .sort(-Proposal.last_updated)
            .limit(count)
            .to_list()
        )
    return updated


# async def fetch_proposals_for_cycle(cycle: str) -> list[str]:
#     proposals = await Proposal.find(In(Proposal.cycles, [cycle])).to_list()
#     result = [u.proposal_id for u in proposals if u.proposal_id is not None]
#     return result


async def fetch_proposals_for_cycle(
    cycle_name: str, facility_name: FacilityName = FacilityName.nsls2
) -> list[str]:
    cycle = await Cycle.find_one(
        Cycle.name == cycle_name, Cycle.facility == facility_name
    )
    if cycle is None:
        raise LookupError(f"Cycle {cycle} not found in local database.")

    # Return an empty list if cycle.proposals is None to ensure a consistent return type.
    return cycle.proposals or []


async def fetch_data_sessions_for_username(username: str) -> list[str]:
    proposals = await Proposal.find(
        ElemMatch(Proposal.users, {"username": username})
    ).to_list()
    data_sessions = [p.data_session for p in proposals if p.data_session is not None]
    return data_sessions


def generate_data_session_for_proposal(proposal_id: str) -> str:
    """
    Generate a data session name for a given proposal ID.

    Args:
        proposal_id (str): The ID of the proposal.

    Returns:
        str: The generated data session name.
    """
    return f"pass-{str(proposal_id)}"


async def get_beamline_specific_slack_channel_for_proposal(
    proposal_id: str,
) -> list[str]:
    beamline_channels = []
    for beamline in await beamlines_for_proposal(proposal_id):
        channel_name = (
            f"{generate_data_session_for_proposal(proposal_id)}-{beamline.lower()}"
        )
        beamline_channels.append(channel_name)
    return beamline_channels


async def get_slack_channels_to_create_for_proposal(
    proposal_id: str, separate_chat_channel=True
) -> list[SlackChannelToCreate]:
    channel_list = []

    beamline_list = await beamlines_for_proposal(proposal_id)
    channel_base_name = generate_data_session_for_proposal(proposal_id).lower()

    common_topic_text = f"Discussion channel for proposal {proposal_id}"

    # Set the channel purpose to include the PI and proposal title
    # (if we have multiple PIs, just use the first one)
    try:
        proposal_pi: list[User] = await pi_from_proposal(proposal_id)
    except LookupError:
        # If no PI exists then just use insert an "Unknown" one.
        proposal_pi = [
            User(first_name="Unknown", last_name="Unknown", email="unknown@example.com")
        ]

    proposal_title = (await proposal_by_id(proposal_id)).title
    common_topic_text = (
        f"for proposal {proposal_id}"
        f" - PI: {proposal_pi[0].first_name} {proposal_pi[0].last_name}"
        f" - Title: {proposal_title}"
    )

    # The generic channel is the one that all beamlines (staff and bots) can post to
    generic_channel = SlackChannelToCreate(
        channel_name=channel_base_name,
        proposal_id=proposal_id,
        beamlines=beamline_list,
        topic=f"Discussion channel {common_topic_text}",
    )
    channel_list.append(generic_channel)

    # If we want a separate chat channel, then we need to create channels
    # for each beamline to post their messages.
    if separate_chat_channel:
        for beamline in beamline_list:
            channel_name = f"{channel_base_name}-{beamline}".lower()
            beamline_channel = SlackChannelToCreate(
                channel_name=channel_name,
                proposal_id=proposal_id,
                beamlines=[beamline],
                topic=f"{beamline.upper()} Beamline notifications {common_topic_text}",
            )
            channel_list.append(beamline_channel)

    return channel_list


async def proposal_by_id(proposal_id: str) -> Proposal:
    """
    Retrieve a single proposal by its ID.

    :param proposal_id: The ID of the proposal to retrieve.
    :return: The proposal if found otherwise, this function throws a LookupError.
    """

    proposal: Proposal = await Proposal.find_one(
        Proposal.proposal_id == str(proposal_id)
    )

    if proposal is None:
        raise LookupError(f"Could not find a proposal with an ID of {proposal_id}")

    return proposal


async def proposal_by_saf_id(saf_id: str) -> Proposal:
    """
    Retrieve a single proposal by its SAF ID.

    :param saf_id: The SAF ID of the proposal to retrieve.
    :return: The proposal if found otherwise, this function throws a LookupError.
    """

    proposal: Proposal = await Proposal.find_one(
        ElemMatch(Proposal.safs, {"saf_id": str(saf_id)})
    )

    if proposal is None:
        raise LookupError(f"Could not find a proposal with an SAF ID of {saf_id}")

    return proposal


# Get a list of proposals that match the search criteria
async def search_proposals(search_text: str) -> Optional[list[Proposal]]:
    query = Text(search=search_text, case_sensitive=False)

    if len(search_text) < 3:
        return []

    logger.debug(f"Searching for '{search_text}'")

    # Not sure we need to sort here - but hey why not!
    found_proposals = (
        await Proposal.find(query).sort([("score", {"$meta": "textScore"})]).to_list()
    )

    logger.info(
        f"Found {len(found_proposals)} proposals by search for the text '{search_text}'"
    )

    # Now do a special search just for the proposal id
    found_proposals += await Proposal.find(
        RegEx(Proposal.proposal_id, pattern=f"{search_text}")
    ).to_list()

    logger.info(
        f"Found {len(found_proposals)} proposals  after searching for '{search_text}' in just the proposal_id field"
    )

    return found_proposals


# Get a list of proposals that match the given criteria
async def fetch_proposals(
    proposal_id: list[str] | None = None,
    beamline: list[str] | None = None,
    cycle: list[str] | None = None,
    facility: list[str] | None = None,
    username: str | None = None,
    saf_status: list[str] | None = None,
    page_size: int = 10,
    page: int = 1,
    include_directories: bool = False,

) -> Optional[list[ProposalFullDetails]]:
    query = []
    saf_status_upper: list[str] = []

    
    if beamline:
        beamline_upper = [beamline_name.upper() for beamline_name in beamline]
        query.append(In(Proposal.instruments, beamline_upper))

    if cycle:
        query.append(In(Proposal.cycles, cycle))

    if proposal_id:
        query.append(In(Proposal.proposal_id, proposal_id))
        
    if username is not None:
        username = username.strip()
    if username:
        query.append(ElemMatch(Proposal.users, {"username": username}))

    if saf_status:
        saf_status_upper = [s.strip().upper() for s in saf_status if s and s.strip()]
        query.append(
            ElemMatch(
                Proposal.safs,
                {
                    "saf_id": {"$ne": None},
                    "status": {"$in": saf_status_upper},
                }
            )
        )

    if len(query) == 0:
        proposals = (
            await Proposal.find_many()
            .sort(-Proposal.last_updated)
            .limit(page_size)
            .skip(page_size * (page - 1))
            .to_list()
        )
    else:
        proposals = (
            await Proposal.find_many(And(*query))
            .sort(-Proposal.last_updated)
            .limit(page_size)
            .skip(page_size * (page - 1))
            .to_list()
        )

    # Trim SAFs in-memory so response SAFs match requested statuses only.
    if saf_status_upper:
        filtered_proposals = []
        for proposal in proposals:
            proposal.safs = [
                saf
                for saf in (proposal.safs or [])
                if saf.saf_id
                and (saf.status or "").strip().upper() in saf_status_upper
            ]
            if proposal.safs:
                filtered_proposals.append(proposal)
        proposals = filtered_proposals

    # Add directories field to each proposal
    if include_directories:
        detailed_proposals = []
        for proposal in proposals:
            new_proposal = ProposalFullDetails(
                **proposal.model_dump(),
                directories=await directories(proposal.proposal_id),
            )
            detailed_proposals.append(new_proposal)
        return detailed_proposals
    else:
        return proposals

async def fetch_data_sessions(
    proposal_id: list[str] | None = None,
    beamline: list[str] | None = None,
    cycle: list[str] | None = None,
    facility: list[str] | None = None,
    page_size: int = 10,
    page: int = 1,
) -> list[ProposalIdDataSession]:
    """
    Fetch proposal_id and data_session for proposals matching filters.
    Returns a list of ProposalIdDataSession objects.
    """
    query = []

    if beamline:
        beamline_upper = [beamline_name.upper() for beamline_name in beamline]
        query.append(In(Proposal.instruments, beamline_upper))

    if cycle:
        query.append(In(Proposal.cycles, cycle))

    if proposal_id:
        query.append(In(Proposal.proposal_id, proposal_id))

    filter_query = And(*query) if query else {}

    proposals = (
        await Proposal.find_many(
            filter_query,
            projection_model=ProposalIdDataSession
        )
        .sort(-Proposal.last_updated)
        .limit(page_size)
        .skip(page_size * (page - 1))
        .to_list()
    )

    return proposals

async def proposal_type_description_from_pass_type_id(
    pass_type_id: int,
) -> Optional[str]:
    proposal_type = await ProposalType.find_one(
        ProposalType.pass_id == str(pass_type_id)
    )
    if proposal_type is None:
        error_message = f"PASS Proposal type {pass_type_id} not found.  Check that the proposal types have been synchronized."
        logger.error(error_message)
        raise LookupError(error_message)
    else:
        return proposal_type.description


async def data_session_for_proposal(proposal_id: str) -> Optional[str]:
    proposal = await Proposal.find_one(Proposal.proposal_id == str(proposal_id))
    return proposal.data_session


async def beamlines_for_proposal(proposal_id: str) -> Optional[list[str]]:
    proposal = await proposal_by_id(proposal_id)
    return proposal.instruments


async def cycles_for_proposal(proposal_id: str) -> Optional[list[str]]:
    proposal = await proposal_by_id(proposal_id)
    return proposal.cycles


async def slack_channels_for_proposal(proposal_id: str) -> Optional[list[SlackChannel]]:
    proposal = await proposal_by_id(proposal_id)
    return proposal.slack_channels


async def fetch_users_on_proposal(proposal_id: str) -> Optional[list[User]]:
    """
    Fetches the users associated with a given proposal.

    Args:
        proposal_id (int): The ID of the proposal.

    Returns:
        Optional[list[User]]: A list of User objects associated with the proposal, or None if the proposal is not found.
    """
    proposal = await proposal_by_id(proposal_id)
    return proposal.users


async def fetch_usernames_from_proposal(
    proposal_id: str,
) -> Optional[list[str]]:
    proposal = await proposal_by_id(proposal_id)

    if proposal is None:
        raise LookupError(f"Proposal {proposal_id} not found")

    usernames = [u.username for u in proposal.users if u.username is not None]
    return usernames


async def fetch_emails_from_proposal(
    proposal_id: str,
) -> Optional[list[str]]:
    proposal = await proposal_by_id(proposal_id)

    if proposal is None:
        raise LookupError(f"Proposal {proposal_id} not found")

    emails = [u.email for u in proposal.users if u.email is not None]
    return emails


async def safs_from_proposal(proposal_id: str) -> Optional[list[str]]:
    proposal = await proposal_by_id(proposal_id)

    safs = [s.saf_id for s in proposal.safs if s.saf_id is not None]

    return safs


async def pi_from_proposal(proposal_id: str) -> Optional[list[User]]:
    proposal = await proposal_by_id(proposal_id)

    pi = [u for u in proposal.users if u.is_pi]

    if len(pi) == 0:
        raise LookupError(f"Proposal {proposal_id} does not contain any PIs.")
    elif len(pi) > 1:
        raise LookupError(f"Proposal {proposal_id} contains {len(pi)} different PIs.")
    else:
        return pi


# TODO: There seems to be a data integrity issue that not all commissioning proposals have a beamline listed.
async def commissioning_proposals(
    beamline: str | None = None, facility: FacilityName | None = None
) -> CommissioningProposalsList:
    commissioning_proposal_list = []
    proposals = None
    query_on_facility = None
    query_on_beamline = None

    commissioning_proposal_types = (
        await pass_service.get_all_commissioning_proposal_type_ids()
    )

    query = Or(
        *[
            Proposal.pass_type_id == proposal_type
            for proposal_type in commissioning_proposal_types
        ]
    )

    # if there is a beamline specified then this will take precedence
    if beamline:
        # Ensure we match the case in the database for the beamline name
        query_on_beamline = beamline.upper()
        proposals = Proposal.find(In(Proposal.instruments, [query_on_beamline])).find(
            query, projection_model=ProposalIdView
        )

    elif facility:
        # look up the pass proposal type id for commissioning proposals for this facility
        query_on_facility = facility
        proposal_type: ProposalType = (
            await pass_service.get_commissioning_proposal_type(query_on_facility)
        )
        print(f"Found proposal type {proposal_type}")
        if proposal_type:
            proposals = Proposal.find(
                Proposal.pass_type_id == proposal_type.pass_id,
                projection_model=ProposalIdView,
            )
    else:
        proposals = Proposal.find(query, projection_model=ProposalIdView)

    if proposals:
        commissioning_proposal_list = [
            p.proposal_id
            for p in await proposals.to_list()
            if p.proposal_id is not None
        ]

    model = CommissioningProposalsList(
        count=len(commissioning_proposal_list),
        commissioning_proposals=commissioning_proposal_list,
        beamline=query_on_beamline,
        facility=query_on_facility,
    )

    return model


async def has_valid_cycle(proposal: Proposal):
    # If we don't have any cycles listed and this is not a commissioning
    # proposal then the cycle information is invalid
    return (len(proposal.cycles) > 0) or (await is_commissioning(proposal))


async def is_commissioning(proposal: Proposal) -> bool:
    commissioning_proposal_types = (
        await pass_service.get_all_commissioning_proposal_type_ids()
    )
    return proposal.pass_type_id in commissioning_proposal_types


# Return the directories and permissions that should be present for a given proposal
async def directories(proposal_id: str):
    proposal = await proposal_by_id(proposal_id)

    # if any of the following are null or zero length, then we don't have
    # enough information to create any directories
    error_msg = []

    if proposal.data_session is None:
        error_text = (
            f"Proposal {str(proposal.proposal_id)} does not contain a data_session."
        )
        logger.error(error_text)
        error_msg.append(error_text)

    if not await has_valid_cycle(proposal) and not await is_commissioning(proposal):
        error_text = f"Proposal {str(proposal.proposal_id)} does not contain any cycle information."
        logger.error(error_text)
        error_msg.append(error_text)

    if len(proposal.instruments) == 0:
        error_text = (
            f"Proposal {str(proposal.proposal_id)} does not contain any beamlines."
        )
        logger.error(error_text)
        error_msg.append(error_text)

    if len(error_msg) > 0:
        raise Exception(error_msg)

    directory_list = []

    for beamline in proposal.instruments:
        data_root = Path(await beamline_service.data_root_directory(beamline))
        # print(f"Data Root ({beamline}) = {data_root}")

        service_accounts = await beamline_service.service_accounts(beamline)
        # print(f"service_accounts: {service_accounts}")

        if await is_commissioning(proposal):
            cycles = ["commissioning"]
        else:
            cycles = proposal.cycles

        for cycle in cycles:
            beamline_tla = str(beamline).lower()

            users_acl: list[dict[str, str]] = []
            groups_acl: list[dict[str, str]] = []

            users_acl.append({"nsls2data": "rw"})
            users_acl.append({f"{service_accounts.workflow}": "rw"})
            users_acl.append({f"{service_accounts.ioc}": "rw"})

            if service_accounts.bluesky is not None:
                users_acl.append({f"{service_accounts.bluesky}": "r"})
            # If beamline uses SynchWeb then add access for synchweb user
            if await beamline_service.uses_synchweb(beamline_tla):
                users_acl.append({"synchweb": "r"})
            # Add LSDC beamline users for the appropriate beamlines (i.e. if the account is defined)
            if service_accounts.lsdc:
                users_acl.append({f"{service_accounts.lsdc}": "rw"})

            groups_acl.append({str(proposal.data_session): "rw"})
            groups_acl.append({"n2sn-right-dataadmin": "rw"})
            groups_acl.append(
                {f"{await beamline_service.data_admin_group(beamline_tla)}": "rw"}
            )

            directory = {
                "path": str(
                    data_root / "proposals" / str(cycle) / proposal.data_session
                ),
                "beamline": beamline.upper(),
                "cycle": str(cycle),
                "owner": "nsls2data",
                "group": proposal.data_session,
                "users": users_acl,
                "groups": groups_acl,
            }
            directory_list.append(directory)

    return directory_list


async def diagnostic_details_by_id(proposal_id: str) -> Optional[ProposalDiagnostics]:
    proposal = await proposal_by_id(proposal_id)

    if proposal is None:
        raise LookupError(f"Proposal {proposal_id} not found")

    pi = await pi_from_proposal(proposal.proposal_id)

    proposal_diagnostics = ProposalDiagnostics(
        proposal_id=proposal.proposal_id,
        title=proposal.title,
        proposal_type=proposal.type,
        pi=pi[0],
        users=proposal.users,
        data_session=proposal.data_session,
        beamlines=proposal.instruments,
        cycles=proposal.cycles,
        safs=await safs_from_proposal(proposal.proposal_id),
        updated=proposal.last_updated,
    )

    return proposal_diagnostics


async def generate_fake_proposal_id() -> int:
    proposal_id_already_exists = True

    while proposal_id_already_exists:
        fake_proposal_id = random.randint(900000, 999999)
        proposal_id_already_exists = await exists(str(fake_proposal_id))

    return fake_proposal_id


async def generate_fake_test_proposal(
    facility_name: FacilityName = FacilityName.nsls2, add_specific_user=None
) -> Optional[Proposal]:
    """
    Generates a fake test proposal.

    Args:
        facility_name (FacilityName, optional): The name of the facility. Defaults to using the NSLS-II facility.
        add_specific_user (Optional[str], optional): If specified, the username of a specific user to add to the proposal, propagated by the BNL AD. Defaults to None.
    Returns:
        Optional[Proposal]: The generated fake test proposal, or None if an error occurred.
    """
    MAX_USERS_PER_PROPOSAL: int = 9

    number_of_users = random.randint(1, MAX_USERS_PER_PROPOSAL)
    pi_number = random.randint(0, number_of_users - 1)
    user_list = []

    fake = Faker()
    fake.add_provider(python)
    fake.add_provider(date_time)

    # Fake Users
    for i in range(number_of_users):
        if i == pi_number:
            is_pi = True
        else:
            is_pi = False

        if fake.pybool(truth_probability=80) or is_pi:
            user_bnl_id = fake.pystr_format(string_format="??##?").upper()
            # Now only a subset of people with BNL IDs will actually have usernames
            if fake.pybool(truth_probability=80) or is_pi:
                username = fake.user_name()
            else:
                username = None
        else:
            user_bnl_id = None
            username = None

        user = User(
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            email=fake.email(),
            bnl_id=user_bnl_id,
            username=username,
            is_pi=False if isinstance(add_specific_user, str) else is_pi,
        )
        user_list.append(user)

    # Real User(s)
    # If there is a real user, make them the only PI using the above `is_pi` logic.
    if isinstance(add_specific_user, str):
        try:
            person = await bnlpeople_service.get_person_by_username(add_specific_user)
            if person:
                user = User(
                    first_name=person.FirstName,
                    last_name=person.LastName,
                    email=person.BNLEmail,
                    bnl_id=person.EmployeeNumber,
                    username=add_specific_user,
                    is_pi=True,
                )
                user_list.append(user)
        except LookupError:
            logger.error(f"Could not find user {add_specific_user} in BNLPeople.")
            return None

    fake_proposal_id = await generate_fake_proposal_id()
    fake_title = fake.sentence()

    fake_cycle = await facility_service.current_operating_cycle(facility_name)
    if fake_cycle is None:
        # If there is no current operating cycle, then just make one up
        fake_cycle = f"{fake.year()}-{fake.pyint(min_value=1, max_value=3)}"

    proposal = Proposal(
        proposal_id=str(fake_proposal_id),
        title=fake_title,
        type="Fake Test Proposal",
        users=user_list,
        pass_type_id="666666",
        data_session=generate_data_session_for_proposal(str(fake_proposal_id)),
        instruments=["TST"],
        cycles=[fake_cycle],
        last_updated=datetime.datetime.now(),
    )

    await Proposal.insert_one(proposal)

    return proposal
