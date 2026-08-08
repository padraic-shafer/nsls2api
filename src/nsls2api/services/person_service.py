# Helper and utility functions for people/users

from nsls2api.api.models.person_model import (
    ActiveDirectoryUser,
    DataSessionAccess,
    Person,
    PersonSummary,
)
from nsls2api.services import (
    beamline_service,
    bnlpeople_service,
    facility_service,
    n2sn_service,
    proposal_service,
)
from nsls2api.services.pass_service import get_proposals_by_person


async def summary_details_by_username(username: str) -> PersonSummary | None:
    diag_person = await diagnostic_details_by_username(username)
    # Now lets return a Person that only contains a limited
    person = PersonSummary(
        firstname=diag_person.firstname,
        lastname=diag_person.lastname,
        email=diag_person.email,
        username=username,
        institution=diag_person.institution,
    )
    return person


async def diagnostic_details_by_username(username: str) -> Person | None:
    try:
        bnl_person = await bnlpeople_service.get_person_by_username(username)
        ad_person: ActiveDirectoryUser = await n2sn_service.get_user_by_username(
            username
        )
        ad_groups = await n2sn_service.get_groups_by_username(username)
        proposals = await get_proposals_by_person(bnl_person.EmployeeNumber)
    except LookupError as error:
        raise LookupError(
            f"Error obtaining diagnostic details for username of {username}"
        ) from error

    print(bnl_person)
    print("-------")

    print(ad_person)
    print("-------")

    print(ad_groups)
    print("-------")

    print(proposals)
    print("-------")

    person = Person(
        firstname=bnl_person.FirstName,
        lastname=bnl_person.LastName,
        email=ad_person.mail,
        username=username,
        institution=bnl_person.Institution,
        bnl_id=bnl_person.EmployeeNumber,
        account_locked=ad_person.locked,
        cyber_agreement_signed=bnl_person.CyberAgreementSigned,
        facility_code=bnl_person.FacilityCode,
        facility_name=bnl_person.Facility,
    )

    # If the person is an Employee then set their institution to BNL
    if bnl_person.EmployeeStatus == "Active" and bnl_person.EmployeeType == "Employee":
        person.bnl_employee = True
        person.institution = "Brookhaven National Laboratory"

    return person


async def data_sessions_by_username(username: str):
    print(f"Looking up if {username} has any special access")

    facility_admin = await facility_service.data_roles_by_user(username)
    beamline_admin = await beamline_service.data_roles_by_user(username)
    data_session_list = await proposal_service.fetch_data_sessions_for_username(
        username
    )

    data_access = DataSessionAccess(
        data_sessions=data_session_list,
        facility_all_access=facility_admin,
        beamline_all_access=beamline_admin,
    )

    return data_access
