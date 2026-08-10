from datetime import datetime
from enum import StrEnum

import pydantic


class FacilityName(StrEnum):
    nsls2 = "nsls2"
    lbms = "lbms"
    cfn = "cfn"


class FacilityCyclesResponseModel(pydantic.BaseModel):
    facility: str
    cycles: list[str]


class FacilityCurrentOperatingCycleResponseModel(pydantic.BaseModel):
    facility: str
    cycle: str


class FacilityCycleDetailsResponseModel(pydantic.BaseModel):
    facility: str
    cycle: str
    start_date: datetime | None = None
    end_date: datetime | None = None
    is_current_operating_cycle: bool
    accepting_proposals: bool | None = None
