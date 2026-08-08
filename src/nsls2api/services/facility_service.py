import datetime
from contextlib import asynccontextmanager
from dataclasses import dataclass

from beanie.odm.operators.find.comparison import In
from beanie.odm.operators.update.general import Set

from nsls2api.api.models.facility_model import FacilityName
from nsls2api.infrastructure.logging import logger
from nsls2api.models.cycles import Cycle
from nsls2api.models.facilities import Facility


class CycleOperationError(Exception):
    """Base exception for cycle operations."""
    # No additional methods or attributes are needed for this class.



class CycleNotFoundError(CycleOperationError):
    """Raised when a requested cycle cannot be found."""

    def __init__(self, facility: str, cycle: str):
        self.facility = facility
        self.cycle = cycle
        super().__init__(
            f"Requested Cycle '{cycle}' does not exist for facility '{facility}'."
        )


class CycleUpdateError(CycleOperationError):
    """Raised when cycle update operations fail."""

    def __init__(self, facility: str, cycle: str, reason: str):
        self.facility = facility
        self.cycle = cycle
        self.reason = reason
        super().__init__(f"Failed to update cycle for facility '{facility}': {reason}")


class CycleVerificationError(CycleOperationError):
    """Raised when cycle verification fails after an update."""

    def __init__(self, facility: str, expected_cycle: str, actual_cycle: str | None):
        self.facility = facility
        self.expected_cycle = expected_cycle
        self.actual_cycle = actual_cycle
        super().__init__(
            f"Cycle verification failed for facility '{facility}'. "
            f"Expected: '{expected_cycle}', "
            f"Actual: '{actual_cycle or 'None'}'"
        )


async def facilities_count() -> int:
    """
    Count the number of facilities in the database.

    :return: The number of facilities.
    """
    return await Facility.count()


async def all_facilities() -> list[Facility]:
    """
    This method retrieves all facilities in the database.

    :return: A list of facilities (list[Facility]).
    """
    return await Facility.find().to_list()


async def facility_cycles(facility: str) -> list[str] | None:
    """
    Facility Cycles

    This method retrieves the cycles for a given facility.

    :param facility: The facility name (str).
    :return: A list of cycles for the facility (list[Cycle]).
    """
    # FIXME: This next line is not returning a sorted list of cycles.
    cycles = (
        await Cycle.find(Cycle.facility == facility)
        .sort(+Cycle.year, +Cycle.name)
        .to_list()
    )
    cycle_list = [c.name for c in cycles if c.name is not None]
    return cycle_list


async def facility_cycle_by_date(
    facility: FacilityName, date: datetime.datetime
) -> Cycle | None:
    """
    Find the cycle for a facility that contains the given date.

    :param facility: The facility name (FacilityName).
    :param date: The date to search for (datetime).
    :return: The matching Cycle or None.
    """
    cycle = await Cycle.find_one(
        Cycle.facility == facility.value,
        Cycle.start_date <= date,
        Cycle.end_date >= date,
    )
    return cycle if cycle else None


async def facility_by_pass_id(pass_user_facility_id: str) -> Facility | None:
    """
    Facility by PASS ID

    This method retrieves the facility by the PASS ID.

    :param pass_user_facility_id: The PASS ID (str).
    :return: The facility (Facility) or None if no facility is found.
    """
    return await Facility.find_one(Facility.pass_facility_id == pass_user_facility_id)


async def pass_id_for_facility(facility_id: str) -> str | None:
    """
    PASS ID for Facility

    This method retrieves the PASS ID for a given facility.

    :param facility_id: The facility name (str). e.g. "nsls2, lbms, cfn, etc."
    :return: The PASS ID (str) or None if no facility is found.
    """
    facility = await Facility.find_one(Facility.facility_id == facility_id)

    return facility.pass_facility_id if facility else None


async def data_roles_by_user(username: str) -> list[str] | None:
    facilities = await Facility.find(In(Facility.data_admins, [username])).to_list()
    facility_names = [f.facility_id for f in facilities if f.facility_id is not None]
    return facility_names


async def data_admin_group(facility_name: str) -> str | None:
    """
    Retrieves the data admin group for a given facility name.

    Args:
        facility_name (str): The facility name. e.g. "nsls2, lbms, cfn, etc."

    Returns:
        str: The data admin group for the specified facility or None if a group is not found.
    """
    facility = await Facility.find_one(Facility.facility_id == facility_name)

    return facility.data_admin_group if facility else None


async def get_data_admins(facility_name: str) -> list[str]:
    """
    Retrieves the data admins for a given facility name.

    Args:
        facility_name (str): The facility name. e.g. "nsls2, lbms, cfn, etc."

    Returns:
        list[str]: A list of data admins for the specified facility.
    """
    facility = await Facility.find_one(Facility.facility_id == facility_name)

    return facility.data_admins if facility else []


async def update_data_admins(facility_id: str, data_admins: list[str]):
    """
    Update the data admins for a given facility.

    Args:
        facility_id (str): The name/ID of the facility (e.g. nsls2, lbms, cfn, etc.).
        data_admins (list[str]): A list of usernames to set as data admins for the facility.
    """
    await Facility.find_one(Facility.facility_id == facility_id.lower()).update(
        Set(
            {
                Facility.data_admins: data_admins,
                Facility.last_updated: datetime.datetime.now(),
            }
        )
    )


