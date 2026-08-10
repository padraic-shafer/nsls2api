
from pydantic import ValidationError

from nsls2api.api.models.facility_model import FacilityName
from nsls2api.infrastructure import config
from nsls2api.infrastructure.logging import logger
from nsls2api.models.cycles import Cycle
from nsls2api.models.pass_models import (
    PassAllocation,
    PassCycle,
    PassProposal,
    PassProposalType,
    PassSaf,
)
from nsls2api.models.proposal_types import ProposalType
from nsls2api.services import facility_service
from nsls2api.services.helpers import (
    _call_async_webservice_with_client,
    httpx_client_wrapper,
)

settings = config.get_settings()

api_key = settings.pass_api_key
base_url = settings.pass_api_url


class PassException(Exception):
    pass


async def _call_pass_webservice(url: str):
    return await _call_async_webservice_with_client(url, client=httpx_client_wrapper())


async def get_proposal(
    proposal_id: str, facility: FacilityName = FacilityName.nsls2
) -> PassProposal | None:
    pass_facility = await facility_service.pass_id_for_facility(facility)

    if not pass_facility:
        error_message: str = f"Facility {facility} does not have a PASS ID."
        logger.error(error_message)
        raise PassException(error_message)

    url = f"{base_url}/Proposal/GetProposal/{api_key}/{pass_facility}/{proposal_id}"

    try:
        pass_proposal = await _call_pass_webservice(url)
        proposal = PassProposal(**pass_proposal)
    except ValidationError as error:
        error_message = (
            f"Error validating data received from PASS for proposal {proposal_id}."
        )
        logger.error(error_message)
        raise PassException(error_message) from error
    except Exception as error:
        error_message = f"Error retrieving proposal {proposal_id} from PASS."
        logger.exception(error_message)
        raise PassException(error_message) from error

    return proposal


async def get_proposal_types(
    facility: FacilityName = FacilityName.nsls2,
) -> list[PassProposalType] | None:
    pass_facility = await facility_service.pass_id_for_facility(facility)

    if not pass_facility:
        error_message: str = f"Facility {facility} does not have a PASS ID."
        logger.error(error_message)
        raise PassException(error_message)

    url = f"{base_url}/Proposal/GetProposalTypes/{api_key}/{pass_facility}"

    try:
        pass_proposal_types_list = await _call_pass_webservice(url)
        proposal_types = []
        if pass_proposal_types_list and len(pass_proposal_types_list) > 0:
            for proposal_type in pass_proposal_types_list:
                proposal_types.append(PassProposalType(**proposal_type))
    except ValidationError as error:
        error_message = f"Error validating data received from PASS for proposal type for the {facility} facility."
        logger.error(error_message)
        raise PassException(error_message) from error
    except Exception as error:
        error_message = "Error retrieving proposal types from PASS."
        logger.exception(error_message)
        raise PassException(error_message) from error

    return proposal_types


async def get_commissioning_proposal_type(
    facility: FacilityName = FacilityName.nsls2,
) -> ProposalType | None:
    match facility:
        case FacilityName.nsls2:
            # The PASS ID for NSLS-II commissioning proposals is 300005
            proposal = await ProposalType.find_one(ProposalType.pass_id == "300005")
            return proposal
        case FacilityName.lbms:
            # The PASS ID for LBMS commissioning proposals is 300042
            proposal = await ProposalType.find_one(ProposalType.pass_id == "300042")
            return proposal
        case FacilityName.cfn:
            return None
            # We don't have a commissioning proposal type for CFN
        case _:
            raise ValueError(f"Unknown facility: {facility}")


async def get_all_commissioning_proposal_type_ids() -> list[str]:
    """
    Get all the PASS IDs for commissioning proposal types for all facilities.
    Returns:
        list[str]: List of PASS IDs for commissioning proposal types
    """
    commissioning_proposal_types = ["300005", "300042"]
    return commissioning_proposal_types


async def get_saf_from_proposal(
    proposal_id: str, facility: FacilityName = FacilityName.nsls2
) -> list[PassSaf] | None:
    pass_facility = await facility_service.pass_id_for_facility(facility)

    if not pass_facility:
        error_message: str = f"Facility {facility} does not have a PASS ID."
        logger.error(error_message)
        raise PassException(error_message)

    url = f"{base_url}/SAF/GetSAFsByProposal/{api_key}/{pass_facility}/{proposal_id}"
    try:
        pass_saf_list = await _call_pass_webservice(url)
        saf_list = []
        if pass_saf_list and len(pass_saf_list) > 0:
            for saf in pass_saf_list:
                saf_list.append(PassSaf(**saf))
    except ValidationError as error:
        error_message = (
            f"Error validating SAF data received from PASS for proposal {proposal_id}."
        )
        logger.error(error_message)
        raise PassException(error_message) from error
    except Exception as error:
        error_message = f"Error retrieving SAFs for proposal {proposal_id} from PASS."
        logger.exception(error_message)
        raise PassException(error_message) from error

    return saf_list


