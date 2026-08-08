
import bson
import fastapi
from fastapi import Depends, Request

from nsls2api.api.models.facility_model import FacilityName
from nsls2api.infrastructure.security import get_current_user
from nsls2api.models.jobs import (
    BackgroundJob,
    JobActions,
    JobSyncParameters,
    JobSyncSource,
)
from nsls2api.services import background_service

# TODO: This flag should be automatically set to be True for development but False for production.
SYNC_ROUTES_IN_SCHEMA = True

router = fastapi.APIRouter(tags=["jobs"])


@router.get("/jobs/check-status/{job_id}")
async def check_job_status(request: Request, job_id: str):
    """
    Check the status of a background job.

    :param job_id: The ID of the job to check.
    :return: The status of the job.
    """

    job = await background_service.job_by_id(bson.ObjectId(job_id))
    if job is None:
        return fastapi.responses.JSONResponse(
            {"error": f"Job {job_id} not found"},
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
        )
    else:
        return job.processing_status


@router.get(
    "/sync/dataadmins",
    dependencies=[Depends(get_current_user)],
    include_in_schema=SYNC_ROUTES_IN_SCHEMA,
    tags=["sync"],
)
async def sync_dataadmins(request: Request) -> BackgroundJob:
    job = await background_service.create_background_job(JobActions.synchronize_admins)
    return job


@router.get(
    "/sync/proposal/{proposal_id}",
    dependencies=[Depends(get_current_user)],
    include_in_schema=SYNC_ROUTES_IN_SCHEMA,
    tags=["sync"],
    deprecated=True,
)
async def sync_proposal(
    request: Request, proposal_id: str, facility: FacilityName = FacilityName.nsls2
) -> BackgroundJob:
    sync_params = JobSyncParameters(proposal_id=proposal_id, facility=facility)
    job = await background_service.create_background_job(
        JobActions.synchronize_proposal,
        sync_parameters=sync_params,
    )
    return job


@router.get(
    "/sync/facility/{facility}/proposal/{proposal_id}",
    dependencies=[Depends(get_current_user)],
    include_in_schema=SYNC_ROUTES_IN_SCHEMA,
    tags=["sync"],
)
async def sync_facility_proposal(
    request: Request, facility: FacilityName, proposal_id: str
) -> BackgroundJob:
    sync_params = JobSyncParameters(proposal_id=proposal_id, facility=facility)
    job = await background_service.create_background_job(
        JobActions.synchronize_proposal,
        sync_parameters=sync_params,
    )
    return job


@router.get(
    "/sync/proposal/types/{facility}",
    include_in_schema=SYNC_ROUTES_IN_SCHEMA,
    tags=["sync"],
)
async def sync_proposal_types(facility: FacilityName = FacilityName.nsls2):
    sync_params = JobSyncParameters(facility=facility)
    job = await background_service.create_background_job(
        JobActions.synchronize_proposal_types,
        sync_parameters=sync_params,
    )
    return job


@router.get(
    "/sync/proposals/cycle/{cycle}",
    dependencies=[Depends(get_current_user)],
    include_in_schema=SYNC_ROUTES_IN_SCHEMA,
    tags=["sync"],
    deprecated=True,
)
async def sync_proposals_for_cycle(
    request: Request, cycle: str, facility: FacilityName = FacilityName.nsls2
) -> BackgroundJob:
    sync_params = JobSyncParameters(cycle=cycle, facility=facility)
    job = await background_service.create_background_job(
        JobActions.synchronize_proposals_for_cycle,
        sync_parameters=sync_params,
    )
    return job


@router.get(
    "/sync/facility/{facility}/cycle/{cycle}/proposals",
    dependencies=[Depends(get_current_user)],
    include_in_schema=SYNC_ROUTES_IN_SCHEMA,
    tags=["sync"],
)
async def sync_proposals_for_facility_cycle(
    request: Request, facility: FacilityName, cycle: str
) -> BackgroundJob:
    sync_params = JobSyncParameters(cycle=cycle, facility=facility)
    job = await background_service.create_background_job(
        JobActions.synchronize_proposals_for_cycle,
        sync_parameters=sync_params,
    )
    return job


@router.get(
    "/sync/cycles/{facility}", include_in_schema=SYNC_ROUTES_IN_SCHEMA, tags=["sync"]
)
async def sync_cycles(facility: FacilityName = FacilityName.nsls2):
    sync_params = JobSyncParameters(facility=facility)
    job = await background_service.create_background_job(
        JobActions.synchronize_cycles,
        sync_parameters=sync_params,
    )
    return job


@router.get(
    "/sync/update-cycles/{facility}",
    include_in_schema=SYNC_ROUTES_IN_SCHEMA,
    tags=["sync"],
    summary="Updates the local (nsls2core DB) cycle <-> proposal mapping",
)
async def sync_update_cycles(
    request: fastapi.Request,
    facility: FacilityName = FacilityName.nsls2,
    cycle: str | None = None,
):
    sync_params = JobSyncParameters(facility=facility, sync_source=JobSyncSource.PASS)

    job = await background_service.create_background_job(
        JobActions.update_cycle_information,
        sync_parameters=sync_params,
    )
    return job
