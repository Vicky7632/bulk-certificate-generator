# Bulk Certificate Generator

## Overview

Bulk Certificate Generator is a FastAPI backend for accepting one request containing multiple certificate recipients. It validates the submitted data, records a generation job and its recipients in PostgreSQL, generates one PDF certificate per recipient from a predefined template, and provides job progress and certificate retrieval endpoints.

The API accepts the whole recipient batch in one request; clients do not need to submit one request per certificate.

## Features

- Bulk certificate generation requests
- Recipient and request-data validation
- PostgreSQL persistence for jobs, recipients, and processing status
- In-process background processing with FastAPI `BackgroundTasks`
- Job status and progress tracking
- Per-certificate failure isolation
- PDF generation using a predefined ReportLab template
- Retrieval of successfully generated PDF certificates
- Automated tests for API, validation, generation, failure handling, and retrieval

## Tech Stack

- Python 3.12+
- FastAPI
- PostgreSQL
- SQLAlchemy
- Pydantic and Pydantic Settings
- ReportLab
- pytest

## Architecture

```text
Bulk Request
    → Generation Job
    → Certificate Records
    → FastAPI Background Worker
    → PDF Generation
    → Database Status Updates
    → Certificate Retrieval
```

The request creates one `generation_jobs` row and one `certificate_generations` row for every recipient. After the transaction commits, a FastAPI background task processes the job. Each successful PDF is written to disk and the associated record is updated with its path and status.

The relational database has two main tables:

- **`generation_jobs`** stores the event and organization details, issue date, job status, recipient total, success/failure counters, and timestamps.
- **`certificate_generations`** stores each recipient, its status, generated file path, any error message, and timestamps.

One generation job has many certificate-generation records. Each certificate record references its parent job through `job_id`.

### Why BackgroundTasks?

FastAPI `BackgroundTasks` keeps processing straightforward for this take-home assignment without adding Redis, Celery, Kafka, or another queue service. The request commits the job and recipient records before scheduling the task.

`BackgroundTasks` runs in the application process and is **not** a durable, distributed job queue. Tasks can be interrupted by process restarts, and this approach is not intended for production-scale workloads. A production system could use a durable worker queue such as Celery or RQ, or a messaging platform such as Kafka, based on its requirements.

### Certificate Storage

PDF files are stored on the filesystem, not in PostgreSQL. The database stores only the generated file path. Files are grouped under a directory for their job:

```text
generated/{job_id}/{certificate_id}.pdf
```

The retrieval endpoint serves only certificates with `SUCCESS` status, checks that the stored path resolves to a file within `GENERATED_CERTIFICATES_DIR`, and returns the existing PDF without regenerating it.

### Failure Handling

Each recipient is processed independently. If generating one certificate fails:

- That certificate is marked `FAILED`.
- The exception message is stored in `error_message`.
- The job's `failed_count` is incremented.
- Processing continues with the remaining recipients.

If the worker finishes processing the job, its overall status is `COMPLETED` even when one or more individual certificates failed. `FAILED` is reserved for an unexpected job-level processing failure.

### Progress Calculation

Progress counts both successful and failed certificates as processed:

```text
progress = (successful + failed) / total * 100
pending = total - successful - failed
```

Consequently, a completed job can report 100% progress even when some certificates failed.

## API Endpoints

### Create a bulk generation job

`POST /api/v1/certificates/jobs`

Example request:

```json
{
  "event_name": "Python Bootcamp 2026",
  "organization_name": "ABC Institute",
  "issue_date": "2026-10-07",
  "recipients": [
    {
      "name": "Rahul Kumar",
      "email": "rahul@example.com"
    },
    {
      "name": "Priya Sharma",
      "email": "priya@example.com"
    }
  ]
}
```

Example response (`201 Created`):

```json
{
  "job_id": "2e9df989-d473-41af-970f-5de05c11a102",
  "status": "QUEUED",
  "total": 2
}
```

### Get job status and progress

`GET /api/v1/certificates/jobs/{job_id}`

Example response:

```json
{
  "job_id": "2e9df989-d473-41af-970f-5de05c11a102",
  "status": "PROCESSING",
  "total": 10,
  "successful": 6,
  "failed": 1,
  "pending": 3,
  "progress": 70.0
}
```

