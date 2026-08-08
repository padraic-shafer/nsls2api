import datetime

import pydantic


class BNLPerson(pydantic.BaseModel):
    ActiveDirectoryName: str | None = None
    AltEmail: str | None = None
    AppointmentEndDate: str | None = None
    BNLEmail: str | None = None
    BNLExtension: str | None = None
    BNLFax: str | None = None
    BNLPager: str | None = None
    BNLStreet: str | None = None
    IsUSCitizen: bool | None = None
    CyberAgreementSigned: str | None = None
    DeliveryOffice: str | None = None
    DepartmentCode: str | None = None
    DepartmentId: int | None = None
    DepartmentName: str | None = None
    DisplayContactInformation: bool | None = None
    EmployeeNumber: str | None = None
    EmployeeStatus: str | None = None
    EmployeeType: str | None = None
    Facility: str | None = None
    FacilityCode: str | None = None
    FirstName: str | None = None
    Institution: str | None = None
    LastName: str | None = None
    ManagerEmail: str | None = None
    ManagerEmployeeNumber: str | None = None
    ManagerFirstName: str | None = None
    ManagerLastName: str | None = None
    TermDate: str | None = None
    TimeStamp: str | None = None


class ActiveDirectoryUser(pydantic.BaseModel):
    sAMAccountName: str | None = None
    distinguishedName: str | None = None
    displayName: str | None = None
    employeeID: str | None = None
    mail: str | None = None
    description: str | None = None
    userPrincipalName: str | None = None
    pwdLastSet: str | None = None
    userAccountControl: str | None = None
    lockoutTime: str | None = None
    set_passwd: bool | None = None
    locked: bool | None = None
    was_locked: bool | None = None


class ActiveDirectoryUserGroups(pydantic.BaseModel):
    sAMAccountName: str | None = None
    distinguishedName: str | None = None
    member: list[str] | None = None
    memberOf: list[str] | None = None


class Person(pydantic.BaseModel):
    firstname: str
    lastname: str
    email: str
    username: str
    bnl_id: str | None
    bnl_employee: bool | None = None
    institution: str | None = None
    orcid: str | None = None
    globus_username: str | None = None
    pass_unique_id: str | None = None
    account_locked: bool | None = None
    cyber_agreement_signed: datetime.datetime | None = None
    facility_code: str | None = None
    facility_name: str | None = None
    citizenship: str | None = None


class PersonSummary(pydantic.BaseModel):
    firstname: str
    lastname: str
    email: str
    username: str
    institution: str


class DataAdmins(pydantic.BaseModel):
    nsls2_dataadmin: bool = False
    lbms_dataadmin: bool = False
    dataadmin: list | None = None


class DataSessionAccess(pydantic.BaseModel):
    facility_all_access: list[str] = None
    beamline_all_access: list[str] = None
    data_sessions: list[str] = None


class UnixInfo(pydantic.BaseModel):
    uid: str | None = None
    uidNumber: str | None = None
    gidNumber: str | None = None
    homeDirectory: str | None = None
    loginShell: str | None = None


class IdentityInfo(pydantic.BaseModel):
    displayName: str | None = None
    email: str | None = None
    department: str | None = None
    manager: str | None = None
    unix: UnixInfo | None = None


class AccountInfo(pydantic.BaseModel):
    accountExpires: str | None = None
    badPasswordTime: str | None = None
    badPwdCount: int = 0
    pwdLastSet: str | None = None
    lastLogon: str | None = None
    userAccountControlFlags: list[str] = pydantic.Field(default_factory=list)
    userPrincipalName: str | None = None
    logonCount: int = 0
    sAMAccountName: str | None = None
    sAMAccountType: str | None = None
    lastLogoff: str | None = None
    uSNCreated: int | None = None
    uSNChanged: int | None = None


class DirectoryInfo(pydantic.BaseModel):
    objectGUID: str | None = None
    objectSid: str | None = None
    primaryGroupID: str | None = None
    distinguishedName: str | None = None
    whenCreated: str | None = None
    whenChanged: str | None = None


class AttributesInfo(pydantic.BaseModel):
    sn: str | None = None
    givenName: str | None = None
    description: str | None = None
    gecos: str | None = None
    street: str | None = None
    codePage: str | None = None
    countryCode: str | None = None
    instanceType: str | None = None
    objectClass: list[str] = pydantic.Field(default_factory=list)


class LDAPUserResponse(pydantic.BaseModel):
    """Complete LDAP user data from direct LDAP query"""

    dn: str | None = None
    status: str = "Read"
    readTime: str | None = None
    identity: IdentityInfo | None = None
    account: AccountInfo | None = None
    directory: DirectoryInfo | None = None
    groups: list[str] = pydantic.Field(default_factory=list)
    attributes: AttributesInfo | None = None
