import base64
from datetime import date
import re
import zlib

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
    pdf_bytes = output_path.read_bytes()
    assert pdf_bytes.startswith(b"%PDF")

    encoded_content = re.search(
        rb"stream\s*(.*?)\s*endstream",
        pdf_bytes,
        re.DOTALL,
    )
    assert encoded_content is not None
    decoded_content = zlib.decompress(
        base64.a85decode(encoded_content.group(1), adobe=True)
    )
    assert b"Rahul Kumar" in decoded_content
    assert b"Python Bootcamp 2026" in decoded_content
    assert b"ABC Institute" in decoded_content
