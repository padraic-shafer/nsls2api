from datetime import datetime

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from nsls2api.infrastructure.config import get_settings
from nsls2api.infrastructure.logging import logger
from nsls2api.models.slack_models import (
    ProposalSlackChannel,
    SlackBot,
    SlackChannelToCreate,
    SlackConversation,
    SlackPerson,
    SlackUser,
)
from nsls2api.services import beamline_service, proposal_service

settings = get_settings()


class ChannelAlreadyExistsError(Exception):
    pass


def create_conversation(name: str, is_private: bool = True) -> str | None:
    """
    Creates a new Slack conversation with the given name and privacy setting.

    Args:
        name (str): The name of the conversation to be created.
        is_private (bool, optional): Whether the conversation should be private. Defaults to True.

    Returns:
        str | None: The ID of the created conversation if successful, None otherwise.

    Raises:
        ChannelAlreadyExistsError: If a channel with the given name already exists.
    """
    client = WebClient(token=settings.slack_bot_token)
    try:
        response = client.conversations_create(name=name, is_private=is_private)
        if response.get("ok"):
            return response.get("channel").get("id")
    except SlackApiError as error:
        if error.response["error"] == "name_taken":
            print(f"#### Channel '{name}' already exists.")
            raise ChannelAlreadyExistsError(f"Channel '{name}' already exists.")
        else:
            logger.exception(error)
    return None


def conversation_invite(channel_id: str, user_ids: list[str]):
    """
    Invites users to a Slack conversation.

    Args:
        channel_id (str): The ID of the Slack conversation.
        user_ids (list[str]): A list of user IDs to invite to the conversation.

    Raises:
        Exception: If an error occurs while inviting users to the conversation.

    Returns:
        None
    """
    client = WebClient(token=settings.slack_bot_token)
    try:
        response = client.conversations_invite(
            channel=channel_id, users=user_ids, force=True
        )
        if response.get("ok"):
            logger.info(f"Invited users {user_ids} to channel '{channel_id}'.")
    except SlackApiError as error:
        # If the error is that the user is already in the channel, we can ignore it
        if error.response["error"] == "already_in_channel":
            return
        if error.response["error"] == "user_is_ultra_restricted":
            detailed_errors = error.response.get("errors", [])
            problem_users = []
            for detailed_error in detailed_errors:
                if detailed_error.get("error") == "user_is_ultra_restricted":
                    problem_users.append(detailed_error.get("user"))
            logger.error(
                f"User(s) {problem_users} are ultra-restricted and cannot be invited to channel '{channel_id}'."
            )
            return
        logger.exception(error)


def get_conversation_topic(channel_id: str) -> str | None:
    """
    Retrieves the topic of a Slack conversation.

    Args:
        channel_id (str): The ID of the Slack conversation.

    Returns:
        str | None: The topic of the conversation if successful, None otherwise.
    """
    client = WebClient(token=settings.slack_bot_token)
    try:
        response = client.conversations_info(channel=channel_id)
        return response.get("channel").get("topic", {}).get("value", "")
    except SlackApiError as error:
        logger.exception(error)
    return None


def set_conversation_topic(channel_id: str, topic: str):
    """
    Sets the topic of a Slack conversation.

    Args:
        channel_id (str): The ID of the Slack conversation.
        topic (str): The topic to set for the conversation.

    Raises:
        Exception: If an error occurs while setting the topic for the conversation.

    Returns:
        None
    """
    client = WebClient(token=settings.slack_bot_token)
    try:
        original_topic = get_conversation_topic(channel_id=channel_id)
        # Only set the topic if it is different from the current topic
        if original_topic == topic:
            logger.info(
                f"Topic is already set to '{topic}' for channel '{channel_id}'."
            )
            return
        response = client.conversations_setTopic(channel=channel_id, topic=topic)
        if response.get("ok"):
            logger.info(f"Set topic for channel '{channel_id}' to '{topic}'.")
    except SlackApiError as error:
        logger.exception(error)


