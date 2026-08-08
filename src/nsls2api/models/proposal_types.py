import datetime

import beanie
import pydantic


class ProposalType(beanie.Document):
    code: str
    facility_id: str | None = None
    description: str | None = None
    pass_id: str | None = None
    pass_description: str | None = None
    created_on: datetime.datetime = pydantic.Field(
        default_factory=datetime.datetime.now
    )
    last_updated: datetime.datetime = pydantic.Field(
        default_factory=datetime.datetime.now
    )

    class Settings:
        name = "proposal_types"
        indexes = []
