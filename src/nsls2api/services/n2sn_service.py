
from N2SNUserTools.ldap import ADObjects

from nsls2api.api.models.person_model import (
    ActiveDirectoryUser,
    ActiveDirectoryUserGroups,
)
from nsls2api.infrastructure.config import get_settings
from nsls2api.infrastructure.logging import logger

settings = get_settings()


async def get_groups_by_username(username: str) -> ActiveDirectoryUserGroups | None:
    """
    :param username: The username for which you want to retrieve the groups.
    :return: An instance of ActiveDirectoryUserGroups that contains information about the groups the user belongs to. Returns None if the user is not found or if there are multiple users with the same username.
    """

    with ADObjects(
        settings.active_directory_server,
        user_search=settings.n2sn_user_search,
        group_search=settings.n2sn_group_search,
        authenticate=False,
        ca_certs_file=settings.bnlroot_ca_certs_file,
    ) as ad:
        user_details = ad.get_group_by_samaccountname(username)
    if len(user_details) == 0 or len(user_details) > 1:
        return None
    return ActiveDirectoryUserGroups(**user_details[0])


async def get_user_by_username(username: str) -> ActiveDirectoryUser | None:
    """
    Get a user by their username.

    :param username: The username of the user.
    :return: An instance of ActiveDirectoryUser if the user is found, else None.
    """

    print(f"type = {type(settings)}")
    print(settings.pass_api_key)

    with ADObjects(
        settings.active_directory_server,
        user_search=settings.n2sn_user_search,
        group_search=settings.n2sn_group_search,
        authenticate=False,
        ca_certs_file=settings.bnlroot_ca_certs_file,
    ) as ad:
        user_details = ad.get_user_by_samaccountname(username)
    if len(user_details) == 0 or len(user_details) > 1:
        return None
    return ActiveDirectoryUser(**user_details[0])


async def get_user_by_id(bnl_id: str) -> ActiveDirectoryUser | None:
    """
    :param bnl_id: The BNL ID of the user to retrieve
    :return: An ActiveDirectoryUser object representing the user's details

    """
    with ADObjects(
        settings.active_directory_server,
        user_search=settings.n2sn_user_search,
        group_search=settings.n2sn_group_search,
        authenticate=False,
        ca_certs_file=settings.bnlroot_ca_certs_file,
    ) as ad:
        user_details = ad.get_user_by_id(bnl_id)
    if len(user_details) == 0 or len(user_details) > 1:
        return None
    return ActiveDirectoryUser(**user_details[0])


async def get_username_by_id(bnl_id: str) -> str | None:
    ad_user: ActiveDirectoryUser = await get_user_by_id(bnl_id)
    if ad_user is None:
        return None
    return ad_user.sAMAccountName


async def get_users_in_group(group: str) -> list[ActiveDirectoryUser]:
    """
    :param group: The name of the group that you want to retrieve the users from.

    :return: A list of `ActiveDirectoryUser` objects representing the users in the specified group.

    """
    with ADObjects(
        settings.active_directory_server,
        user_search=settings.n2sn_user_search,
        group_search=settings.n2sn_group_search,
        authenticate=False,
        ca_certs_file=settings.bnlroot_ca_certs_file,
    ) as ad:
        try:
            users = ad.get_group_members(group)
        except RuntimeError as e:
            logger.exception(e)
            return []
    return users


async def is_user_in_group(username: str, group: str):
    """
    Checks if a user is present in a specified group.

    Args:
        username (str): The username of the user to check.
        group (str): The name of the group to check.

    Returns:
        bool: True if the user is found in the group, False otherwise.
    """
    _user_found = False
    users = await get_users_in_group(group)
    _user_found: bool = any(
        user for user in users if user["sAMAccountName"] == username
    )
    return _user_found
