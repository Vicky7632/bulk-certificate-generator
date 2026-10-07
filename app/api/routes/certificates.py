from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import (
    CertificateGeneration,
    CertificateGenerationStatus,
    GenerationJob,
    GenerationJobStatus,
)
from app.schemas.certificate import (
    CertificateJobCreate,
    CertificateJobCreateResponse,
)
from app.workers.certificate_worker import process_generation_job

router = APIRouter()


@router.post(
    "/jobs",
    response_model=CertificateJobCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_certificate_job(
    request: CertificateJobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CertificateJobCreateResponse:
    job = GenerationJob(
        event_name=request.event_name,
        organization_name=request.organization_name,
        issue_date=request.issue_date,
        total_count=len(request.recipients),
        success_count=0,
        failed_count=0,
        status=GenerationJobStatus.QUEUED,
    )

    try:
        db.add(job)
        db.flush()

        certificates = [
            CertificateGeneration(
                job_id=job.id,
                recipient_name=recipient.name,
                recipient_email=str(recipient.email),
                status=CertificateGenerationStatus.PENDING,
                file_path=None,
                error_message=None,
            )
            for recipient in request.recipients
        ]
        db.add_all(certificates)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create certificate job",
        ) from exc

    background_tasks.add_task(process_generation_job, job.id)

    return CertificateJobCreateResponse(
        job_id=job.id,
        status=job.status.value,
        total=job.total_count,
    )
