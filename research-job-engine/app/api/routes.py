import uuid

from fastapi import APIRouter, HTTPException, Request, status

from app.api.schemas import (
    CreateJobRequest,
    CreateJobResponse,
    JobResponse,
    ReportResponse,
    SourceOut,
)
from app.jobs.repository import JobRepository
from app.models import JobStatus

router = APIRouter(prefix="/api/v1")


def _repo(request: Request) -> JobRepository:
    return request.app.state.repo


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED, response_model=CreateJobResponse)
async def create_job(body: CreateJobRequest, request: Request) -> CreateJobResponse:
    job = await _repo(request).create_job(
        body.topic, request.app.state.settings.default_max_attempts
    )
    return CreateJobResponse(job_id=job.id, status=job.status)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: uuid.UUID, request: Request) -> JobResponse:
    found = await _repo(request).get_job(job_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    job, has_report = found
    return JobResponse(
        job_id=job.id,
        topic=job.topic,
        status=job.status,
        stage=(job.checkpoint or {}).get("stage"),
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        last_error=job.last_error,
        next_attempt_at=job.next_attempt_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        report_available=has_report,
    )


@router.get("/jobs/{job_id}/report", response_model=ReportResponse)
async def get_report(job_id: uuid.UUID, request: Request) -> ReportResponse:
    repo = _repo(request)
    found = await repo.get_report(job_id)
    if found is None:
        job = await repo.get_job(job_id)
        if job is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
        detail = (
            "job failed; no report"
            if job[0].status == JobStatus.FAILED
            else f"report not ready (status: {job[0].status.value})"
        )
        raise HTTPException(status.HTTP_409_CONFLICT, detail)
    report, sources = found
    return ReportResponse(
        job_id=report.job_id,
        content=report.content,
        sources=[SourceOut(url=s.url, title=s.title) for s in sources],
        created_at=report.created_at,
    )