async def get_commissioning_proposals_by_year(
    year: str, facility_name: FacilityName = FacilityName.nsls2
) -> list[PassProposal] | None:
    pass_facility = await facility_service.pass_id_for_facility(facility_name)
    if not pass_facility:
        error_message: str = f"Facility {facility_name} does not have a PASS ID."
        logger.error(error_message)
        raise PassException(error_message)
    pass_commissioning_type = await get_commissioning_proposal_type(facility_name)
    url = f"{base_url}/Proposal/GetProposalsByType/{api_key}/{pass_facility}/{year}/{pass_commissioning_type.pass_id}/NULL"

    try:
        pass_commissioning_proposals = await _call_pass_webservice(url)
        commissioning_proposal_list = []
        if pass_commissioning_proposals and len(pass_commissioning_proposals) > 0:
            for commissioning_proposal in pass_commissioning_proposals:
                commissioning_proposal_list.append(
                    PassProposal(**commissioning_proposal)
                )
    except ValidationError as error:
        error_message = f"Error validating commissioning proposal data received from PASS for year {year!s} at {facility_name} facility."
        logger.error(error_message)
        raise PassException(error_message) from error
    except Exception as error:
        error_message = f"Error retrieving commissioning proposal information from PASS for year {year!s} at {facility_name} facility."
        logger.exception(error_message)
        raise PassException(error_message) from error

    return commissioning_proposal_list


async def get_pass_resources():
    url = f"{base_url}/Resource/GetResources/{api_key}/NSLS-II"
    resources = await _call_pass_webservice(url)
    return resources


async def get_cycles(
    facility: FacilityName = FacilityName.nsls2,
) -> list[PassCycle] | None:
    pass_facility = await facility_service.pass_id_for_facility(facility)

    if not pass_facility:
        error_message: str = f"Facility {facility} does not have a PASS ID."
        logger.error(error_message)
        raise PassException(error_message)

    url = f"{base_url}/Proposal/GetCycles/{api_key}/{pass_facility}"
    logger.info(f"Getting cycles from PASS for {facility} facility.")

    try:
        pass_cycle_list = await _call_pass_webservice(url)
        cycles = []
        if pass_cycle_list and len(pass_cycle_list) > 0:
            for cycle in pass_cycle_list:
                cycles.append(PassCycle(**cycle))
    except ValidationError as error:
        error_message = f"Error validating cycle data received from PASS for the {facility} facility."
        logger.error(error_message)
        raise PassException(error_message) from error
    except Exception as error:
        error_message = "Error retrieving cycle information from PASS."
        logger.exception(error_message)
        raise PassException(error_message) from error

    return cycles


async def get_proposals_allocated_by_cycle(
    cycle_name: str, facility: FacilityName = FacilityName.nsls2
) -> list[PassAllocation] | None:
    pass_facility = await facility_service.pass_id_for_facility(facility)
    if not pass_facility:
        error_message: str = f"Facility {facility} does not have a PASS ID."
        logger.error(error_message)
        raise PassException(error_message)

    cycle = await Cycle.find_one(Cycle.name == cycle_name, Cycle.facility == facility)
    if not cycle:
        error_message: str = f"Could not find a cycle with the name {cycle_name}."
        logger.error(error_message)
        raise PassException(error_message)

    url = f"{base_url}/Proposal/GetProposalsAllocatedByCycle/{api_key}/{pass_facility}/{cycle.pass_id}/null"

    try:
        pass_allocated_proposals = await _call_pass_webservice(url)
        allocated_proposals = []
        if pass_allocated_proposals and len(pass_allocated_proposals) > 0:
            for allocation in pass_allocated_proposals:
                allocated_proposals.append(PassAllocation(**allocation))
    except ValidationError as error:
        error_message = f"Error validating allocated proposal data received from PASS for the {cycle} cycle at {facility} facility."
        logger.error(error_message)
        raise PassException(error_message) from error
    except Exception as error:
        error_message = f"Error retrieving allocated proposal information from PASS for the {cycle} cycle at {facility} facility."
        logger.exception(error_message)
        raise PassException(error_message) from error

    return allocated_proposals


async def get_proposals_allocated(
    facility: FacilityName = FacilityName.nsls2,
) -> list[PassAllocation] | None:
    pass_facility = await facility_service.pass_id_for_facility(facility)

    if not pass_facility:
        error_message: str = f"Facility {facility} does not have a PASS ID."
        logger.error(error_message)
        raise PassException(error_message)

    url = f"{base_url}/Proposal/GetProposalsAllocated/{api_key}/{pass_facility}"

    try:
        pass_allocated_proposals = await _call_pass_webservice(url)
        allocated_proposals = []
        if pass_allocated_proposals and len(pass_allocated_proposals) > 0:
            for allocation in pass_allocated_proposals:
                allocated_proposals.append(PassAllocation(**allocation))
    except ValidationError as error:
        error_message = f"Error validating allocated proposal data received from PASS at {facility} facility."
        logger.error(error_message)
        raise PassException(error_message) from error
    except Exception as error:
        error_message = f"Error retrieving allocated proposal information from PASS at {facility} facility."
        logger.exception(error_message)
        raise PassException(error_message) from error

    return allocated_proposals


async def get_proposals_by_person(bnl_id: str):
    url = f"{base_url}/Proposal/GetProposalsByPerson/{api_key}/NSLS-II/null/null/{bnl_id}/null"
    print(url)
    proposals = await _call_pass_webservice(url)
    return proposals