### Retrieve a certificate

`GET /api/v1/certificates/{certificate_id}`

Returns the generated PDF for a successful certificate as `application/pdf`. Certificates that are not successful, have no stored file, or whose file is missing are not available for retrieval.

## Project Structure

```text
app/
├── api/routes/       # Certificate API endpoints
├── core/             # Application settings
├── db/               # SQLAlchemy configuration and ORM models
├── schemas/          # Pydantic request and response schemas
├── services/         # Certificate workflow and PDF generation services
└── workers/          # Background job processing
templates/            # Predefined certificate template
generated/            # Generated PDF files (not committed)
tests/                # API, validation, worker, and PDF tests
Dockerfile            # FastAPI application image
docker-compose.yml    # Local FastAPI and PostgreSQL services
```

## Requirements

- Python 3.12 or newer
- PostgreSQL 16 or newer for local development
- Docker Compose v2 if using the container setup

## Local Setup

From the project directory in PowerShell, create and activate a virtual environment and install dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create a local PostgreSQL database named `bulk_certificate_db`. For example, using `psql` with a PostgreSQL server already running:

```powershell
createdb -U postgres bulk_certificate_db
```

Copy the example environment file and edit `.env` for your local PostgreSQL credentials:

```powershell
Copy-Item .env.example .env
```

Set the following values in `.env`:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/bulk_certificate_db
GENERATED_CERTIFICATES_DIR=generated
POSTGRES_PASSWORD=YOUR_LOCAL_PASSWORD
```

Use your own local password; do not commit `.env`. Create the tables for a fresh local database from the current SQLAlchemy models:

```powershell
python -c "import app.db.models; from app.db.database import Base, engine; Base.metadata.create_all(engine)"
```

## Run the Application

With PostgreSQL running and `.env` configured:

```powershell
uvicorn app.main:app --reload
```

Interactive API documentation is available at <http://127.0.0.1:8000/docs>.

## Run Tests

```powershell
python -m pytest -q
```

Tests use isolated SQLite databases where database behavior is required, and temporary directories for generated files. They do not require a running PostgreSQL server or committed/generated repository PDFs.

## Docker

The Compose setup starts the FastAPI application and PostgreSQL. It reads `POSTGRES_PASSWORD` from `.env`; set it to a local development password before starting the services. The application connects to the Compose database using the internal hostname `db`. Generated PDFs are mounted to the local `generated` directory.

```powershell
Copy-Item .env.example .env
# Edit .env and replace the local password placeholder.
docker compose up --build -d
```

For a fresh Compose database, create the tables from the SQLAlchemy models:

```powershell
docker compose exec app python -c "import app.db.models; from app.db.database import Base, engine; Base.metadata.create_all(engine)"
```

The API is then available at <http://127.0.0.1:8000>, with Swagger at <http://127.0.0.1:8000/docs>. To stop the services without deleting database data:

```powershell
docker compose down
```

## Design Decisions

- **FastAPI** provides request validation, dependency injection, and the HTTP API.
- **PostgreSQL** stores relational job and per-recipient status data.
- **SQLAlchemy** maps the job and certificate records to relational tables.
- **FastAPI BackgroundTasks** keeps this take-home's background processing simple and in-process.
- **Filesystem PDF storage** avoids storing binary documents in database rows.
- **Database-backed counters** support progress queries without loading every certificate record.
- **UUID identifiers** provide unique job and certificate identifiers.
- **UTC timestamps** provide consistent, timezone-aware processing times.
- **Per-certificate failure isolation** lets the worker continue after an individual generation error.

## Testing / Assignment Coverage

- [x] Generation job creation and recipient records
- [x] Input validation, including recipient limits and whitespace handling
- [x] PDF certificate generation and content
- [x] Job status, pending count, progress, and missing-job response
- [x] Individual certificate failure isolation and job completion
- [x] Successful certificate retrieval and unavailable/missing-file handling

## Limitations / Future Improvements

- Use a durable distributed queue for production-scale background processing.
- Store generated PDFs in object storage such as S3 for distributed deployments.
- Add database migrations with Alembic.
- Add authentication and authorization before public exposure.
- Add a retry policy for transient generation failures.
