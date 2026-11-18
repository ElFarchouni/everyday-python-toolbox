"""Generate sample PDFs (file1.pdf, file2.pdf, file3.pdf) for testing Merge_pdf.py."""
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

for i in range(1, 4):
    name = f"file{i}.pdf"
    c = canvas.Canvas(name, pagesize=A4)
    # give each file a different number of pages so the merge is easy to verify
    for page in range(1, i + 1):
        c.setFont("Helvetica-Bold", 28)
        c.drawCentredString(A4[0] / 2, A4[1] / 2 + 20, f"This is {name}")
        c.setFont("Helvetica", 18)
        c.drawCentredString(A4[0] / 2, A4[1] / 2 - 20, f"Page {page} of {i}")
        c.showPage()
    c.save()
    print(f"Created {name} ({i} page(s))")
