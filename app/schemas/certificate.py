from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, StringConstraints


RecipientName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=100),
]
JobName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class RecipientCreate(BaseModel):
    name: RecipientName
    email: EmailStr


class CertificateJobCreate(BaseModel):
    event_name: JobName
    organization_name: JobName
    issue_date: date
    recipients: list[RecipientCreate] = Field(min_length=1, max_length=1000)


class CertificateJobCreateResponse(BaseModel):
    job_id: UUID
    status: str
    total: int


class CertificateStatusResponse(BaseModel):
    id: UUID
    recipient_name: str
    recipient_email: EmailStr
    status: str
    file_path: str | None = None
    error_message: str | None = None


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    total: int
    successful: int
    failed: int
    pending: int
    progress: float = Field(ge=0, le=100)