def get_bot_details() -> SlackBot:
    """
    Retrieves the details of the Slack bot.

    Returns:
        SlackBot: An instance of the SlackBot class containing the bot details.
    """
    client = WebClient(token=settings.slack_bot_token)
    response = client.auth_test()

    return SlackBot(
        username=response.get("user"),
        user_id=response.get("user_id"),
        bot_id=response.get("bot_id"),
    )


def get_user_info(user_id: str) -> SlackUser | None:
    """
    Retrieves the details of a Slack User.

    Args:
        user_id (str): Slack user_id to lookup

    Returns:
        SlackUser: An instance of the SlackUser class containing the user details.
    """
    client = WebClient(token=settings.slack_bot_token)
    try:
        response = client.users_info(user=user_id)
        slack_user = SlackUser(
            username=response.get("user", {}).get("name", ""),
            user_id=response.get("user", {}).get("id", user_id),
            is_bot=response.get("user", {}).get("is_bot", False),
            real_name=response.get("user", {}).get("real_name", ""),
            pending_invitation=response.get("user", {}).get(
                "accepted_invitation", False
            ),
        )
        return slack_user
    except SlackApiError as error:
        logger.exception(error)

    return None


def verify_slack_users(users: list[str]) -> list[SlackUser]:
    """
    Verifies that the given list of user IDs are valid Slack users.

    Args:
        users (list[str]): A list of user IDs to verify.

    Returns:
        list[SlackUser]: A list of SlackUser instances containing the user details.
    """
    client = WebClient(token=settings.slack_bot_token)
    verified_users = []
    for user_id in users:
        try:
            response = client.users_info(user=user_id)
            verified_users.append(
                SlackUser(
                    username=response.get("user", {}).get("name", ""),
                    user_id=user_id,
                )
            )
        except SlackApiError as error:
            logger.exception(error)
    return verified_users


def verify_slack_bot(bot_user_id: str) -> SlackBot | None:
    """
    Verifies that the given bot ID is a valid Slack bot.

    Args:
        bot_user_id (str): The user_id of the bot to verify.

    Returns:
        SlackBot | None: An instance of the SlackBot class containing the bot details if valid, None otherwise.
    """
    client = WebClient(token=settings.slack_bot_token)
    try:
        response = client.users_info(user=bot_user_id)
        is_bot = response.get("ok", False)
        if is_bot:
            return SlackBot(
                username=response.get("user", {}).get("name", ""),
                user_id=bot_user_id,
                bot_id=response.get("user", {}).get("profile", {}).get("bot_id", ""),
            )
        else:
            # This user_id is not a bot
            return None
    except SlackApiError as error:
        logger.exception(error)
    return None


def get_channel_members(channel_id: str) -> list[str]:
    """
    Retrieves the members of a Slack channel.
    It assumes that the bot is already a member of the
    channel (if it is a private channel)

    Args:
        channel_id (str): The ID of the Slack channel.

    Returns:
        list[str]: A list of member IDs in the channel.
    """
    try:
        client = WebClient(token=settings.slack_bot_token)
        response = client.conversations_members(channel=channel_id, limit=1000)
    except SlackApiError as error:
        logger.exception(error)
        return []
    return response.get("members", [])


async def is_channel_private(channel_id: str) -> bool:
    """
    Checks if a Slack channel is private.

    Args:
        channel_id (str): The ID of the channel to check.

    Returns:
        bool: True if the channel is private, False otherwise.
    """
    client = WebClient(token=settings.slack_bot_token)
    response = client.conversations_info(channel=channel_id)
    return response.get("channel").get("is_private")


def get_private_channel_id(name: str) -> str | None:
    """
    Retrieves the channel ID for a given private channel name.

    Args:
        name (str): The name of the channel.

    Returns:
        str | None: The ID of the channel if found, None otherwise.
    """
    client = WebClient(token=settings.slack_bot_token)
    response = client.conversations_list(types="private_channel")
    # This returns a list of channels, find the one with the exact name (just in case we get more than one returned)
    for channel in response.get("channels"):
        if channel.get("name") == name:
            logger.info(f"Found existing channel '{name}' with ID {channel['id']}")
            return channel.get("id")
    return None


