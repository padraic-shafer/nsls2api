import asyncio
import datetime
import traceback

import bson

from nsls2api.infrastructure.logging import logger
from nsls2api.models.jobs import BackgroundJob, JobActions, JobStatus, JobSyncParameters
from nsls2api.services import sync_service


async def create_background_job(
    action: JobActions, sync_parameters: JobSyncParameters = None
) -> BackgroundJob:
    job = BackgroundJob(action=action, sync_parameters=sync_parameters)
    await job.save()

    return job


async def pending_jobs(limit=1_000) -> list[BackgroundJob]:
    try:
        return await (
            BackgroundJob.find(BackgroundJob.processing_status == JobStatus.awaiting)
            .sort("created_date")
            .limit(limit)
            .to_list()
        )
    except Exception as e:
        logger.error(f"Error retrieving pending jobs: {e}")
        return []


async def start_job(job_id: bson.ObjectId) -> BackgroundJob | None:
    job = await job_by_id(job_id)
    if not job:
        raise Exception(f"No job with ID {job_id} found.")

    if job.processing_status != JobStatus.awaiting:
        raise Exception(
            f"Cannot start job {job_id} with status {job.processing_status}."
        )

    job.processing_status = JobStatus.processing
    job.started_date = datetime.datetime.now()
    await job.save()

    return job


async def complete_job(
    job_id: bson.ObjectId, processing_status: JobStatus, log_message: str = None
) -> BackgroundJob | None:
    job = await job_by_id(job_id)
    if not job:
        raise Exception(f"No job with ID {job_id} found.")

    if job.processing_status != JobStatus.processing:
        raise Exception(
            f"Cannot complete job {job_id} with status {job.processing_status}."
        )

    job.processing_status = processing_status
    job.finished_date = datetime.datetime.now()
    job.is_finished = True
    job.log_message = log_message
    await job.save()

    return job


async def job_by_id(job_id: bson.ObjectId) -> BackgroundJob | None:
    return await BackgroundJob.find_one(BackgroundJob.id == job_id)


async def is_job_finished(job_id: bson.ObjectId) -> bool:
    job: BackgroundJob | None = await job_by_id(job_id)
    if not job:
        return False

    return job.is_finished


async def worker_function():
    logger.info("Background asyncio service worker up and running.")
    await asyncio.sleep(1)

    while True:
        jobs = await pending_jobs()
        if len(jobs) == 0:
            # logger.debug("No new jobs to process.")
            await asyncio.sleep(1)
            continue

        # Only process one job per iteration
        job = jobs[0]
        try:
            logger.info(f"Starting new job {job.id} with action {job.action}.")
            await start_job(job.id)
        except Exception as e:
            logger.error(f"Error starting new job {job.id}: {e}")
            continue

        try:
            match job.action:
                case JobActions.synchronize_admins:
                    logger.info(f"Processing job {job.id} to synchronize admins.")
                    await sync_service.worker_synchronize_dataadmins()
                case JobActions.update_cycle_information:
                    logger.info(
                        f"Processing job {job.id} to update cycle information for the {job.sync_parameters.facility} facility (from {job.sync_parameters.sync_source})."
                    )
                    await sync_service.worker_update_proposal_to_cycle_mapping(
                        job.sync_parameters.facility, job.sync_parameters.sync_source
                    )
                case JobActions.synchronize_cycles:
                    logger.info(
                        f"Processing job {job.id} to synchronize cycles for the {job.sync_parameters.facility} facility (from {job.sync_parameters.sync_source})."
                    )
                    await sync_service.worker_synchronize_cycles_from_pass(
                        job.sync_parameters.facility
                    )
                case JobActions.synchronize_proposal:
                    logger.info(
                        f"Processing job {job.id} to synchronize proposal {job.sync_parameters.proposal_id} for the {job.sync_parameters.facility} facility (from {job.sync_parameters.sync_source})."
                    )
                    await sync_service.worker_synchronize_proposal_from_pass(
                        job.sync_parameters.proposal_id, job.sync_parameters.facility
                    )
                case JobActions.synchronize_proposals_for_cycle:
                    logger.info(
                        f"Processing job {job.id} to synchronize proposals for the {job.sync_parameters.facility} facility's cycle {job.sync_parameters.cycle} (from {job.sync_parameters.sync_source})."
                    )
                    await sync_service.worker_synchronize_proposals_for_cycle_from_pass(
                        job.sync_parameters.cycle, job.sync_parameters.facility
                    )
                case JobActions.synchronize_proposal_types:
                    logger.info(
                        f"Processing job {job.id} to synchronize proposal types for the {job.sync_parameters.facility} facility (from {job.sync_parameters.sync_source})."
                    )
                    await sync_service.worker_synchronize_proposal_types_from_pass(
                        job.sync_parameters.facility
                    )
                case JobActions.create_slack_channel:
                    logger.info(
                        f"I would be Processing job {job.id} to create Slack channel for proposal {job.sync_parameters.proposal_id} if it was written."
                    )
                    # await proposal_service.worker_create_slack_channel(job.proposal_id)
                case _:
                    raise Exception(f"Unknown job action {job.action}.")

            await complete_job(job.id, JobStatus.success)

        except Exception as e:
            logger.exception(f"Error processing job {job.id} for {job.action}: {e}")
            error_message = traceback.format_exc()
            await complete_job(job.id, JobStatus.failed, error_message)
