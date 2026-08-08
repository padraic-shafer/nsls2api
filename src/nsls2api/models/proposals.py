import datetime

import beanie
import pydantic
import pymongo
from pydantic import ConfigDict

from nsls2api.models.slack_models import SlackChannel


class SafetyForm(pydantic.BaseModel):
    saf_id: str
    status: str
    instruments: list[str] | None


class User(pydantic.BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str
    bnl_id: str | None = None
    username: str | None = None
    is_pi: bool = False
    orcid: str | None = None


# -- Shared Base --
class ProposalBase(pydantic.BaseModel):
    proposal_id: str
    data_session: str
    title: str | None = None
    type: str | None = None
    pass_type_id: str | None = None
    instruments: list[str] | None = []
    cycles: list[str] | None = []
    users: list[User] | None = []
    safs: list[SafetyForm] | None = []
    slack_channels: list[SlackChannel] | None = []
    created_on: datetime.datetime = pydantic.Field(
        default_factory=datetime.datetime.now
    )
    last_updated: datetime.datetime = pydantic.Field(
        default_factory=datetime.datetime.now
    )
    locked: bool | None = False


# -- Pydantic Model for Display/Transport --
class ProposalDisplay(ProposalBase):
    # Prevent unwanted fields (like MongoDB _id) from breaking deserialization
    model_config = ConfigDict(extra="ignore")


# -- Beanie Model for Database --
class Proposal(ProposalBase, beanie.Document):
    class Settings:
        name = "proposals"
        indexes = [
            pymongo.IndexModel(
                keys=[("proposal_id", pymongo.DESCENDING)],
                name="proposal_id_descend",
            ),
            pymongo.IndexModel(
                keys=[("last_updated", pymongo.DESCENDING)],
                name="last_updated_descend",
            ),
            pymongo.IndexModel(
                keys=[("users.username", pymongo.ASCENDING)],
                name="users_username_ascend",
            ),
            pymongo.IndexModel(
                keys=[("users.email", pymongo.ASCENDING)],
                name="users_email_ascend",
            ),
            pymongo.IndexModel(
                keys=[("users.bnl_id", pymongo.ASCENDING)],
                name="users_bnl_id_ascend",
            ),
            pymongo.IndexModel(
                keys=[("users.last_name", pymongo.ASCENDING)],
                name="users_last_name_ascend",
            ),
            pymongo.IndexModel(
                keys=[("safs.saf_id", pymongo.DESCENDING)],
                name="safs_saf_id_descend",
            ),
            pymongo.IndexModel(
                keys=[
                    ("proposal_id", pymongo.TEXT),
                    ("data_session", pymongo.TEXT),
                    ("safs.saf_id", pymongo.TEXT),
                    ("instruments", pymongo.TEXT),
                    ("cycles", pymongo.TEXT),
                    ("title", pymongo.TEXT),
                ],
                name="proposals_full_text",
            ),
        ]


class UsernamesOnly(pydantic.BaseModel):
    username: str

    class Settings:
        projection = {
            "username": "$username",
        }


class ProposalIdView(pydantic.BaseModel):
    proposal_id: str

    class Settings:
        projection = {"proposal_id": "$proposal_id"}
