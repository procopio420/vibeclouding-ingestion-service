from fastapi import APIRouter, HTTPException
from app.db import get_session, JobModel

router = APIRouter()


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    session = get_session()
    job = session.query(JobModel).filter(JobModel.id == job_id).first()
    session.close()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.id,
        "project_id": job.project_id,
        "job_type": job.job_type,
        "status": job.status,
        "payload": job.payload,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "retries": job.retries,
    }


@router.get("/projects/{project_id}/jobs")
async def get_jobs_by_project(project_id: str):
    session = get_session()
    jobs = session.query(JobModel).filter(JobModel.project_id == project_id).all()
    session.close()
    return [
        {
            "job_id": j.id,
            "job_type": j.job_type,
            "status": j.status,
            "created_at": j.created_at,
            "started_at": j.started_at,
            "completed_at": j.completed_at,
        }
        for j in jobs
    ]
