from collections.abc import Generator
from uuid import UUID

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


def test_create_certificate_job(test_database: sessionmaker[Session]) -> None:
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