async def current_operating_cycle(facility_name: str) -> str | None:
    """
    Current Operating Cycle

    This method retrieves the current operating cycle for a given facility.

    :param facility_name: The facility name (str).
    :return: The current operating cycle (str) or None if no current operating cycle is found.
    """
    cycle = await Cycle.find_one(
        Cycle.facility == facility_name,
        Cycle.is_current_operating_cycle == True,  # noqa: E712 # Operator is used by Beanie query
    )

    return cycle.name if cycle else None


@dataclass
class CycleChangeState:
    new_cycle: Cycle | None = None
    previous_cycle: Cycle | None = None
    is_successful: bool = False


@asynccontextmanager
async def cycle_change_context(facility: str, cycle: str):
    """
    Context manager to handle atomic-like operations for changing facility cycles.

    Args:
        facility (str): The facility name
        cycle (str): The new cycle name to be set

    Yields:
        CycleChangeState: Object containing the state of the cycle change operation

    Raises:
        CycleNotFoundError: If the requested cycle cannot be found
        CycleUpdateError: If the update operations fail
        CycleVerificationError: If the final state verification fails
    """
    state = CycleChangeState()

    try:
        # Validate and get the new cycle
        state.new_cycle = await Cycle.find_one(
            Cycle.facility == facility,
            Cycle.name == cycle,
        )
        if state.new_cycle is None:
            raise CycleNotFoundError(facility, cycle)

        # Get the current active cycle
        state.previous_cycle = await Cycle.find_one(
            Cycle.facility == facility,
            Cycle.is_current_operating_cycle == True,  # noqa: E712 # Operator is used by Beanie query
        )

        yield state

        # If we get here without exceptions, mark the operation as successful
        state.is_successful = True

    except CycleOperationError:
        state.is_successful = False
        raise

    except Exception as e:
        state.is_successful = False
        raise CycleUpdateError(facility, cycle, str(e)) from e

    finally:
        if state.is_successful:
            try:
                # Perform the updates only if everything was successful
                if state.previous_cycle is not None:
                    await state.previous_cycle.set(
                        {Cycle.is_current_operating_cycle: False}
                    )

                await state.new_cycle.set({Cycle.is_current_operating_cycle: True})

                # Verify the change
                current = await current_operating_cycle(facility)
                if str(current) != cycle:
                    logger.error(
                        f"Failed to set the current operating cycle for {facility} to be {cycle}."
                    )
                    raise CycleVerificationError(facility, cycle, current)

            except CycleOperationError:
                state.is_successful = False
                raise

            except Exception as e:
                state.is_successful = False
                raise CycleUpdateError(facility, cycle, str(e)) from e


async def set_current_operating_cycle(facility_name: str, cycle: str) -> str:
    """
    Set the current operating cycle for a given facility using a pseudo-atomic operation.

    Args:
        facility_name (str): The facility name.
        cycle (str): The new cycle name.

    Returns:
        str: The current operating cycle if successful.

    Raises:
        CycleNotFoundError: If the requested cycle cannot be found
        CycleUpdateError: If the update operations fail
        CycleVerificationError: If the final state verification fails
    """
    # The context manager will handle the cycle update operation,
    # so this pass statement is intentional.
    async with cycle_change_context(facility_name, cycle) as state:  # noqa: F841
        pass

    return cycle


async def cycle_year(
    cycle_name: str, facility_name: FacilityName = FacilityName.nsls2
) -> str | None:
    """
    Cycle Year

    This method retrieves the year for a given cycle.

    :param cycle_name: The cycle name (str).
    :param facility_name: The facility name (FacilityName).
    :return: The year (str) or None if no year is found.
    """
    cycle = await Cycle.find_one(
        Cycle.name == cycle_name, Cycle.facility == facility_name
    )

    return cycle.year if cycle else None


async def is_healthy(facility: str) -> bool:
    """
    Database Health Check

    This method checks the health of the information in the database.
    Basically, is the database populated with the correct information?
    e.g. Is there only one current operating cycle for a facility?

    :param facility: The facility name (str).
    :return: True if the database is healthy, False otherwise.
    """

    # Let's start with assuming the database is healthy.
    health_status = True

    logger.info(f"Checking the health of the {facility} facility data.")

    # TODO: Check that the facility exists in the database.

    # Check that there is only one current operating cycle for the facility.
    cycles = await Cycle.find(Cycle.is_current_operating_cycle == facility).to_list()
    if len(cycles) > 1:
        logger.warning(
            f"There is more than one current operating cycle for the {facility}."
        )
        health_status = False
    elif len(cycles) == 0:
        logger.warning(f"There is not an operating cycle for the {facility}.")
        health_status = False

    return health_status


async def cycle_exists(cycle_name: str, facility: str) -> bool:
    cycle = await Cycle.find_one(Cycle.name == cycle_name, Cycle.facility == facility)
    return False if cycle is None else True


async def get_cycle_by_name(facility: str, cycle_name: str) -> Cycle:
    """
    Retrieve a cycle by its name for a given facility.

    Args:
        facility (str): The facility name or ID.
        cycle_name (str): The cycle name.

    Returns:
        Cycle: The matching Cycle document.

    Raises:
        CycleNotFoundError: If no cycle is found for the given facility and cycle name.
    """
    cycle = await Cycle.find_one(Cycle.facility == facility, Cycle.name == cycle_name)
    if cycle is None:
        raise CycleNotFoundError(facility, cycle_name)
    return cycle
