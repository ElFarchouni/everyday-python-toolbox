"""
article_to_word.py: Convert a research article (PDF) into a clean, editable Word document.

Made for scientific papers: one- or two-column layouts, figures, tables and
equations. pdf_to_word.py copies the page layout exactly (text boxes, frames,
fixed positions). This tool instead *reflows* the article into a normal Word
document that you can edit, translate or quote from:

  - two-column pages are read in the right order (left column, then right)
  - title, section headings (Heading 1/2/3), captions and references get real
    Word styles, so the Navigation Pane shows the article's outline
  - running headers, footers, page numbers and margin stamps are removed
  - words hyphenated at line ends are joined, and paragraphs broken across
    columns or pages are stitched back together
  - figures, tables and display equations are kept as sharp images, exactly
    as they look in the PDF
  - bold, italic and superscript text (citations, footnote marks) is kept

Requirements:
    pip install pymupdf python-docx      (both come with pdf2docx too)

Usage:
    python article_to_word.py article.pdf [output.docx] [--pages 1-5] [--no-figures] [--dpi 200]

Examples:
    python article_to_word.py paper.pdf                  # creates paper.docx
    python article_to_word.py paper.pdf notes.docx       # custom output name
    python article_to_word.py paper.pdf --pages 1-8      # skip the appendix
    python article_to_word.py paper.pdf --no-figures     # text only
    python article_to_word.py papers/                    # every PDF in a folder

Which tool should I use?
    article_to_word.py  -> papers and reports you want to read, edit or translate
    pdf_to_word.py      -> documents whose exact look matters (forms, CVs, flyers)

Limitations: scanned PDFs contain no real text, so their pages come out as
images (run OCR on them first). Tables become pictures, not editable Word tables.
"""

import argparse
import io
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Inches, Pt, RGBColor

# Windows terminals can't print every character (accents, Arabic file names...)
sys.stdout.reconfigure(errors="replace")
# Recent PyMuPDF versions print an advert for an add-on package; we don't need it
getattr(fitz, "no_recommend_layout", lambda: None)()

GAP = 8            # points: pieces of a figure closer than this belong together
LABEL_GAP = 14     # points: short labels (axis names, panel titles) can sit a bit further away

MATH_FONT = re.compile(r"cmmi|cmsy|cmex|msbm|msam|math|symbol|stix|euclid|mt ?extra|rsfs|eufm", re.I)
BOLD_FONT = re.compile(r"bold|black|heavy|semibold|demi|cmbx", re.I)
ITALIC_FONT = re.compile(r"italic|oblique|cmti", re.I)
LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"})
# Control and private-use characters: invisible in the PDF, and Word refuses control characters
SOFT_HYPHEN = "\u00ad"   # invisible hyphenation point some publishers (Elsevier) put at line ends
JUNK = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ue000-\uf8ff\ufeff\ufffd]")
# LaTeX draws accents as a separate character: "M¨uller", "Doll´ar", "Fran¸cois" -> Müller, Dollár, François
ACCENTS = {"¨": "\u0308", "´": "\u0301", "ˆ": "\u0302", "˜": "\u0303", "ˇ": "\u030c", "˚": "\u030a", "¸": "\u0327"}
LOOSE_ACCENT = re.compile(r"([¨´ˆ˜ˇ˚¸])([AaEeIiOoUuYyıNnCcSsZzRrGgLl])|([cC])¸")

CAPTION = re.compile(r"^(fig(ure|\.)?|tab(le|leau|\.)?|algorithm|algorithme|scheme|chart|listing)\s*([A-Z]?\d+|[IVXL]+)[a-z]?\s*([.:|\u2014–-]|$)", re.I)
CAPTION_LOOSE = re.compile(r"^(fig(ure|\.)?|tab(le|leau|\.)?)\s*([A-Z]?\d+|[IVXL]+)\b", re.I)
# A caption label at the start of a line inside a block: the caption starts there ("TABLE 1", "Fig. 3. ...")
CAPTION_LINE = re.compile(r"^(TABLE|TABLEAU|FIGURE)\s+([IVXL]+|\d+)\b|^(Fig\.|Figure|Table|Tableau)\s*\d+\s?[.:]\s")
NUMBER = re.compile(r"[-+±−]?\(?[\d.,]+\)?%?|n/a|[-–\u2014]")
NUMBERED = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+\S")
ROMAN = re.compile(r"^[IVX]{1,4}\.\s+\S")
LETTERED = re.compile(r"^[A-H]\.\s+[A-Z]")
SECTION = re.compile(
    r"^((\d+(\.\d+)*|[IVX]+|[A-Z])\.?\s+)?(abstract|introduction|background|related work|"
    r"methods?|methodology|materials and methods|experiments?|results?( and discussion)?|discussion|"
    r"conclusions?( and future work)?|acknowledge?ments?|references|bibliography|appendix\b.*|"
    r"keywords?|résumé|conclusion générale|références( bibliographiques)?|"
    # French
    r"méthodes?|méthodologie|matériels? et méthodes|résultats?( et discussion)?|conclusions?( et perspectives)?|"
    r"remerciements|bibliographie|annexes?\b.*|mots[- ]clés|état de l'art|travaux connexes)\s*[.:]?$",
    re.I,
)
REFERENCES = re.compile(r"^((\d+|[IVX]+)\.?\s+)?(references|bibliography|works cited|literature cited|"
                        r"références( bibliographiques)?|bibliographie)$", re.I)
REF_BRACKET = re.compile(r"^\s*\[\d{1,3}\]")
REF_START = re.compile(r"^\s*(\[\d{1,3}\]|\d{1,3}\.\s|\(\d{1,3}\)\s)")
BULLET = re.compile(r"^[•●▪■◦○∙]\s")
# A sentence can't end on these words, so the text after them is the same paragraph
CONNECTOR = re.compile(r"\b(the|a|an|of|in|on|at|to|for|from|with|by|and|or|as|is|are|was|were|that|"
                       r"le|la|les|un|une|des|du|de|et|ou|en|au|aux|par|pour|sur|dans|avec|est|sont|que)$", re.I)
