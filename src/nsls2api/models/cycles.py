import datetime

import beanie
import pydantic


class Cycle(beanie.Document):
    name: str
    accepting_proposals: bool | None = False
    is_current_operating_cycle: bool | None = False
    active: bool | None = False
    end_date: datetime.datetime | None
    facility: str
    pass_description: str | None
    pass_id: str | None
    start_date: datetime.datetime | None
    year: str
    proposals: list[str] | None = []
    created_on: datetime.datetime = pydantic.Field(
        default_factory=datetime.datetime.now
    )
    last_updated: datetime.datetime = pydantic.Field(
        default_factory=datetime.datetime.now
    )

    class Settings:
        name = "cycles"
        indexes = []
