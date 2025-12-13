from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
from datetime import datetime


def generate_withdrawal_receipt_pdf(
    *,
    withdrawal_id: str,
    user_name: str,
    user_email: str,
    amount: float,
    currency: str,
    bank_name: str | None,
    clabe: str | None,
    account_holder: str | None,
    account_type: str | None,
    phone: str | None,
    status: str,
    stripe_transfer_id: str | None,
    created_at: datetime,
    processed_at: datetime | None,
    company_name: str = "Invertox",
) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, f"{company_name} — Comprobante de Retiro")
    y -= 30

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Withdrawal ID: {withdrawal_id}")
    y -= 15
    c.drawString(50, y, f"Status: {status}")
    y -= 15
    c.drawString(50, y, f"Created at: {created_at.isoformat()}")
    y -= 15
    if processed_at:
        c.drawString(50, y, f"Processed at: {processed_at.isoformat()}")
        y -= 15
    if stripe_transfer_id:
        c.drawString(50, y, f"Transfer reference: {stripe_transfer_id}")
        y -= 20

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Beneficiario / Cliente")
    y -= 18
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Nombre: {user_name}")
    y -= 14
    c.drawString(50, y, f"Email: {user_email}")
    y -= 14
    if phone:
        c.drawString(50, y, f"Tel: {phone}")
        y -= 14

    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Detalles del Retiro")
    y -= 18
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Monto: {amount:.2f} {currency}")
    y -= 14
    c.drawString(50, y, f"Banco: {bank_name or '-'}")
    y -= 14
    c.drawString(50, y, f"CLABE: {clabe or '-'}")
    y -= 14
    c.drawString(50, y, f"Titular: {account_holder or '-'}")
    y -= 14
    c.drawString(50, y, f"Tipo de cuenta: {account_type or '-'}")
    y -= 25

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, y, "Este comprobante es generado automáticamente.")
    c.showPage()
    c.save()

    return buf.getvalue()