EQUATION_NUMBER = re.compile(r"^\(\d{1,3}[a-z]?\)$")
PAGE_NUMBER = re.compile(r"^(page\s*)?#(\s*(of|/)\s*#)?$|^[-–]\s*#\s*[-–]$")


# ----------------------------------------------------------------------------
# Data structures
# ----------------------------------------------------------------------------

@dataclass
class Run:
    """A piece of text with one formatting."""
    text: str
    bold: bool = False
    italic: bool = False
    sup: bool = False
    size: float = 0
    math: bool = False


@dataclass
class Line:
    runs: list
    rect: fitz.Rect

    @property
    def text(self):
        return "".join(r.text for r in self.runs).strip()


@dataclass
class Block:
    """A group of lines that PyMuPDF found together on the page."""
    lines: list
    page: int
    kind: str = "text"   # becomes: title, heading, front, body, ref, caption, footnote, equation, gone
    level: int = 1
    rect: fitz.Rect = None
    size: float = 0      # main font size, weighted by character count
    bold: float = 0      # share of characters in bold
    italic: float = 0    # share of characters in italic
    math: float = 0      # share of characters in a math font
    col_end: bool = False   # lowest text of its column: a sentence cut here goes on in the next column

    def __post_init__(self):
        self.rect = fitz.Rect(self.lines[0].rect)
        for line in self.lines[1:]:
            self.rect = union(self.rect, line.rect)
        counted = [(len(r.text.strip()), r) for line in self.lines for r in line.runs]
        total = sum(n for n, _ in counted) or 1
        self.size = main_size([r for _, r in counted])
        self.bold = sum(n for n, r in counted if r.bold) / total
        self.italic = sum(n for n, r in counted if r.italic) / total
        self.math = sum(n for n, r in counted if r.math) / total

    @property
    def text(self):
        return " ".join(line.text for line in self.lines)

    @property
    def words(self):
        return len(self.text.split())


@dataclass
class Picture:
    """A figure, table or equation, rendered from the page as an image."""
    rect: fitz.Rect
    kind: str            # "figure" or "equation"
    page: int = 0
    clip: fitz.Rect = None
    png: bytes = b""


@dataclass
class Element:
    """One paragraph (or picture) of the final Word document."""
    kind: str
    runs: list = field(default_factory=list)
    level: int = 1
    lines: list = field(default_factory=list)   # front matter keeps its line breaks
    picture: Picture = None
    col_end: bool = False


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------

def main_size(runs):
    """Most common font size among runs, weighted by number of characters."""
    sizes = Counter()
    for r in runs:
        sizes[round(r.size * 2) / 2] += len(r.text.strip())
    sizes.pop(0, None)
    return sizes.most_common(1)[0][0] if sizes else 0


def plain(runs):
    return "".join(r.text for r in runs)


def near(a, b, gap):
    """True if rectangles a and b touch once both are grown by gap (works for flat lines too)."""
    return a.x0 - gap <= b.x1 and b.x0 - gap <= a.x1 and a.y0 - gap <= b.y1 and b.y0 - gap <= a.y1


def share_inside(inner, outer):
    """Fraction of rectangle inner that lies inside rectangle outer."""
    w = min(inner.x1, outer.x1) - max(inner.x0, outer.x0)
    h = min(inner.y1, outer.y1) - max(inner.y0, outer.y0)
    if w <= 0 or h <= 0:
        return 0
    return w * h / max(inner.width * inner.height, 1e-6)


def union(a, b):
    """Smallest rectangle around a and b. (PyMuPDF's own "|" ignores flat rule lines.)"""
    return fitz.Rect(min(a.x0, b.x0), min(a.y0, b.y0), max(a.x1, b.x1), max(a.y1, b.y1))


def clamp(rect, page_rect):
    return fitz.Rect(
        max(rect.x0, page_rect.x0), max(rect.y0, page_rect.y0),
        min(rect.x1, page_rect.x1), min(rect.y1, page_rect.y1),
    )


def parse_pages(spec, page_count):
    """Turn '1-5' or '1,4,9' into a sorted list of 0-based page indexes."""
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
    return [p - 1 for p in sorted(pages) if p <= page_count]


# ----------------------------------------------------------------------------
# Step 1: read the text of a page into blocks of lines and formatted runs
# ----------------------------------------------------------------------------

def read_blocks(page, page_no):
    blocks = []
    # No TEXT_PRESERVE_LIGATURES flag, so "ﬁ" comes out as "fi"
    for b in page.get_text("dict", flags=fitz.TEXT_MEDIABOX_CLIP)["blocks"]:
        lines = []
        for l in b["lines"]:
            if abs(l["dir"][1]) > 0.05:   # rotated text: arXiv margin stamp, axis titles
                continue
            runs = []
            for s in l["spans"]:
                text = re.sub(r"\s+", " ", JUNK.sub("", s["text"].translate(LIGATURES)))
                if text:
                    runs.append(Run(
                        text,
                        bold=bool(s["flags"] & 16 or BOLD_FONT.search(s["font"])),
                        italic=bool(s["flags"] & 2 or ITALIC_FONT.search(s["font"])),
                        sup=bool(s["flags"] & 1),
                        size=s["size"],
                        math=bool(MATH_FONT.search(s["font"])),
                    ))
            if not plain(runs).strip():
                continue
            spaced = plain(runs).strip()
            if re.fullmatch(r"[^\W\d_]( {1,3}[^\W\d_]){3,}", spaced):
                # Letter-spaced heading "A R T I C L E  I N F O" -> "ARTICLE INFO"
                words = [w.replace(" ", "") for w in re.split(r" {2,}", spaced)]
                runs = [Run(" ".join(words), runs[0].bold, runs[0].italic, size=runs[0].size)]
            rect = fitz.Rect(l["bbox"])
            prev = lines[-1] if lines else None
            if prev and abs(rect.y1 - prev.rect.y1) < 2 and rect.x0 >= prev.rect.x1 - 2:
                if rect.x0 - prev.rect.x1 < 3 * main_size(runs):
                    # Same line, e.g. "[12]" and its reference text arrive as two pieces
                    prev.runs += [Run(" ")] + runs
                    prev.rect = union(prev.rect, rect)
                    continue
                # Far apart on the same line (e.g. labels of two side-by-side figures): separate blocks
                blocks.extend(split_leading_heading(Block(lines, page_no)))
                lines = []
            elif lines and CAPTION_LINE.match(plain(runs).strip()):
                # A caption glued under a table or figure: the caption starts its own block
                blocks.extend(split_leading_heading(Block(lines, page_no)))
                lines = []
            lines.append(Line(runs, rect))
        if lines:
            blocks.extend(split_leading_heading(Block(lines, page_no)))
    # Drop symbol-only leftovers (decorative glyphs like "!" or "•"), but keep math
    return [b for b in blocks if re.search(r"\w", b.text) or b.math >= 0.5]


