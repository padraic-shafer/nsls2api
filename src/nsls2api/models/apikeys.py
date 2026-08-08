import datetime
from enum import StrEnum
from uuid import UUID, uuid4

import beanie
import pydantic
import pymongo
from beanie import BackLink, Link
from pydantic import Field


class ApiUserType(StrEnum):
    user = "user"
    service = "service"


class ApiUserRole(StrEnum):
    user = "user"
    staff = "staff"
    admin = "admin"


class ApiUserResponseModel(pydantic.BaseModel):
    id: UUID
    username: str
    type: ApiUserType
    role: ApiUserRole
    created_on: datetime.datetime
    last_updated: datetime.datetime


class ApiUser(beanie.Document):
    id: UUID = Field(default_factory=uuid4)
    username: str
    type: ApiUserType
    role: ApiUserRole | None = ApiUserRole.user
    created_on: datetime.datetime = pydantic.Field(
        default_factory=datetime.datetime.now
    )
    last_updated: datetime.datetime = pydantic.Field(
        default_factory=datetime.datetime.now
    )
    user_api_keys: BackLink["ApiKey"] = Field(
        json_schema_extra={"original_field": "user"}
    )
    # user_api_keys: Optional[List[BackLink["ApiKey"]]]= Field(original_field="user")

    class Settings:
        name = "api_users"
        indexes = [
            pymongo.IndexModel(
                keys=[("username", pymongo.ASCENDING)],
                name="username_ascend",
                unique=True,
            ),
            pymongo.IndexModel(keys=[("type", pymongo.ASCENDING)], name="type_ascend"),
            pymongo.IndexModel(keys=[("role", pymongo.ASCENDING)], name="role_ascend"),
            pymongo.IndexModel(
                keys=[("created_date", pymongo.DESCENDING)],
                name="created_date_descend",
            ),
            pymongo.IndexModel(
                keys=[("last_login", pymongo.DESCENDING)],
                name="last_login_descend",
            ),
        ]


class ApiKey(beanie.Document):
    user: Link[ApiUser]
    username: str
    first_eight: pydantic.constr(min_length=8, max_length=8)
    hashed_key: str
    note: str | None = ""
    # scopes: Optional[list[str]] = pydantic.Field(..., example=["inherit"])
    valid: bool = True
    expires_after: datetime.datetime | None = None
    created_on: datetime.datetime = pydantic.Field(
        default_factory=datetime.datetime.now
    )
    last_updated: datetime.datetime = pydantic.Field(
        default_factory=datetime.datetime.now
    )

    class Settings:
        name = "api_keys"
        keep_nulls = False
        indexes = [
            pymongo.IndexModel(
                keys=[("created_date", pymongo.DESCENDING)],
                name="created_date_descend",
            ),
            pymongo.IndexModel(
                keys=[("last_login", pymongo.DESCENDING)],
                name="last_login_descend",
            ),
            pymongo.IndexModel(
                keys=[("first_eight", pymongo.ASCENDING)],
                name="first_eight_ascend",
                unique=True,
            ),
            pymongo.IndexModel(keys=[("note", pymongo.TEXT)], name="apikey_text"),
        ]
