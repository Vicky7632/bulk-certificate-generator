import pytest
from pydantic import ValidationError

from app.schemas.certificate import CertificateJobCreate


def valid_request() -> dict:
    return {
        "event_name": "Python Bootcamp 2026",
        "organization_name": "ABC Institute",
        "issue_date": "2026-10-07",
        "recipients": [
            {"name": "Rahul Kumar", "email": "rahul@example.com"},
        ],
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("recipients", []),
        ("recipients", [{"name": "Rahul Kumar", "email": "invalid-email"}]),
        ("recipients", [{"name": "   ", "email": "rahul@example.com"}]),
        ("event_name", "   "),
        ("organization_name", "   "),
        ("issue_date", "not-a-date"),
    ],
)
def test_certificate_job_rejects_invalid_fields(field: str, value: object) -> None:
    request_data = valid_request()
    request_data[field] = value

    with pytest.raises(ValidationError):
        CertificateJobCreate.model_validate(request_data)


def test_certificate_job_rejects_more_than_1000_recipients() -> None:
    request_data = valid_request()
    request_data["recipients"] = [
        {"name": "Rahul Kumar", "email": "rahul@example.com"}
    ] * 1001

    with pytest.raises(ValidationError):
        CertificateJobCreate.model_validate(request_data)


def test_certificate_job_strips_whitespace_from_fields() -> None:
    request_data = valid_request()
    request_data["event_name"] = "  Python Bootcamp 2026  "
    request_data["organization_name"] = "  ABC Institute  "
    request_data["recipients"] = [
        {"name": "  Rahul Kumar  ", "email": "rahul@example.com"}
    ]

    parsed = CertificateJobCreate.model_validate(request_data)

    assert parsed.event_name == "Python Bootcamp 2026"
    assert parsed.organization_name == "ABC Institute"
    assert parsed.recipients[0].name == "Rahul Kumar"