def split_leading_heading(block):
    """A short bold (or bigger) first line glued to a paragraph is really a heading."""
    if len(block.lines) < 2:
        return [block]
    first, rest = block.lines[0], block.lines[1:]
    first_runs = [r for r in first.runs if r.text.strip()]
    rest_runs = [r for line in rest for r in line.runs if r.text.strip()]
    standout = (
        (all(r.bold for r in first_runs) and not all(r.bold for r in rest_runs))
        or main_size(first_runs) >= 1.12 * main_size(rest_runs)
    )
    short = len(first.text.split()) <= 12 and first.rect.x1 < block.rect.x1 - 0.15 * block.rect.width
    if standout and short and not first.text.endswith((".", ",", ";")):
        return [Block([first], block.page), Block(rest, block.page)]
    return [block]


# ----------------------------------------------------------------------------
# Step 2: find what to ignore: running headers, footers, page numbers
# ----------------------------------------------------------------------------

def remove_headers_footers(pages_blocks, page_heights):
    def margin_key(block, height):
        if len(block.lines) <= 2 and (block.rect.y1 < 0.1 * height or block.rect.y0 > 0.9 * height):
            return re.sub(r"\d+", "#", block.text.lower()).strip()
        return None

    seen = defaultdict(set)
    for page_no, blocks in pages_blocks.items():
        for b in blocks:
            key = margin_key(b, page_heights[page_no])
            if key:
                seen[key].add(page_no)

    repeated = max(2, 0.4 * len(pages_blocks))
    for page_no, blocks in pages_blocks.items():
        removed = []
        for b in blocks:
            key = margin_key(b, page_heights[page_no])
            if key and (len(seen[key]) >= repeated or PAGE_NUMBER.match(key)):
                removed.append(b)
        if len(removed) < len(blocks):   # never empty a whole page: then it wasn't a header
            for b in removed:
                b.kind = "gone"


def tag_block(b, body, page_height):
    """First guess of what a block is, from its own look (before page layout is known)."""
    text = b.text
    if CAPTION.match(text) or (CAPTION_LOOSE.match(text) and b.size < 0.97 * body):
        b.kind = "caption"
    elif (b.size < 0.95 * body and b.rect.y0 > 0.7 * page_height and b.bold < 0.5
          and (b.lines[0].runs[0].sup or re.match(r"^[\d*†‡§¶∗]", text))):
        b.kind = "footnote"   # (bold small text at the page bottom is a heading like "2 RELATED WORK")
    elif b.math >= 0.3 and len(b.lines) <= 6:
        prose = re.findall(r"[A-Za-z]{4,}", "".join(r.text for line in b.lines for r in line.runs if not r.math))
        if len(prose) <= 4:
            b.kind = "equation"


# ----------------------------------------------------------------------------
# Step 3: find figures, tables and equations and turn them into pictures
# ----------------------------------------------------------------------------

def join_caption_labels(blocks, body):
    """A label alone on its line ("Table 1") with the caption text in the block below: make them one caption."""
    for cap in blocks:
        if cap.kind != "caption" or cap.words > 3:
            continue
        below = [b for b in blocks if b.kind == "text" and b.size < 1.05 * body
                 and -0.6 * cap.size <= b.rect.y0 - cap.rect.y1 <= cap.size
                 and b.rect.x0 < cap.rect.x1 + 50 and b.rect.x1 > cap.rect.x0]
        if below:
            title = min(below, key=lambda b: b.rect.y0)
            cap.lines += title.lines
            cap.rect = union(cap.rect, title.rect)
            title.kind = "gone"


def mostly_numbers(b):
    tokens = b.text.split()
    return len(tokens) >= 6 and sum(bool(NUMBER.fullmatch(t)) for t in tokens) >= 0.5 * len(tokens)


def find_gutter(blocks, page_width, body):
    """x position of the gap between two text columns, or None for a one-column page."""
    # Normal body text first: small print (affiliations, keyword boxes) can use a different grid.
    # Pages of small print only (references) fall back to all text.
    for body_size_only in (True, False):
        narrow = [b for b in blocks if b.kind in ("text", "caption") and b.words >= 8
                  and b.rect.width < 0.6 * page_width
                  and (not body_size_only or 0.85 * body <= b.size <= 1.15 * body)]
        left = [b for b in narrow if (b.rect.x0 + b.rect.x1) / 2 < page_width / 2]
        right = [b for b in narrow if (b.rect.x0 + b.rect.x1) / 2 >= page_width / 2]
        if sum(b.words for b in left) >= 30 and sum(b.words for b in right) >= 30:
            left_edge = statistics.median(b.rect.x1 for b in left)
            # The right column starts at its leftmost block (others may be indented, e.g. next to a photo)
            right_edge = min((b.rect.x0 for b in right if b.rect.x0 >= left_edge - 2),
                             default=statistics.median(b.rect.x0 for b in right))
            return (left_edge + right_edge) / 2
    return None


