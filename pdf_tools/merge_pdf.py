"""
merge_pdf.py: Merge several PDF files into a single PDF.

Combines the input PDFs (in the order given) into one output file.
The pages keep their original order: all pages of the first file,
then the second, and so on.

Requirements:
    pip install pypdf

Usage:
    python merge_pdf.py output.pdf input1.pdf input2.pdf [input3.pdf ...]

Example:
    python merge_pdf.py notes.pdf chapter1.pdf chapter2.pdf chapter3.pdf

Run with no arguments to merge the test files in samples/ into
samples/merged.pdf (generate them first with samples/make_test_pdfs.py).
"""

import sys
from pathlib import Path

from pypdf import PdfWriter

if len(sys.argv) >= 3:
    output = Path(sys.argv[1])
    inputs = [Path(p) for p in sys.argv[2:]]
else:
    # Demo mode: merge the bundled sample files
    samples = Path(__file__).resolve().parent / "samples"
    output = samples / "merged.pdf"
    inputs = [samples / f"file{i}.pdf" for i in (1, 2, 3)]
    print("No arguments given: merging the sample PDFs as a demo.\n")

for pdf in inputs:
    if not pdf.is_file():
        print(f"File not found: {pdf}")
        sys.exit(1)

# PdfWriter collects pages from several PDFs and writes them out as one file.
writer = PdfWriter()

for pdf in inputs:
    writer.append(str(pdf))  # append() adds every page of the given PDF
    print(f"Added {pdf}")

writer.write(str(output))
writer.close()

print(f"\nDone! Created {output}")