def get_conversation_details(channel_id: str) -> SlackConversation | None:
    """
    Retrieves detailed information about a Slack conversation (channel).

    Args:
        channel_id (str): The ID of the Slack channel.

    Returns:
        SlackConversation | None: An instance of the SlackConversation class containing
            the channel details if successful, None otherwise.
    """
    client = WebClient(token=settings.slack_bot_token)
    try:
        info_response = client.conversations_info(
            channel=channel_id, include_num_members=True
        )

        channel_users = [
            user_info
            for slack_userid in get_channel_members(channel_id)
            if (user_info := get_user_info(user_id=slack_userid))
        ]

        details = SlackConversation(
            conversation_id=channel_id,
            name=info_response.get("channel", {}).get("name", ""),
            is_private=info_response.get("channel", {}).get("is_private", False),
            topic=info_response.get("channel", {}).get("topic", {}).get("value", ""),
            purpose=info_response.get("channel").get("purpose", {}).get("value", ""),
            creator=info_response.get("channel", {}).get("creator", ""),
            is_archived=info_response.get("channel", {}).get("is_archived", False),
            updated=datetime.fromtimestamp(
                info_response.get("channel", {}).get("updated", 0) / 1000.0
            ),
            created=datetime.fromtimestamp(
                info_response.get("channel", {}).get("created", 0)
            ),
            num_members=info_response.get("channel", {}).get("num_members", 0),
            members=channel_users,
        )
        return details
    except SlackApiError as error:
        logger.exception(error)
    return None


def lookup_user_by_email(email: str) -> SlackPerson | None:
    """
    Looks up the user associated with the given email address.

    Args:
        email (str): The email address of the user.

    Returns:
        SlackPerson | None: An instance of the SlackPerson class containing
                          the user details if found, None otherwise.
    """
    try:
        client = WebClient(token=settings.slack_bot_token)
        response = client.users_lookupByEmail(email=email)
        if response.get("ok"):
            return SlackPerson(
                user_id=response.get("user", {}).get("id", ""),
                username=response.get("user", {}).get("name", ""),
                email=email,
            )
    except SlackApiError as error:
        if error.response["error"] == "users_not_found":
            logger.info(f"Slack User with an email of '{email}' not found.")
            return None
        logger.exception(error)

    return None


def get_userid_by_username(username: str) -> str | None:
    """
    Looks up the slack user_id associated with the given username.

    Args:
        username (str): The username of the user.

    Returns:
        str | None: A string containing the user_id of
                          the user if found, None otherwise.
    """
    client = WebClient(token=settings.slack_bot_token)
    try:
        cursor = None
        while True:
            response = client.users_list(cursor=cursor)
            if not response["ok"]:
                logger.error(f"Slack API returned an error: {response}")
                return None

            for member in response["members"]:
                if member.get("name") == username:
                    return member["id"]

            # Check if there are more pages to fetch
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
    except SlackApiError as error:
        logger.exception(f"Failed to retrieve users list: {error}")
        return None

    return None  # Not found


def invite_newuser_to_channel(channel: str, email: str) -> SlackPerson | None:
    """
    Invites a user to the workspace/channel.
    Args:
        channel (str): The channel ID of the Slack channel.
        email (str): The email address of the user.

    Returns:
        SlackPerson | None: An instance of the SlackPerson class containing
                  the user details of the invited user if successful, None otherwise.
    """
    try:
        client = WebClient(token=settings.slack_admin_user_token)
        response = client.admin_users_invite(
            team_id=settings.nsls2_workspace_team_id,
            email=email,
            channel_ids=channel,
        )
        if response.get("ok"):
            # If the user invite was ok, then lets look up the user_id of the newly invited user
            new_user = lookup_user_by_email(email)
            if new_user:
                return new_user
            return None
        return None
    except SlackApiError as error:
        if error.response["error"] == "already_in_team_invited_user":
            # We've already invited this user - so we are good.
            return None
        logger.exception(error)
        return None