def column_of(rect, gutter):
    if gutter is None:
        return "page"
    if rect.x1 <= gutter + 3:
        return "left"
    if rect.x0 >= gutter - 3:
        return "right"
    return "both"


def tag_numbered_equations(blocks, gutter):
    """A short line with "(2)" at the right margin is a display equation, whatever its fonts."""
    for num in blocks:
        if num.kind != "text" or not EQUATION_NUMBER.match(num.text):
            continue
        for b in blocks:
            if (b is not num and b.kind == "text" and b.words <= 20 and len(b.lines) <= 3
                    and b.rect.x1 < num.rect.x0 and b.rect.y0 < num.rect.y1 and b.rect.y1 > num.rect.y0
                    and column_of(b.rect, gutter) == column_of(num.rect, gutter)):
                b.kind = "equation"


def ruled_tables(rules, captions):
    """Tables drawn with horizontal rules only (LaTeX booktabs), found from their "Table N" caption."""
    rules = [r for r in rules if r.width > 40]
    found = []
    for cap in captions:
        if not re.match(r"tab", cap.text, re.I):
            continue
        for below in (True, False):   # the table usually sits below its caption, sometimes above

            def gap(r, ref):
                return r.y0 - ref.y1 if below else ref.y0 - r.y1

            first = [r for r in rules if -1 <= gap(r, cap.rect) <= 25 and r.x0 < cap.rect.x1 and r.x1 > cap.rect.x0]
            if not first:
                continue
            group = [min(first, key=lambda r: gap(r, cap.rect))]
            aligned = sorted(
                (r for r in rules if abs(r.x0 - group[0].x0) < 10 and abs(r.x1 - group[0].x1) < 10),
                key=lambda r: r.y0 if below else -r.y0,
            )
            for r in aligned:
                between = fitz.Rect(r.x0, min(r.y1, group[-1].y1), r.x1, max(r.y0, group[-1].y0))
                other_caption = any(c is not cap and share_inside(c.rect, between) > 0.5 for c in captions)
                if 0 < gap(r, group[-1]) <= 300 and not other_caption:
                    group.append(r)
            if len(group) >= 2:
                rect = fitz.Rect(group[0])
                for r in group[1:]:
                    rect = union(rect, r)
                found.append(rect)
                break
    return found


def text_tables(captions, text_blocks, body):
    """Tables with no lines at all: the short, cell-like blocks right below (or above) a "Table N" caption."""
    found = []
    for cap in captions:
        if not re.match(r"tab", cap.text, re.I):
            continue
        for below in (True, False):
            candidates = sorted(
                (b for b in text_blocks if b.kind == "text"
                 and b.rect.x0 < cap.rect.x1 + 5 and b.rect.x1 > cap.rect.x0 - 5
                 and (b.rect.y0 >= cap.rect.y1 - 1 if below else b.rect.y1 <= cap.rect.y0 + 1)),
                key=lambda b: b.rect.y0 if below else -b.rect.y1,
            )
            edge, table = cap.rect, None
            for b in candidates:
                gap = b.rect.y0 - edge.y1 if below else edge.y0 - b.rect.y1
                section = SECTION.match(b.text) or b.size >= 1.12 * body or (NUMBERED.match(b.text) and b.bold >= 0.9)
                cell = mostly_numbers(b) or (b.words <= 8 and not b.text.endswith("."))
                if gap > 2 * body or section or not cell:
                    break
                edge = union(edge, b.rect)
                table = b.rect if table is None else union(table, b.rect)
            if table and sum(share_inside(b.rect, table) > 0.6 for b in text_blocks) >= 3:
                found.append(table)
                break
    return found


