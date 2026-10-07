from collections.abc import Generator
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import (
    CertificateGeneration,
    CertificateGenerationStatus,
    GenerationJob,
    GenerationJobStatus,
)
from app.workers import certificate_worker


@pytest.fixture
def worker_database(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(certificate_worker, "SessionLocal", testing_session_local)
    monkeypatch.setattr(
        certificate_worker.settings,
        "generated_certificates_dir",
        str(tmp_path / "generated"),
    )

    try:
        yield testing_session_local
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_process_job_continues_after_certificate_failure(
    worker_database: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    with worker_database() as db:
        job = GenerationJob(
            event_name="Python Bootcamp 2026",
            organization_name="ABC Institute",
            issue_date=date(2026, 10, 7),
            total_count=3,
        )
        db.add(job)
        db.flush()
        job_id = job.id
        db.add_all(
            [
                CertificateGeneration(
                    job_id=job_id,
                    recipient_name=name,
                    recipient_email=f"{name.split()[0].lower()}@example.com",
                )
                for name in ("First Recipient", "Fail Recipient", "Last Recipient")
            ]
        )
        db.commit()

    processed_names: list[str] = []

    def mock_generate_certificate_pdf(
        recipient_name: str,
        event_name: str,
        organization_name: str,
        issue_date: date,
        output_path,
    ) -> str:
        processed_names.append(recipient_name)
        if recipient_name == "Fail Recipient":
            raise RuntimeError("intentional test failure")
        return str(output_path)

    monkeypatch.setattr(
        certificate_worker,
        "generate_certificate_pdf",
        mock_generate_certificate_pdf,
    )

    certificate_worker.process_generation_job(job_id)

    with worker_database() as db:
        job = db.get(GenerationJob, job_id)
        assert job is not None
        assert job.status is GenerationJobStatus.COMPLETED
        assert job.success_count == 2
        assert job.failed_count == 1
        assert job.started_at is not None
        assert job.completed_at is not None

        certificates = db.scalars(
            select(CertificateGeneration)
            .where(CertificateGeneration.job_id == job_id)
            .order_by(CertificateGeneration.recipient_name)
        ).all()
        certificate_by_name = {
            certificate.recipient_name: certificate for certificate in certificates
        }
        assert certificate_by_name["Fail Recipient"].status is (
            CertificateGenerationStatus.FAILED
        )
        assert certificate_by_name["Fail Recipient"].error_message == (
            "intentional test failure"
        )
        for name in ("First Recipient", "Last Recipient"):
            certificate = certificate_by_name[name]
            assert certificate.status is CertificateGenerationStatus.SUCCESS
            assert certificate.file_path == str(
                tmp_path
                / "generated"
                / str(job_id)
                / f"{certificate.id}.pdf"
            )
            assert certificate.completed_at is not None

    assert set(processed_names) == {
        "First Recipient",
        "Fail Recipient",
        "Last Recipient",
    }
    assert len(processed_names) == 3