async def create_proposal_channels(
    proposal_id: str,
) -> list[ProposalSlackChannel] | None:
    channels_created = []

    # What is(are) the name of the channel(s) associated with this proposal?
    channels_to_create: list[
        SlackChannelToCreate
    ] = await proposal_service.get_slack_channels_to_create_for_proposal(
        proposal_id, separate_chat_channel=True
    )

    # We will add the superset of all the relevant slack managers and bots to
    # the proposal channel for all the beamlines associated with the proposal.

    # Loop over the channels to create
    for channel in channels_to_create:
        channel_name = channel.channel_name
        logger.info(f"Creating new channel '{channel_name}'.")

        # Create the channel
        try:
            channel_id = create_conversation(channel_name, is_private=True)
            logger.info(f"Created Channel '{channel_name}' with an ID of {channel_id}")
        except ChannelAlreadyExistsError:
            logger.info(f"Channel '{channel_name}' already exists.")
            channel_id = get_private_channel_id(channel_name)

        # Create a new proposal channel object to store the details
        proposal_channel = ProposalSlackChannel(
            channel_name=channel_name,
            channel_id=channel_id,
            managers=[],
            bots=[],
            users=[],
            is_private=True,
        )

        logger.info(f"Setting topic for channel {channel_id}: {channel.topic}")
        set_conversation_topic(channel_id, channel.topic)
        # Store the topic to return
        proposal_channel.topic = channel.topic

        # Beamline specific managers and bots
        for beamline in channel.beamlines:
            logger.info(
                f"Adding {beamline} specific managers and bots to the channel '{channel_id}'."
            )
            beamline_slack_managers = await beamline_service.slack_channel_managers(
                beamline
            )
            # Verify that the beamline managers are valid Slack users
            verified_managers = verify_slack_users(beamline_slack_managers)

            if len(beamline_slack_managers) != len(verified_managers):
                verified_manager_ids = {
                    manager.user_id for manager in verified_managers
                }
                difference = set(beamline_slack_managers) - verified_manager_ids
                logger.warning(
                    f"Failed to verify Slack accounts the following defined managers {difference} for beamline {beamline}"
                )

            # Proceed with the verified managers
            verified_manager_ids = [manager.user_id for manager in verified_managers]

            if beamline_slack_managers:
                logger.info(
                    f"Adding slack managers for {beamline} with IDs {verified_manager_ids}"
                )
                # Now let's add the beamline Slack channel managers to the channel
                conversation_invite(channel_id, verified_manager_ids)
                # And store the verified managers in the proposal channel object
                proposal_channel.managers.extend(verified_managers)

            beamline_slack_bot = verify_slack_bot(
                await beamline_service.slack_beamline_bot_user_id(beamline)
            )

            if beamline_slack_bot:
                logger.info(
                    f"Adding slack bot for {beamline} with ID {beamline_slack_bot}"
                )
                # Add the beamline "bots" to the channel
                logger.info(
                    f"Adding these beamline bots to the channel: {beamline_slack_bot}"
                )
                # Now lets invite the beamline bot to the channel
                conversation_invite(channel_id, [beamline_slack_bot.user_id])
                # And store the verified bot in the proposal channel object
                proposal_channel.bots.append(beamline_slack_bot)
            else:
                logger.info(f"No slack bot found for beamline {beamline}")

        # Add the users on the proposal to the channel
        user_emails = await proposal_service.fetch_emails_from_proposal(proposal_id)
        user_ids = []
        for email in user_emails:
            user = lookup_user_by_email(email)
            if user:
                user_ids.append(user.user_id)
            else:
                # We need to invite user into the channels (and workspace)
                logger.info(
                    f"Inviting user {email} to channel '{channel_name}' (ID: {channel_id})"
                )
                new_user = invite_newuser_to_channel(channel_id, email)
                if new_user:
                    user_ids.append(new_user.user_id)
                    proposal_channel.users.append(new_user)
        logger.info(
            f"Found {len(user_ids)} users to invite: {user_ids} to channel '{channel_name}' (ID: {channel_id})"
        )
        if len(user_ids) > 0:
            # Only invite users to the channel when we have some to invite.
            conversation_invite(channel_id, user_ids)

        channels_created.append(proposal_channel)

    return channels_created
