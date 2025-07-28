import os
import json
import re
from pathlib import Path
from typing import List, Dict

import PyPDF2
import fitz  # PyMuPDF
import pdfplumber

# ---------------------- Helper: Date Filter ---------------------- #

def looks_like_date(text: str) -> bool:
    """Detects if a line looks like a date using regex."""
    text = text.strip()

    date_patterns = [
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[\s,]*(\d{4}|\d{1,2})\b",  # e.g., March 2005, Aug 17
        r"\b\d{1,2}[\s/-](jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[\s/-]*\d{2,4}\b",  # e.g., 15 July 2023
        r"\b(19|20)\d{2}\b"  # Year only between 1900 and 2099
    ]

    return any(re.search(pat, text, re.IGNORECASE) for pat in date_patterns)


# ---------------------- Title Extraction ---------------------- #

def extract_title_from_pdf(pdf_path: Path) -> str:
    try:
        with open(pdf_path, 'rb') as f:
            metadata = PyPDF2.PdfReader(f).metadata
            if metadata and metadata.title:
                title = metadata.title.strip()
                if title and len(title) > 3:
                    return title

        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0] if pdf.pages else None
            if first_page:
                text = first_page.extract_text()
                if text:
                    lines = text.split('\n')
                    for line in lines[:10]:
                        if is_valid_title_candidate(line):
                            return line.strip()

                title = extract_title_by_font_analysis(first_page)
                if title:
                    return title

        doc = fitz.open(pdf_path)
        first_page = doc[0] if len(doc) > 0 else None
        if first_page:
            for line in first_page.get_text().split('\n'):
                if is_valid_title_candidate(line):
                    return line.strip()
        doc.close()

    except Exception as e:
        print(f"Error extracting title from {pdf_path.name}: {e}")

    return ""

def is_valid_title_candidate(line: str) -> bool:
    line = line.strip()
    if not (5 < len(line) < 150):
        return False
    skip = ['page', 'date', 'www.', 'http', '@', 'copyright', 'vol.', 'no.', 'issue']
    if any(token in line.lower() for token in skip):
        return False
    if looks_like_date(line):
        return False
    return line[0].isupper() and not line.endswith('.') and not line.isdigit()

def extract_title_by_font_analysis(page) -> str:
    try:
        font_sizes = {}
        for char in page.chars:
            size = char.get('size', 0)
            if size > 10:
                font_sizes.setdefault(size, []).append(char)

        if font_sizes:
            max_size = max(font_sizes)
            chars = font_sizes[max_size]
            text = ''.join(char.get('text', '') for char in chars).strip()
            return text if is_valid_title_candidate(text) else ""

    except Exception as e:
        print(f"Error in font analysis: {e}")
    return ""

# ---------------------- Outline Extraction ---------------------- #

def extract_outline_from_pdf(pdf_path: Path) -> List[Dict]:
    try:
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()

        if toc:
            outline = [
                {
                    "level": f"H{min(level, 6)}",
                    "text": title.strip(),
                    "page": max(0, page - 1)
                }
                for level, title, page in toc if title.strip()
            ]
        else:
            outline = extract_headings_from_text(doc)

        doc.close()
        return outline

    except Exception as e:
        print(f"Error extracting outline from {pdf_path.name}: {e}")
        return []

def extract_headings_from_text(doc) -> List[Dict]:
    headings = []
    seen = set()
    font_sizes = []

    try:
        # First pass: gather all font sizes
        for page_num in range(len(doc)):
            blocks = doc[page_num].get_text("dict").get("blocks", [])
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        size = span.get("size", 0)
                        if size > 6:
                            font_sizes.append(size)

        if not font_sizes:
            return []

        min_size = min(font_sizes)
        max_size = max(font_sizes)
        size_range = max_size - min_size if max_size != min_size else 1.0

        # Second pass: heading classification
        for page_num in range(len(doc)):
            blocks = doc[page_num].get_text("dict").get("blocks", [])
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text or text in seen:
                            continue

                        font_size = span.get("size", 0)
                        if font_size <= 6:
                            continue

                        font_flags = span.get("flags", 0)
                        is_bold = bool(font_flags & 2**4)

                        norm_size = (font_size - min_size) / size_range

                        if (
                            3 < len(text) < 100 and
                            not text.endswith('.') and
                            not text.isdigit() and
                            text[0].isupper() and
                            not looks_like_date(text) and
                            (norm_size > 0.5 or is_bold)
                        ):
                            if norm_size >= 0.8:
                                level = "H1"
                            elif norm_size >= 0.6:
                                level = "H2"
                            else:
                                level = "H3"

                            seen.add(text)
                            headings.append({
                                "level": level,
                                "text": text,
                                "page": page_num
                            })

    except Exception as e:
        print(f"Error during heading detection: {e}")

    return headings

# ---------------------- Main Processor ---------------------- #

def process_pdfs():
    input_dir = Path("/app/input")
    output_dir = Path("/app/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        print("No PDF files found in input directory.")
        return

    for pdf_file in pdf_files:
        print(f"Processing: {pdf_file.name}")

        try:
            title = extract_title_from_pdf(pdf_file)
            outline = extract_outline_from_pdf(pdf_file)

            output_data = {
                "title": title,
                "outline": outline
            }

            output_file = output_dir / f"{pdf_file.stem}.json"
            with open(output_file, "w", encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            print(f"Done: {output_file.name} | Title: \"{title}\" | Headings: {len(outline)}")

        except Exception as e:
            print(f"Failed to process {pdf_file.name}: {e}")

# ---------------------- Entry Point ---------------------- #

if __name__ == "__main__":
    print("Starting PDF outline extraction")
    process_pdfs()
    print("Finished processing all PDFs")
