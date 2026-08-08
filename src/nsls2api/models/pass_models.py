
import pydantic
from pydantic import ConfigDict


class PassPerson(pydantic.BaseModel):
    """
    This class represents PASS's representation of a Person (e.g. PI or Creator).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    Can_Edit: bool | None = None
    Can_Read: bool | None = None
    CoPI: bool | None = None
    On_Site: bool | None = None
    Pool_ID: int | None = None
    Proposal_ID: int | None = None
    User_ID: int | None = None
    Account: str | None = None
    BNL_ID: str | None = None
    Email: str | None = None
    First_Name: str | None = None
    Last_Name: str | None = None
    User_Facility_ID: str | None = None
    ORCID_ID: str | None = None


class PassAllocation(pydantic.BaseModel):
    """
    This class represents PASS's representation of an Allocation.
    """

    Expired: bool | None = None
    Expiration_Date: str | None = None
    Allocated_Proposal_Type_ID: int | None = None
    Created_Proposal_Type_ID: int | None = None
    Creator_User_ID: int | None = None
    Cycle_Request_ID: int | None = None
    Proposal_ID: int | None = None
    PI_User_ID: int | None = None
    PRP_Hours_Recommended: float | None = None
    Total_Hours_Requested: float | None = None
    Total_Hours_Awarded: float | None = None
    Allocated_Proposal_Type_Description: str | None = None
    Beamline_Description: str | None = None
    Comments: str | None = None
    Created_Proposal_Type_Description: str | None = None
    Cycle_Requested_Description: str | None = None
    Short_Name: str | None = None
    Title: str | None = None
    User_Facility_ID: str | None = None
    Creator: PassPerson | None = None
    PI: PassPerson | None = None


class PassCycle(pydantic.BaseModel):
    """
    This class represents PASS's representation of a Cycle.
    """

    Active: bool | None = None
    ID: int | None = None
    Year: int | None = None
    Start_Date: str | None = None
    End_Date: str | None = None
    Name: str | None = None
    Description: str | None = None
    User_Facility_ID: str | None = None


class PassExperimenter(pydantic.BaseModel):
    """
    This class represents PASS's representation of an Experimenter.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    Can_Edit: bool | None = None
    Can_Read: bool | None = None
    CoPI: bool | None = None
    On_Site: bool | None = None
    Remote_Access: bool | None = None
    Mail_In: bool | None = None
    Off_Site: bool | None = None
    Pool_ID: int | None = None
    Proposal_ID: int | None = None
    User_ID: int | None = None
    Account: str | None = None
    BNL_ID: str | None = None
    Email: str | None = None
    First_Name: str | None = None
    Last_Name: str | None = None
    User_Facility_ID: str | None = None
    ORCID_ID: str | None = None


class PassResource(pydantic.BaseModel):
    """
    This class represents PASS's representation of a Resource.
    """

    ID: int | None = None
    Description: str | None = None
    User_Facility_ID: str | None = None
    Short_Name: str | None = None


class PassProposalType(pydantic.BaseModel):
    """
    This class represents PASS's representation of a ProposalType.
    """

    ID: int | None = None
    Code: str | None = None
    Description: str | None = None
    User_Facility_ID: str | None = None


class PassProposal(pydantic.BaseModel):
    """
    This class represents PASS's representation of a Proposal.
    """

    Expired: bool | None = None
    Expiration_Date: str | None = None
    Creator_User_ID: int | None = None
    Proposal_ID: int | None = None
    Proposal_Type_ID: int | None = None
    PI_User_ID: int | None = None
    Proposal_Type_Description: str | None = None
    Title: str | None = None
    User_Facility_ID: str | None = None
    Creator: PassPerson | None = None
    PI: PassPerson | None = None
    Experimenters: list[PassExperimenter] | None = []
    Resources: list[PassResource] | None = []


class PassScheduledTimeSFTK(pydantic.BaseModel):
    """
    This class represents PASS's representation of a ScheduledTimeSFTK.
    """

    ProposalID: int | None = None
    CycleRequestedID: int | None = None
    ResourceID: int | None = None
    UserFacilityID: str | None = None
    ExtSchedulerRecordID: str | None = None
    ScheduledHoursDuration: float | None = None
    StartTime: str | None = None
    StopTime: str | None = None
    AddedModifiedByUserID: int | None = None
    DateAddedModified: str | None = None


class PassSaf(pydantic.BaseModel):
    """
    This class represents PASS's representation of a SAF.
    """

    SAF_ID: int | None = None
    Date_Expires: str | None = None
    Status: str | None = None
    Experimenters: list[PassExperimenter] | None = []
    Resources: list[PassResource] | None = []
