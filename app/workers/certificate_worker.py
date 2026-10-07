from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import (
    CertificateGeneration,
    CertificateGenerationStatus,
    GenerationJob,
    GenerationJobStatus,
)
from app.services.pdf_service import generate_certificate_pdf


def process_generation_job(job_id: UUID) -> None:
    db = SessionLocal()
    try:
        job = db.get(GenerationJob, job_id)
        if job is None or job.status is not GenerationJobStatus.QUEUED:
            return

        job.status = GenerationJobStatus.PROCESSING
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        certificates = db.scalars(
            select(CertificateGeneration).where(
                CertificateGeneration.job_id == job_id
            )
        ).all()

        for certificate in certificates:
            certificate_id = certificate.id
            certificate.status = CertificateGenerationStatus.PROCESSING
            db.commit()

            try:
                output_path = (
                    Path(settings.generated_certificates_dir)
                    / str(job_id)
                    / f"{certificate_id}.pdf"
                )
                generated_path = generate_certificate_pdf(
                    recipient_name=certificate.recipient_name,
                    event_name=job.event_name,
                    organization_name=job.organization_name,
                    issue_date=job.issue_date,
                    output_path=output_path,
                )

                certificate.status = CertificateGenerationStatus.SUCCESS
                certificate.file_path = generated_path
                certificate.error_message = None
                certificate.completed_at = datetime.now(timezone.utc)
                job.success_count += 1
                db.commit()
            except Exception as exc:
                db.rollback()
                certificate = db.get(CertificateGeneration, certificate_id)
                job = db.get(GenerationJob, job_id)
                if certificate is None or job is None:
                    raise

                certificate.status = CertificateGenerationStatus.FAILED
                certificate.error_message = str(exc)
                certificate.completed_at = datetime.now(timezone.utc)
                job.failed_count += 1
                db.commit()

        job = db.get(GenerationJob, job_id)
        if job is not None:
            job.status = GenerationJobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:
        db.rollback()
        try:
            job = db.get(GenerationJob, job_id)
            if job is not None:
                job.status = GenerationJobStatus.FAILED
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()
