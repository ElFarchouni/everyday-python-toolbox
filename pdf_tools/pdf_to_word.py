"""
pdf_to_word.py: Convert a PDF into an editable Word document (.docx).

Keeps the layout as close as possible to the original: paragraphs, fonts,
tables, images and multi-column text are rebuilt in Word. Works best on
PDFs that contain real text (exported from Word, LaTeX, a browser...).
Scanned PDFs are just pictures of text: they need OCR first, so this tool
will produce a document with images only.

Requirements:
    pip install pdf2docx

Usage:
    python pdf_to_word.py input.pdf [output.docx] [--pages 1-5]

Examples:
    python pdf_to_word.py report.pdf                 # creates report.docx
    python pdf_to_word.py report.pdf essay.docx      # custom output name
    python pdf_to_word.py report.pdf --pages 3-7     # only pages 3 to 7
    python pdf_to_word.py report.pdf --pages 1,4,9   # only pages 1, 4 and 9
    python pdf_to_word.py notes/                     # every PDF in a folder

Run with no arguments to convert samples/merged.pdf as a demo
(create it first with merge_pdf.py).
"""

import argparse
import sys
from pathlib import Path

from pdf2docx import Converter

parser = argparse.ArgumentParser(description="Convert a PDF to an editable Word (.docx) file.")
parser.add_argument("input", nargs="?", help="PDF file, or a folder of PDFs to convert in bulk")
parser.add_argument("output", nargs="?", help="output .docx path (default: same name as input)")
parser.add_argument(
    "--pages",
    help="pages to convert, e.g. 1-5 or 1,4,9 (default: all pages)",
)
args = parser.parse_args()

if args.input:
    source = Path(args.input)
else:
    # Demo mode: convert the merged sample PDF
    source = Path(__file__).resolve().parent / "samples" / "merged.pdf"
    print("No arguments given: converting samples/merged.pdf as a demo.\n")

if not source.exists():
    print(f"File not found: {source}")
    sys.exit(1)


def parse_pages(spec):
    """Turn '1-5' or '1,4,9' into a list of 0-based page indexes (pdf2docx counts from 0)."""
    pages = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            pages.update(range(int(start), int(end) + 1))
        elif part:
            pages.add(int(part))
    if not pages or min(pages) < 1:
        raise ValueError
    return [p - 1 for p in sorted(pages)]


pages = None
if args.pages:
    try:
        pages = parse_pages(args.pages)
    except ValueError:
        print("Pages must look like 1-5 or 1,4,9 (page numbers start at 1).")
        sys.exit(1)


def convert(pdf, docx):
    """Convert one PDF file to one .docx file."""
    print(f"Converting {pdf} ...")
    converter = Converter(str(pdf))
    try:
        # pdf2docx analyses each page's layout (text blocks, tables, images)
        # and rebuilds it with python-docx. pages=None means the whole file.
        converter.convert(str(docx), pages=pages)
    finally:
        converter.close()
    print(f"  -> {docx}")


if source.is_dir():
    # Bulk mode: every PDF in the folder, each next to its original
    pdfs = sorted(source.glob("*.pdf"))
    if not pdfs:
        print(f"No PDF files found in {source}")
        sys.exit(1)
    if args.output:
        print("Note: output name is ignored when converting a folder.\n")
    for pdf in pdfs:
        convert(pdf, pdf.with_suffix(".docx"))
    print(f"\nDone! Converted {len(pdfs)} file(s) in {source}")
else:
    output = Path(args.output) if args.output else source.with_suffix(".docx")
    convert(source, output)
    print(f"\nDone! Created {output}")
    print("Tip: scanned PDFs come out as images only. Run OCR on them first.")
