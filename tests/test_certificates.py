from collections.abc import Generator
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.database import Base, get_db
from app.db.models import (
    CertificateGeneration,
    CertificateGenerationStatus,
    GenerationJob,
)
from app.main import app


@pytest.fixture
def certificate_database(
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
    monkeypatch.setattr(
        settings,
        "generated_certificates_dir",
        str(tmp_path / "generated"),
    )

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


def create_certificate(
    test_database: sessionmaker[Session],
    *,
    status: CertificateGenerationStatus,
    file_path: str | None = None,
) -> CertificateGeneration:
    with test_database() as db:
        job = GenerationJob(
            event_name="Python Bootcamp 2026",
            organization_name="ABC Institute",
            issue_date=date(2026, 10, 7),
            total_count=1,
        )
        db.add(job)
        db.flush()
        certificate = CertificateGeneration(
            job_id=job.id,
            recipient_name="Rahul Kumar",
            recipient_email="rahul@example.com",
            status=status,
            file_path=file_path,
        )
        db.add(certificate)
        db.commit()
        db.refresh(certificate)
        return certificate


def test_download_successful_certificate(
    certificate_database: sessionmaker[Session],
    tmp_path,
) -> None:
    output_path = tmp_path / "generated" / "test-job" / "certificate.pdf"
    output_path.parent.mkdir(parents=True)
    pdf_content = b"%PDF-1.4\nsample certificate\n%%EOF"
    output_path.write_bytes(pdf_content)
    certificate = create_certificate(
        certificate_database,
        status=CertificateGenerationStatus.SUCCESS,
        file_path=str(output_path),
    )

    with TestClient(app) as client:
        response = client.get(f"/api/v1/certificates/{certificate.id}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].endswith(
        f'filename="certificate-{certificate.id}.pdf"'
    )
    assert response.content == pdf_content


def test_download_missing_certificate_returns_404(
    certificate_database: sessionmaker[Session],
) -> None:
    with TestClient(app) as client:
        response = client.get(f"/api/v1/certificates/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Certificate not found"}


@pytest.mark.parametrize(
    "certificate_status",
    [
        CertificateGenerationStatus.PENDING,
        CertificateGenerationStatus.FAILED,
    ],
)
def test_download_unavailable_certificate_returns_404(
    certificate_database: sessionmaker[Session],
    certificate_status: CertificateGenerationStatus,
) -> None:
    certificate = create_certificate(
        certificate_database,
        status=certificate_status,
        file_path="should-not-be-served.pdf",
    )

    with TestClient(app) as client:
        response = client.get(f"/api/v1/certificates/{certificate.id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Certificate is not available"}


def test_download_successful_certificate_without_file_path_returns_404(
    certificate_database: sessionmaker[Session],
) -> None:
    certificate = create_certificate(
        certificate_database,
        status=CertificateGenerationStatus.SUCCESS,
    )

    with TestClient(app) as client:
        response = client.get(f"/api/v1/certificates/{certificate.id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Certificate file not found"}


def test_download_successful_certificate_with_missing_file_returns_404(
    certificate_database: sessionmaker[Session],
    tmp_path,
) -> None:
    missing_path = tmp_path / "generated" / "missing.pdf"
    certificate = create_certificate(
        certificate_database,
        status=CertificateGenerationStatus.SUCCESS,
        file_path=str(missing_path),
    )

    with TestClient(app) as client:
        response = client.get(f"/api/v1/certificates/{certificate.id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Certificate file not found"}


def test_download_rejects_file_outside_generated_directory(
    certificate_database: sessionmaker[Session],
    tmp_path,
) -> None:
    outside_path = tmp_path / "outside.pdf"
    outside_path.write_bytes(b"%PDF-1.4\nnot in generated directory\n%%EOF")
    certificate = create_certificate(
        certificate_database,
        status=CertificateGenerationStatus.SUCCESS,
        file_path=str(outside_path),
    )

    with TestClient(app) as client:
        response = client.get(f"/api/v1/certificates/{certificate.id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Certificate file not found"}
