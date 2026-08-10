import datetime

import pydantic

from nsls2api.api.models.facility_model import FacilityName
from nsls2api.models.beamlines import DirectoryGranularity
from nsls2api.models.proposals import Proposal, User


class UsernamesList(pydantic.BaseModel):
    usernames: list[str]
    groupname: str
    proposal_id: str | None
    count: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "groupname": "pass-314159",
                    "usernames": ["rdeckard", "rbatty"],
                    "proposal_id": "666666",
                    "count": 2,
                }
            ]
        }
    }


class CommissioningProposalsList(pydantic.BaseModel):
    count: int
    commissioning_proposals: list[str]
    beamline: str | None = None
    facility: FacilityName | None = None


class LockedProposalsList(pydantic.BaseModel):
    count: int
    locked_proposals: list[Proposal]
    page_size: int | None = None
    page: int | None = None


class CycleProposalList(pydantic.BaseModel):
    cycle: str
    count: int
    proposals: list[str]


class RecentProposal(pydantic.BaseModel):
    proposal_id: str
    title: str
    updated: datetime.datetime
    instruments: list[str] | None


class RecentProposalsList(pydantic.BaseModel):
    count: int
    proposals: list[RecentProposal]


class ProposalSummary(pydantic.BaseModel):
    proposal_id: str
    title: str


class SingleProposal(pydantic.BaseModel):
    proposal: Proposal


class ProposalUserList(pydantic.BaseModel):
    proposal_id: str
    users: list[User]
    count: int


class ProposalUser(pydantic.BaseModel):
    proposal_id: str
    user: User


class ProposalDirectories(pydantic.BaseModel):
    path: str
    owner: str
    group: str | None = None
    beamline: str | None = None
    cycle: str | None = None
    users: list[dict[str, str]]
    groups: list[dict[str, str]]
    directory_most_granular_level: DirectoryGranularity | None = (
        DirectoryGranularity.day
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "path": "/nsls2/xf31id1/2021-2/pass-666666",
                    "owner": "xf31id1",
                    "group": "xf31id1",
                    "beamline": "TST",
                    "cycle": "1066-1",
                    "directory_most_granular_level": "month",
                    "users": [
                        {"name": "xf31id", "permissions": "rw"},
                        {"name": "service-account", "permissions": "rw"},
                    ],
                    "groups": [
                        {"name": "dataadmins", "permissions": "rw"},
                        {"name": "datareaders", "permissions": "r"},
                    ],
                }
            ]
        }
    }


class ProposalDirectoriesList(pydantic.BaseModel):
    directory_count: int
    directories: list[ProposalDirectories]


class ProposalFullDetails(Proposal):
    directories: list[ProposalDirectories] | None = None


class ProposalFullDetailsList(pydantic.BaseModel):
    proposals: list[ProposalFullDetails]
    count: int
    page_size: int | None = None
    page: int | None = None


class ProposalDiagnostics(pydantic.BaseModel):
    proposal_id: str
    proposal_type: str | None
    pi: User | None
    users: list[User] | None
    title: str
    data_session: str | None
    beamlines: list[str] | None
    cycles: list[str] | None
    safs: list[str] | None
    updated: datetime.datetime


class ProposalChangeResultsList(pydantic.BaseModel):
    successful_count: int
    successful_proposals: list[str] | None
    failed_proposals: list[str] | None


class ProposalsToChangeList(pydantic.BaseModel):
    proposals_to_change: list[str]


class ProposalIdDataSession(pydantic.BaseModel):
    proposal_id: str
    data_session: str | None = None


class ProposalIdDataSessionList(pydantic.BaseModel):
    proposals: list[ProposalIdDataSession]
    count: int
    page_size: int
    page: int
