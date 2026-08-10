import datetime

import beanie
import pydantic


class Facility(beanie.Document):
    name: str
    facility_id: str
    fullname: str
    pass_facility_id: str | None = None
    data_admins: list[str] | None = []
    data_admin_group: str | None = None
    created_on: datetime.datetime = pydantic.Field(
        default_factory=datetime.datetime.now
    )
    last_updated: datetime.datetime = pydantic.Field(
        default_factory=datetime.datetime.now
    )

    class Settings:
        name = "facilities"
        indexes = []
