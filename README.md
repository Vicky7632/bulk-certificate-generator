# Bulk Certificate Generator

Initial project scaffold for the Bulk Certificate Generator.

## Local setup

Create and activate a virtual environment, then install the dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `DATABASE_URL` to `postgresql+psycopg://postgres:postgres@localhost:5432/bulk_certificates`. This connects to the local PostgreSQL service configured in `docker-compose.yml`.

Start PostgreSQL:

```powershell
docker compose up -d db
```

Start the FastAPI development server:

```powershell
uvicorn app.main:app --reload
```

## Run tests

```powershell
pytest
```