def find_pictures(page, blocks, body, gutter):
    """Group drawings, images, tables, equations and their labels into picture regions."""
    page_rect = page.rect
    page_area = page_rect.width * page_rect.height
    text_blocks = [b for b in blocks if b.kind != "gone"]
    page_words = sum(b.words for b in text_blocks)

    strong = []   # (rect, what): each can be a picture on its own
    weak = []     # (rect, gap): thin lines and labels: only join a picture that is already there
    for info in page.get_image_info():
        r = clamp(fitz.Rect(info["bbox"]), page_rect)
        if r.width < 15 or r.height < 15:
            continue
        if r.width * r.height > 0.6 * page_area and page_words > 100:
            continue   # a page background, not a figure
        strong.append((r, "image"))

    paths = page.get_drawings()
    rules = []
    for path in paths:
        r = clamp(fitz.Rect(path["rect"]), page_rect)
        if min(r.width, r.height) < 4 and max(r.width, r.height) > 4:
            weak.append((r, GAP))   # a rule line: table lines, footnote separator, underline
            if r.height < 4:
                rules.append(r)
    # Clustering skips flat lines (zero height), so rules are taken from the raw paths above
    for r in page.cluster_drawings(drawings=paths) if paths else []:
        r = clamp(fitz.Rect(r), page_rect)
        if r.width * r.height > 0.5 * page_area:
            continue   # page border or background box
        if min(r.width, r.height) >= 4:
            strong.append((r, "drawing"))

    if paths:
        try:
            for table in page.find_tables().tables:
                if table.row_count >= 2 and table.col_count >= 2:
                    strong.append((fitz.Rect(table.bbox), "table"))
        except Exception:
            pass   # table detection is a bonus; drawings still catch most tables
    captions = [b for b in text_blocks if b.kind == "caption"]
    # Tables found from their caption: drawn with horizontal rules only, or with no lines at all
    strong += [(r, "anchored") for r in ruled_tables(rules, captions) + text_tables(captions, text_blocks, body)]

    for b in text_blocks:
        if b.kind == "equation":
            strong.append((b.rect, "equation"))
        elif b.kind == "text" and mostly_numbers(b):
            strong.append((b.rect, "numbers"))   # a row of a table without lines
        elif (b.kind == "text" and (
                (b.size < 0.92 * body and b.words < 15)
                or (b.words <= 3 and b.bold < 0.5 and b.size <= 1.05 * body and not SECTION.match(b.text))
        )) or (b.kind == "footnote" and b.words <= 6):
            weak.append((b.rect, LABEL_GAP))   # figure labels, legends, table cells

    # Grow regions: merge touching strong pieces, then pull in nearby weak ones, until stable
    regions = [{"rect": fitz.Rect(r), "kinds": {k}} for r, k in strong]
    changed = True
    while changed:
        changed = False
        merged = []
        for reg in regions:
            for other in merged:
                if near(other["rect"], reg["rect"], GAP):
                    other["rect"] = union(other["rect"], reg["rect"])
                    other["kinds"] |= reg["kinds"]
                    changed = True
                    break
            else:
                merged.append(reg)
        regions = merged
        for item in weak[:]:
            r, gap = item
            for reg in regions:
                if near(reg["rect"], r, gap):
                    reg["rect"] = union(reg["rect"], r)
                    weak.remove(item)
                    changed = True
                    break

    # Equation numbers like "(3)" sit far to the right of their equation
    for reg in regions:
        if reg["kinds"] == {"equation"}:
            for b in text_blocks:
                if EQUATION_NUMBER.match(b.text) and b.rect.y0 < reg["rect"].y1 and b.rect.y1 > reg["rect"].y0:
                    reg["rect"] = union(reg["rect"], b.rect)

    # Parts of one figure with empty space between them (e.g. three diagrams side by side):
    # merge pictures in the same column when no text lies between them
    changed = True
    while changed:
        changed = False
        free_text = [b for b in text_blocks if b.kind != "equation"
                     and not any(share_inside(b.rect, reg["rect"]) >= 0.6 for reg in regions)]
        for a in regions:
            for b in regions:
                if a is b or column_of(a["rect"], gutter) != column_of(b["rect"], gutter):
                    continue
                both = union(a["rect"], b["rect"])
                if not any(share_inside(t.rect, both) > 0.3 for t in free_text):
                    a["rect"] = both
                    a["kinds"] |= b["kinds"]
                    regions.remove(b)
                    changed = True
                    break
            if changed:
                break

    pictures = []
    for reg in regions:
        rect = reg["rect"]
        kind = "equation" if reg["kinds"] == {"equation"} else "figure"
        if rect.width < 25 or rect.height < (6 if kind == "equation" else 12):
            continue   # too small to be worth a picture (a bullet, a logo next to a name...)
        inside = [b for b in text_blocks if b.kind != "caption" and share_inside(b.rect, rect) >= 0.6]
        prose = sum(b.words for b in inside
                    if b.words >= 6 and 0.9 * body <= b.size <= 1.12 * body and not mostly_numbers(b))
        if "anchored" not in reg["kinds"]:   # a caption says it is a table: always keep it
            limit = 150 if reg["kinds"] & {"image", "table", "numbers"} else 60
            if prose >= limit:
                continue   # a box drawn around normal text (e.g. a framed abstract): keep it as text
        for b in inside:
            b.kind = "gone"
        pictures.append(Picture(rect, kind))

    # Leave a small margin around each picture, but never cut into the text next to it
    for pic in pictures:
        clip = clamp(pic.rect + (-3, -3, 3, 3), page_rect)
        for b in text_blocks:
            if b.kind == "gone" or not near(b.rect, clip, 0):
                continue
            if b.rect.y0 >= pic.rect.y1 - 1:
                clip.y1 = min(clip.y1, b.rect.y0)
            elif b.rect.y1 <= pic.rect.y0 + 1:
                clip.y0 = max(clip.y0, b.rect.y1)
        pic.clip = clip
    return pictures


def render(page, picture, dpi):
    picture.png = page.get_pixmap(clip=picture.clip, dpi=dpi).tobytes("png")


# ----------------------------------------------------------------------------
# Step 4: put the blocks of a page in reading order (handles two columns)
# ----------------------------------------------------------------------------

def by_rows(items):
    """Sort top to bottom; items on the same row go left to right."""
    items = sorted(items, key=lambda i: i.rect.y0)
    rows, out = [], []
    for item in items:
        if rows and abs(item.rect.y0 - rows[-1][0].rect.y0) < 4:
            rows[-1].append(item)
        else:
            rows.append([item])
    for row in rows:
        out += sorted(row, key=lambda i: i.rect.x0)
    return out


def reading_order(items, gutter):
    if gutter is None:
        return by_rows(items)   # single column

    spanning = sorted((i for i in items if column_of(i.rect, gutter) == "both"), key=lambda i: i.rect.y0)
    columns = [i for i in items if column_of(i.rect, gutter) != "both"]

    # Full-width items (title, wide figures) cut the page into bands; read each band
    # left column first, then right column.
    out = []
    for k in range(len(spanning) + 1):
        band = [i for i in columns if sum(s.rect.y0 < i.rect.y0 for s in spanning) == k]
        out += sorted((i for i in band if column_of(i.rect, gutter) == "left"), key=lambda i: i.rect.y0)
        out += sorted((i for i in band if column_of(i.rect, gutter) == "right"), key=lambda i: i.rect.y0)
        if k < len(spanning):
            out.append(spanning[k])
    return out


# ----------------------------------------------------------------------------
# Step 5: decide the role of each block: title, heading, body, reference...
# ----------------------------------------------------------------------------

def is_heading(b, body):
    text = b.text
    words = len(text.split())
    if words > 18 or len(b.lines) > 3 or not re.search(r"[^\W\d_]", text) or text[0].islower():
        return False
    if text.endswith((",", ";")) or (text.endswith(".") and words > 4 and not SECTION.match(text)):
        return False
    return (
        b.size >= 1.12 * body
        or (b.bold >= 0.9 and b.size >= 0.9 * body)
        or (b.italic >= 0.9 and NUMBERED.match(text) is not None and words <= 12)   # "2.1. Data" in italics
        or (text.isupper() and words <= 8 and b.size >= 0.9 * body)
        or (SECTION.match(text) is not None and words <= 6)
    )


