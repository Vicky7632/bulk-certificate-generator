from datetime import date
from os import PathLike
from pathlib import Path

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def generate_certificate_pdf(
    recipient_name: str,
    event_name: str,
    organization_name: str,
    issue_date: date,
    output_path: str | PathLike[str],
) -> str:
    """Generate a single participation certificate and return its file path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(str(path), pagesize=(page_width, page_height))

    margin = 14 * mm
    pdf.setStrokeColorRGB(0.16, 0.28, 0.42)
    pdf.setLineWidth(2)
    pdf.rect(
        margin,
        margin,
        page_width - 2 * margin,
        page_height - 2 * margin,
    )

    center_x = page_width / 2
    pdf.setFillColorRGB(0.12, 0.23, 0.36)
    pdf.setFont("Helvetica-Bold", 27)
    pdf.drawCentredString(center_x, page_height - 49 * mm, "CERTIFICATE OF PARTICIPATION")

    pdf.setFillColorRGB(0.2, 0.2, 0.2)
    pdf.setFont("Helvetica", 15)
    pdf.drawCentredString(center_x, page_height - 72 * mm, "This certificate is presented to")

    pdf.setFillColorRGB(0.12, 0.23, 0.36)
    pdf.setFont("Helvetica-Bold", 30)
    pdf.drawCentredString(center_x, page_height - 91 * mm, recipient_name)

    pdf.setFillColorRGB(0.2, 0.2, 0.2)
    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(center_x, page_height - 111 * mm, "for participating in")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(center_x, page_height - 123 * mm, event_name)

    pdf.setFont("Helvetica", 13)
    pdf.drawCentredString(center_x, page_height - 145 * mm, organization_name)
    pdf.drawCentredString(
        center_x,
        page_height - 163 * mm,
        f"Issued {issue_date.strftime('%B %d, %Y')}",
    )

    pdf.showPage()
    pdf.save()
    return str(path)
