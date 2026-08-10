import datetime
from enum import StrEnum

import beanie
import pydantic
from beanie import Insert, before_event
from pydantic import field_validator


class DirectoryGranularity(StrEnum):
    """
    Represents the granularity options for asset directory YYYY/MM/DD/HH tree structure.
    The value specifies the most granular level to create directories for.  If no date
    structure is wanted, then the value "flat" is used.
    """

    flat = "flat"
    year = "year"
    month = "month"
    day = "day"
    hour = "hour"


class Directory(pydantic.BaseModel):
    path: str
    owner: str
    group: str | None = None
    beamline: str | None = None
    users: list[dict[str, str]]
    groups: list[dict[str, str]]
    directory_most_granular_level: DirectoryGranularity | None = (
        DirectoryGranularity.day
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "directory_count": 1,
                    "directories": [
                        {
                            "path": "assets/detector1",
                            "owner": "nsls2data",
                            "group": "nsls2data",
                            "beamline": "TST",
                            "directory_most_granular_level": "month",
                            "users": [
                                {"softioc-tst": "rw"},
                                {"service-account": "rw"},
                            ],
                            "groups": [
                                {"dataadmins": "rw"},
                                {"datareaders": "r"},
                            ],
                        }
                    ],
                }
            ]
        }
    }


class DirectoryList(pydantic.BaseModel):
    directory_count: int
    directories: list[Directory]


class Detector(pydantic.BaseModel):
    name: str
    directory_name: str
    granularity: DirectoryGranularity | None = DirectoryGranularity.day
    description: str | None = None
    manufacturer: str | None = None


class DetectorView(pydantic.BaseModel):
    detectors: list[Detector] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("detectors", mode="before")
    @classmethod
    def convert_none_to_list(cls, v):
        return [] if v is None else v

    class Settings:
        projection = {
            "detectors": "$detectors",
        }


class DetectorList(pydantic.BaseModel):
    detectors: list[Detector] | None = None
    count: int | None = None


class BeamlineService(pydantic.BaseModel):
    name: str
    used_in_production: bool | None = None
    host: str | None = None
    port: int | None = None
    uri: str | None = None


class ServicesOnly(pydantic.BaseModel):
    services: list[BeamlineService] | None = None

    class Settings:
        projection = {
            "services": "$services",
        }


class ServiceAccounts(pydantic.BaseModel):
    ioc: str | None
    workflow: str | None
    bluesky: str | None
    epics_services: str | None
    operator: str | None
    lsdc: str | None = None

    class Settings:
        keep_nulls = False


class ServiceAccountsView(pydantic.BaseModel):
    service_accounts: ServiceAccounts | None


class WorkflowServiceAccountView(pydantic.BaseModel):
    username: str

    class Settings:
        projection = {"username": "$service_accounts.workflow"}


class IOCServiceAccountView(pydantic.BaseModel):
    username: str

    class Settings:
        projection = {"username": "$service_accounts.ioc"}


class BlueskyServiceAccountView(pydantic.BaseModel):
    username: str

    class Settings:
        projection = {"username": "$service_accounts.bluesky"}


class OperatorServiceAccountView(pydantic.BaseModel):
    username: str

    class Settings:
        projection = {"username": "$service_accounts.operator"}


class EpicsServicesServiceAccountView(pydantic.BaseModel):
    username: str

    class Settings:
        projection = {"username": "$service_accounts.epics_services"}


class LsdcServiceAccountView(pydantic.BaseModel):
    username: str

    class Settings:
        projection = {"username": "$service_accounts.lsdc"}


class BeamlineServicesSynchwebView(pydantic.BaseModel):
    synchweb: BeamlineService

    class Settings:
        projection = {"synchweb": "$services.name"}


class DataRootDirectoryView(pydantic.BaseModel):
    data_root: str | None = None

    class Settings:
        projection = {"data_root": "$custom_root_directory"}


class SlackChannelManagersView(pydantic.BaseModel):
    slack_channel_managers: list[str] | None = []

    class Settings:
        projection = {"slack_channel_managers": "$slack_channel_managers"}


class SlackBeamlineBotUserIdView(pydantic.BaseModel):
    slack_beamline_bot_user_id: str | None = None

    class Settings:
        projection = {"slack_beamline_bot_user_id": "$slack_beamline_bot_user_id"}


class EndStation(pydantic.BaseModel):
    name: str
    service_accounts: ServiceAccounts | None = None


class Beamline(beanie.Document):
    name: str
    long_name: str | None
    alternative_name: str | None
    port: str
    network_locations: list[str] | None = []
    pass_name: str | None
    pass_id: str | None
    nsls2_redhat_satellite_location_name: list[str] | None = []
    service_accounts: ServiceAccounts | None = None
    endstations: list[EndStation] | None = []
    slack_channel_managers: list[str] | None = []
    slack_beamline_bot_user_id: str | None = None
    slack_autocreate_channels: bool | None = False
    data_admins: list[str] | None = []
    custom_data_admin_group: str | None = None
    github_org: str | None = None
    data_root: str | None = None
    services: list[BeamlineService] | None = []
    detectors: list[Detector] | None = []
    created_on: datetime.datetime = pydantic.Field(
        default_factory=datetime.datetime.now
    )
    last_updated: datetime.datetime = pydantic.Field(
        default_factory=datetime.datetime.now
    )

    @field_validator(
        "network_locations", "nsls2_redhat_satellite_location_name", mode="before"
    )
    @classmethod
    def ensure_string_list(cls, v: str) -> list:
        if isinstance(v, str):
            return [v]
        return v

    @field_validator("detectors", "endstations", mode="before")
    @classmethod
    def convert_none_to_list(cls, v):
        return [] if v is None else v

    @before_event(Insert)
    def uppercase_name(self):
        self.name = self.name.upper()

    class Settings:
        name = "beamlines"
        keep_nulls = False
        indexes = []