def heading_level(b, size_rank):
    text = b.text
    if REFERENCES.match(text) or (SECTION.match(text) and not NUMBERED.match(text)):
        return 1
    m = NUMBERED.match(text)
    if m:
        return min(m.group(1).count(".") + 1, 3)
    if ROMAN.match(text):
        return 1
    if LETTERED.match(text):
        # "A. Methods": an appendix section if it's as big as the main headings, else a subsection (IEEE)
        return 1 if len(size_rank) > 1 and size_rank.get(round(b.size * 2) / 2) == 1 else 2
    return min(size_rank.get(round(b.size * 2) / 2, 1), 3)


def classify(flow, body, first_page_height):
    """first_page_height is None when the conversion doesn't start at page 1."""
    blocks = [i for i in flow if isinstance(i, Block)]

    # Title: the biggest text in the top half of the first page
    if first_page_height:
        first = [b for b in blocks if b.page == 0 and b.kind == "text"]
        if first:
            biggest = max(b.size for b in first)
            if biggest >= 1.25 * body:
                for b in first:
                    if b.size == biggest and b.rect.y0 < 0.45 * first_page_height:
                        b.kind = "title"

    for b in blocks:
        if b.kind == "text" and is_heading(b, body):
            b.kind = "heading"
    sizes = sorted({round(b.size * 2) / 2 for b in blocks if b.kind == "heading"}, reverse=True)
    size_rank = {s: n + 1 for n, s in enumerate(sizes)}

    # Front matter: authors, affiliations, emails... everything on page one before
    # the abstract or the first real section
    front = bool(first_page_height)
    in_refs = False
    for b in blocks:
        if b.page != 0:
            front = False   # authors and affiliations only appear on the first page
        if b.kind == "heading":
            if front and not (SECTION.match(b.text) or NUMBERED.match(b.text) or ROMAN.match(b.text)):
                b.kind = "front"
                continue
            front = False
            b.level = heading_level(b, size_rank)
            in_refs = bool(REFERENCES.match(b.text))
        elif b.kind == "text":
            if front and b.words < 50:
                b.kind = "front"
            else:
                front = False
                b.kind = "ref" if in_refs else "body"


# ----------------------------------------------------------------------------
# Step 6: split blocks into paragraphs and join their lines into text
# ----------------------------------------------------------------------------

def append_runs(runs, new_runs):
    """Join two pieces of text the way a reader would: undo end-of-line hyphens, add a space."""
    new_runs = [Run(r.text, r.bold, r.italic, r.sup) for r in new_runs]
    if runs and new_runs:
        end = runs[-1].text.rstrip()
        start = plain(new_runs).lstrip()
        if end.endswith(SOFT_HYPHEN):
            runs[-1].text = end[:-1]   # a hyphenation point Word doesn't need: join the word halves
        elif end.endswith("-") and len(end) > 1 and end[-2].isalpha() and start[:1].islower():
            last_word = end.split()[-1] if end.split() else end
            next_word = start.split()[0] if start.split() else start
            # Keep the hyphen of compound words like "state-of-the-art" or "case-by-case"
            runs[-1].text = end if "-" in last_word[:-1] or "-" in next_word else end[:-1]
        elif end.endswith(("-", "/")):
            runs[-1].text = end   # broken URL or compound: no space
        else:
            runs[-1].text = end + " "
        new_runs[0].text = new_runs[0].text.lstrip()
    runs.extend(new_runs)
    return runs


def fix_accents(text):
    def compose(m):
        if m.group(3):
            return m.group(3) + ACCENTS["¸"]
        letter = "i" if m.group(2) == "ı" else m.group(2)
        return letter + ACCENTS[m.group(1)]
    return unicodedata.normalize("NFC", LOOSE_ACCENT.sub(compose, text))


def tidy(runs):
    """Merge runs that share a format and clean up spaces."""
    out = []
    for r in runs:
        text = re.sub(r" {2,}", " ", r.text)
        if out and out[-1].text.endswith(" "):
            text = text.lstrip()
        if not text:
            continue
        if out and (not text.strip() or (out[-1].bold, out[-1].italic, out[-1].sup) == (r.bold, r.italic, r.sup)):
            out[-1].text += text
        else:
            out.append(Run(text, r.bold, r.italic, r.sup))
    for r in out:
        r.text = fix_accents(r.text).replace(SOFT_HYPHEN, "")
    if out:
        out[0].text = out[0].text.lstrip()
        out[-1].text = out[-1].text.rstrip()
    return [r for r in out if r.text]


def join_lines(lines):
    runs = []
    for line in lines:
        append_runs(runs, line.runs)
    return tidy(runs)


def split_paragraphs(block):
    """One PyMuPDF block can hold a whole column; cut it where paragraphs really start."""
    lines = block.lines
    if len(lines) < 2:
        return [lines]
    left = min(l.rect.x0 for l in lines)
    right = max(l.rect.x1 for l in lines)
    width = right - left
    pitch = statistics.median(b.rect.y0 - a.rect.y0 for a, b in zip(lines, lines[1:]))
    paragraphs, current = [], [lines[0]]
    for prev, line in zip(lines, lines[1:]):
        new = (
            (line.rect.x0 > left + 6 and prev.rect.x0 <= left + 3 and width > 100)        # indented first line
            or (prev.rect.x1 < right - 0.2 * width and prev.text.endswith((".", "!", "?", ":")))  # short last line
            or (pitch > 0 and line.rect.y0 - prev.rect.y0 > 1.6 * pitch                 # extra space (but a tall
                and prev.text.endswith((".", "!", "?", ":")))                           # inline fraction isn't one)
            or BULLET.match(line.text)
        )
        if new:
            paragraphs.append(current)
            current = []
        current.append(line)
    paragraphs.append(current)
    return paragraphs


