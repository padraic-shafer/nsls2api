import asyncio

import fastapi
from fastapi import HTTPException, Request, Header

from nsls2api.api.models.person_model import DataSessionAccess, LDAPUserResponse, Person
from nsls2api.infrastructure.security import get_settings
from nsls2api.services import (
    bnlpeople_service,
    person_service,
)
from nsls2api.services.ldap_service import get_user_info, shape_ldap_response

router = fastapi.APIRouter()


@router.get("/person/username/{username}", response_model=Person)
async def get_person_from_username(username: str):
    bnl_person = await bnlpeople_service.get_person_by_username(username)
    print(bnl_person)
    if bnl_person:
        person = Person(
            firstname=bnl_person.FirstName,
            lastname=bnl_person.LastName,
            email=bnl_person.BNLEmail,
            bnl_id=bnl_person.EmployeeNumber,
            institution=bnl_person.Institution,
            username=bnl_person.ActiveDirectoryName,
            cyber_agreement_signed=bnl_person.CyberAgreementSigned,
        )
        # If the person is an Employee then set their institution to BNL
        if (
            bnl_person.EmployeeStatus == "Active"
            and bnl_person.EmployeeType == "Employee"
        ):
            person.bnl_employee = True
            person.institution = "Brookhaven National Laboratory"
        return person
    else:
        return fastapi.responses.JSONResponse(
            {"error": f"No people with username {username} found."},
            status_code=404,
        )


@router.get("/person/email/{email}")
async def get_person_from_email(email: str):
    bnl_person = await bnlpeople_service.get_person_by_email(email)
    if bnl_person:
        person = Person(
            firstname=bnl_person.FirstName,
            lastname=bnl_person.LastName,
            email=bnl_person.BNLEmail,
            bnl_id=bnl_person.EmployeeNumber,
            institution=bnl_person.Institution,
            username=bnl_person.ActiveDirectoryName,
            cyber_agreement_signed=bnl_person.CyberAgreementSigned,
        )
        return person
    else:
        return fastapi.responses.JSONResponse(
            {"error": f"No people with username {email} found."},
            status_code=404,
        )


# TODO: Add back into schema if we decide to use this endpoint.
@router.get("/person/department/{department}", include_in_schema=False)
async def get_person_by_department(department_code: str = "PS"):
    bnl_people = await bnlpeople_service.get_people_by_department(department_code)
    if bnl_people:
        return bnl_people


# TODO: Add back into schema if we decide to use this endpoint.
@router.get("/person/me", include_in_schema=True)
async def get_myself(upn: str = Header(...)):
    # upn: User principal name
    if not upn:
        raise HTTPException(status_code=400, detail="upn not found")
    settings = get_settings()
    ldap_info = await asyncio.to_thread(
        get_user_info,
        upn,
        settings.ldap_server,
        settings.ldap_base_dn,
        settings.ldap_bind_user,
        settings.ldap_bind_password,
    )
    if not ldap_info:
        raise HTTPException(status_code=404, detail="User not found in LDAP")

    shaped_info = shape_ldap_response(ldap_info)
    return LDAPUserResponse(**shaped_info)


@router.get("/data-session/{username}", response_model=DataSessionAccess, tags=["data"])
@router.get(
    "/data_session/{username}",
    response_model=DataSessionAccess,
    tags=["data"],
    include_in_schema=True,
    description="Deprecated endpoint included for Tiled compatibility.",
    deprecated=True,
    operation_id="get_data_session_by_username_v1_deprecated_endpoint",
)
async def get_data_sessions_by_username(username: str):
    data_access = await person_service.data_sessions_by_username(username)
    return data_access
