from datetime import date
from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.db.models import (
    CertificateGeneration,
    CertificateGenerationStatus,
    GenerationJob,
    GenerationJobStatus,
)
from app.main import app


@pytest.fixture
def test_database() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield testing_session_local
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_create_certificate_job(
    test_database: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.routes.certificates.process_generation_job",
        lambda job_id: None,
    )

    payload = {
        "event_name": "Python Bootcamp 2026",
        "organization_name": "ABC Institute",
        "issue_date": "2026-10-07",
        "recipients": [
            {"name": "Rahul Kumar", "email": "rahul@example.com"},
            {"name": "Priya Sharma", "email": "priya@example.com"},
        ],
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/certificates/jobs", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"job_id", "status", "total"}
    assert body["status"] == GenerationJobStatus.QUEUED.value
    assert body["total"] == 2

    with test_database() as db:
        job = db.get(GenerationJob, UUID(body["job_id"]))
        assert job is not None
        assert job.total_count == 2
        assert job.success_count == 0
        assert job.failed_count == 0
        assert job.status is GenerationJobStatus.QUEUED

        certificates = db.scalars(
            select(CertificateGeneration).where(
                CertificateGeneration.job_id == job.id
            )
        ).all()
        assert len(certificates) == 2
        assert {certificate.recipient_name for certificate in certificates} == {
            "Rahul Kumar",
            "Priya Sharma",
        }
        assert all(
            certificate.status is CertificateGenerationStatus.PENDING
            and certificate.file_path is None
            and certificate.error_message is None
            for certificate in certificates
        )


def test_get_job_status_calculates_progress(
    test_database: sessionmaker[Session],
) -> None:
    with test_database() as db:
        job = GenerationJob(
            event_name="Status Test",
            organization_name="ABC Institute",
            issue_date=date(2026, 10, 7),
            total_count=5,
            success_count=3,
            failed_count=1,
            status=GenerationJobStatus.PROCESSING,
        )
        db.add(job)
        db.commit()
        job_id = job.id

    with TestClient(app) as client:
        response = client.get(f"/api/v1/certificates/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": str(job_id),
        "status": "PROCESSING",
        "total": 5,
        "successful": 3,
        "failed": 1,
        "pending": 1,
        "progress": 80.0,
    }


def test_get_job_status_returns_404_for_missing_job(
    test_database: sessionmaker[Session],
) -> None:
    with TestClient(app) as client:
        response = client.get(f"/api/v1/certificates/jobs/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Generation job not found"}


def test_get_completed_job_status_has_full_progress(
    test_database: sessionmaker[Session],
) -> None:
    with test_database() as db:
        job = GenerationJob(
            event_name="Completed Status Test",
            organization_name="ABC Institute",
            issue_date=date(2026, 10, 7),
            total_count=3,
            success_count=2,
            failed_count=1,
            status=GenerationJobStatus.COMPLETED,
        )
        db.add(job)
        db.commit()
        job_id = job.id

    with TestClient(app) as client:
        response = client.get(f"/api/v1/certificates/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["pending"] == 0
    assert response.json()["progress"] == 100.0