def split_references(block):
    """Cut a block of references into one entry each."""
    lines = block.lines
    if any(REF_BRACKET.match(l.text) for l in lines):
        starts = [i for i, l in enumerate(lines) if REF_BRACKET.match(l.text)]
    elif any(REF_START.match(l.text) for l in lines):
        starts = [i for i, l in enumerate(lines) if REF_START.match(l.text)]
    else:
        left = min(l.rect.x0 for l in lines)
        flush = [i for i, l in enumerate(lines) if l.rect.x0 <= left + 3]
        if len(flush) == len(lines):
            return split_paragraphs(block)
        starts = flush   # hanging indent: each entry starts at the left edge
    if not starts or starts[0] != 0:
        starts = [0] + starts
    return [lines[a:b] for a, b in zip(starts, starts[1:] + [len(lines)])]


def split_footnotes(block):
    """Several footnotes can share one block: start a new one at each marker (¹, ∗, †, ‡...)."""
    parts = []
    for line in block.lines:
        first = next((r for r in line.runs if r.text.strip()), None)
        if parts and not (first.sup or re.match(r"^[∗*†‡§¶]", line.text)):
            parts[-1].append(line)
        else:
            parts.append([line])
    return parts


def build_elements(flow):
    elements = []
    for item in flow:
        if isinstance(item, Picture):
            elements.append(Element("picture", picture=item))
        elif item.kind == "body":
            paragraphs = [Element("body", join_lines(p)) for p in split_paragraphs(item)]
            paragraphs[-1].col_end = item.col_end
            elements += paragraphs
        elif item.kind == "ref":
            elements += [Element("ref", join_lines(p)) for p in split_references(item)]
        elif item.kind == "footnote":
            elements += [Element("footnote", join_lines(p)) for p in split_footnotes(item)]
        elif item.kind == "front":
            elements.append(Element("front", lines=[tidy(l.runs) for l in item.lines]))
        elif item.kind in ("title", "heading", "caption"):
            elements.append(Element(item.kind, join_lines(item.lines), level=item.level))
        elif item.kind in ("text", "equation"):   # leftovers, e.g. an equation we couldn't picture
            elements.append(Element("body", join_lines(item.lines)))
    return elements


def stitch(elements):
    """Rejoin paragraphs that were cut by a column or page break (or a figure placed in between)."""
    refs = [plain(e.runs) for e in elements if e.kind == "ref"]
    numbered_refs = refs and sum(bool(REF_START.match(t)) for t in refs) >= 0.5 * len(refs)

    out = []
    refs_over = False
    for el in elements:
        if el.kind == "ref" and numbered_refs and not REF_START.match(plain(el.runs)):
            # Long unnumbered text after the references: author biographies, an appendix...
            refs_over = refs_over or len(plain(el.runs)) > 300
            if refs_over:
                el.kind = "body"
        if el.kind in ("body", "ref") and el.runs:
            j = len(out) - 1
            while j >= 0 and (out[j].kind in ("footnote", "caption")
                              or (out[j].kind == "picture" and out[j].picture.kind == "figure")):
                j -= 1
            if j >= 0 and out[j].kind == el.kind and out[j].runs:
                end = plain(out[j].runs).rstrip()
                start = plain(el.runs).lstrip()
                if el.kind == "body":
                    unfinished = not re.search(r"[.!?:]['\"”’)\]]?$", end)
                    # A long paragraph stopping mid-sentence continues in the next one, even when
                    # that starts with a capital or a digit ("...error on the" + "ImageNet test set")
                    joins = unfinished and (
                        start[:1].islower() or end.endswith((",", "-", "–"))
                        or ((out[j].col_end or len(end.split()) >= 20 or CONNECTOR.search(end))
                            and (start[:1].isalnum() or start[:1] in "([“\"'"))
                    )
                else:
                    joins = (not REF_START.match(start)) if numbered_refs else start[:1].islower()
                if joins:
                    out[j].runs = tidy(append_runs(out[j].runs, el.runs))
                    out[j].col_end = el.col_end
                    continue
        out.append(el)
    return out


# ----------------------------------------------------------------------------
# Step 7: write the Word document
# ----------------------------------------------------------------------------

def add_runs(paragraph, runs, styled=False):
    for r in runs:
        run = paragraph.add_run(r.text)
        if r.bold and not styled:   # headings and titles are already bold by style
            run.bold = True
        if r.italic:
            run.italic = True
        if r.sup:
            run.font.superscript = True


def write_docx(elements, output, title, author, source):
    doc = Document()
    page = doc.sections[0]   # A4 with 2.5 cm margins
    page.page_width, page.page_height = Cm(21), Cm(29.7)
    page.left_margin = page.right_margin = page.top_margin = page.bottom_margin = Cm(2.5)
    max_width = page.page_width - page.left_margin - page.right_margin

    styles = doc.styles
    styles["Normal"].font.size = Pt(11)
    styles["Normal"].paragraph_format.space_after = Pt(6)

    ref_style = styles.add_style("Article Reference", WD_STYLE_TYPE.PARAGRAPH)
    ref_style.base_style = styles["Normal"]
    ref_style.font.size = Pt(9.5)
    ref_style.paragraph_format.left_indent = Inches(0.3)
    ref_style.paragraph_format.first_line_indent = Inches(-0.3)
    ref_style.paragraph_format.space_after = Pt(3)

    note_style = styles.add_style("Article Footnote", WD_STYLE_TYPE.PARAGRAPH)
    note_style.base_style = styles["Normal"]
    note_style.font.size = Pt(8.5)
    note_style.font.color.rgb = RGBColor(0x59, 0x59, 0x59)

    for el in elements:
        if el.kind == "picture":
            # Same size as in the PDF, shrunk only if wider than the page
            width = min(Inches(el.picture.rect.width / 72), max_width)
            doc.add_picture(io.BytesIO(el.picture.png), width=width)
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif el.kind == "title":
            add_runs(doc.add_paragraph(style="Title"), el.runs, styled=True)
        elif el.kind == "heading":
            add_runs(doc.add_paragraph(style=f"Heading {el.level}"), el.runs, styled=True)
        elif el.kind == "front":
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for n, line in enumerate(el.lines):
                if n:
                    p.add_run().add_break()
                add_runs(p, line)
        elif el.kind == "caption":
            add_runs(doc.add_paragraph(style="Caption"), el.runs)
        elif el.kind == "footnote":
            add_runs(doc.add_paragraph(style="Article Footnote"), el.runs)
        elif el.kind == "ref":
            add_runs(doc.add_paragraph(style="Article Reference"), el.runs)
        else:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            add_runs(p, el.runs)

    doc.core_properties.title = title
    doc.core_properties.author = author
    doc.core_properties.comments = f"Converted from {source.name} with article_to_word.py"
    doc.save(output)


