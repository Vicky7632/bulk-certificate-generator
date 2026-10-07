from datetime import date

from app.services.pdf_service import generate_certificate_pdf


def test_generate_certificate_pdf_creates_valid_file(tmp_path) -> None:
    output_path = tmp_path / "nested" / "certificates" / "rahul-kumar.pdf"

    result = generate_certificate_pdf(
        recipient_name="Rahul Kumar",
        event_name="Python Bootcamp 2026",
        organization_name="ABC Institute",
        issue_date=date(2026, 10, 7),
        output_path=output_path,
    )

    assert result == str(output_path)
    assert output_path.is_file()
    assert output_path.stat().st_size > 0
    assert output_path.read_bytes().startswith(b"%PDF")