# ----------------------------------------------------------------------------
# The whole conversion
# ----------------------------------------------------------------------------

def convert(pdf_path, docx_path, pages_spec, figures, dpi):
    print(f"Converting {pdf_path} ...")
    pdf = fitz.open(pdf_path)
    try:
        pages = parse_pages(pages_spec, pdf.page_count) if pages_spec else list(range(pdf.page_count))
    except ValueError:
        print("Pages must look like 1-5 or 1,4,9 (page numbers start at 1).")
        sys.exit(1)

    # Read every page first: the body font size and repeated headers need the whole article
    pages_blocks = {n: read_blocks(pdf[n], n) for n in pages}
    remove_headers_footers(pages_blocks, {n: pdf[n].rect.height for n in pages})
    sizes = Counter()
    for blocks in pages_blocks.values():
        for b in blocks:
            if b.kind != "gone":
                for line in b.lines:
                    for r in line.runs:
                        sizes[round(r.size * 2) / 2] += len(r.text.strip())
    sizes.pop(0, None)
    body = sizes.most_common(1)[0][0] if sizes else 10

    flow, scanned = [], []
    for n in pages:
        page = pdf[n]
        blocks = pages_blocks[n]
        for b in blocks:
            if b.kind == "text":
                tag_block(b, body, page.rect.height)
        join_caption_labels(blocks, body)
        gutter = find_gutter(blocks, page.rect.width, body)
        tag_numbered_equations(blocks, gutter)
        pictures = find_pictures(page, blocks, body, gutter)
        for pic in pictures:
            pic.page = n
        # Small print at the very bottom of page one (DOI, "Received ...", copyright): footnotes
        for b in blocks:
            if (n == 0 and b.kind == "text" and b.rect.y0 > 0.85 * page.rect.height
                    and b.size < 0.95 * body and b.bold < 0.5):
                b.kind = "footnote"

        # The lowest text of each column: a sentence cut there continues in the next column
        lowest = {}
        for b in blocks:
            if b.kind == "text":
                col = column_of(b.rect, gutter)
                if col not in lowest or b.rect.y1 > lowest[col].rect.y1:
                    lowest[col] = b
        for b in lowest.values():
            b.col_end = True
        if not any(b.kind != "gone" for b in blocks):
            scanned.append(n + 1)
        if figures:
            for pic in pictures:
                render(page, pic, dpi)
        else:
            pictures = []

        items = [b for b in blocks if b.kind not in ("gone", "footnote")] + pictures
        footnotes = [b for b in blocks if b.kind == "footnote"]
        flow += reading_order(items, gutter) + by_rows(footnotes)

    classify(flow, body, pdf[0].rect.height if 0 in pages else None)
    # Journal logos and banners printed above the title are not part of the article
    title_blocks = [i for i in flow if isinstance(i, Block) and i.kind == "title"]
    if title_blocks:
        title_bottom = title_blocks[0].rect.y1
        flow = [i for i in flow if not (isinstance(i, Picture) and i.page == 0 and i.rect.y0 < title_bottom)]
    elements = stitch(build_elements(flow))

    # Put the title first, even if a copyright line was printed above it
    titles = [e for e in elements if e.kind == "title"]
    if len(titles) > 1:   # a title printed as several blocks
        runs = []
        for t in titles:
            append_runs(runs, t.runs)
        titles[0].runs = tidy(runs)
    elements = titles[:1] + [e for e in elements if e.kind != "title"]
    title = plain(titles[0].runs) if titles else (pdf.metadata or {}).get("title", "")
    author = (pdf.metadata or {}).get("author", "")
    pdf.close()

    write_docx(elements, docx_path, title, author, pdf_path)

    count = Counter(e.kind if e.kind != "picture" else e.picture.kind for e in elements)
    print(f"  -> {docx_path}")
    print(f"     {len(pages)} pages | {count['heading']} headings | {count['body']} paragraphs | "
          f"{count['figure']} figures/tables | {count['equation']} equations | {count['ref']} references")
    if scanned:
        print(f"     Note: page(s) {', '.join(map(str, scanned))} have no text (scanned?) - they were kept as images; run OCR on them first.")


parser = argparse.ArgumentParser(description="Convert a research article (PDF) into a clean, editable Word document.")
parser.add_argument("input", help="PDF file, or a folder of PDFs to convert in bulk")
parser.add_argument("output", nargs="?", help="output .docx path (default: same name as input)")
parser.add_argument("--pages", help="pages to convert, e.g. 1-5 or 1,4,9 (default: all pages)")
parser.add_argument("--no-figures", action="store_true", help="leave out figures, tables and equations (text only)")
parser.add_argument("--dpi", type=int, default=200, help="sharpness of figure images (default: %(default)s)")
args = parser.parse_args()

source = Path(args.input)
if not source.exists():
    print(f"File not found: {source}")
    sys.exit(1)

if source.is_dir():
    pdfs = sorted(source.glob("*.pdf"))
    if not pdfs:
        print(f"No PDF files found in {source}")
        sys.exit(1)
    if args.output:
        print("Note: output name is ignored when converting a folder.\n")
    for pdf in pdfs:
        convert(pdf, pdf.with_suffix(".docx"), args.pages, not args.no_figures, args.dpi)
    print(f"\nDone! Converted {len(pdfs)} file(s) in {source}")
else:
    output = Path(args.output) if args.output else source.with_suffix(".docx")
    convert(source, output, args.pages, not args.no_figures, args.dpi)
    print("\nDone! Open it in Word and use View > Navigation Pane to jump between sections.")
