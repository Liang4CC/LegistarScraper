import fitz  # PyMuPDF - pip install PyMuPDF
             # Check that it works: python -c "import fitz; print(fitz.__doc__)"
import re
from pathlib import Path
import os

SOURCE_DIR = Path("INPUT")
OUTPUT_DIR = Path("OUTPUT_SPLIT_REPORTS")
SOURCE_PDF = SOURCE_DIR / "Supplemental Reports (Updated 07-15-2025).pdf"
SUMMARY_MD = OUTPUT_DIR / "split_summary_index.md"

OUTPUT_DIR.mkdir(exist_ok=True)

# Patterns to detect headers and subject
break_pattern = re.compile(
    r"CITY COUNCIL STAFF REPORT\s+(DESK ITEM|SUPPLEMENTAL 1)?\s*Meeting: (\w+ \d{1,2}, \d{4})\s+Agenda Item #(\d+)",
    re.MULTILINE,
)
subject_pattern = re.compile(r"Subject\s*(.*?)\s*(?=\n|\r|$)", re.DOTALL)

def sanitize_filename(text):
    return "".join(c if c.isalnum() or c in " ._-#" else "_" for c in text)

def get_subject(text_block):
    match = subject_pattern.search(text_block)
    if match:
        subject_line = match.group(1).strip()
        return " ".join(subject_line.split()[:6])
    return "NoSubject"

def extract_agenda_number(filename):
    match = re.search(r'Agenda Item #(\d+)', filename.stem)
    return int(match.group(1)) if match else 9999

def split_pdf_and_generate_summary(pdf_path):
    all_docs = fitz.open(pdf_path)
    current_doc = []
    metadata_list = []
    doc_header = {}

    for idx, page in enumerate(all_docs):
        text = page.get_text()
        print(f">>>> Page {idx}: {text}")
        match = break_pattern.search(text)
        if match:
            print(f"    >>>> match.groups() = {match.groups()}")
            if doc_header:
                # Save the last doc in metadata_list
                print(f"       - append metadata (current_doc, doc_header) = (current_doc, {doc_header})")
                metadata_list.append((current_doc, doc_header))
            # Start a new doc
            current_doc = []
            # match.groups() = ('DESK ITEM', 'July 15, 2025', '9')
            item_type, meeting_date, agenda_num = match.groups()
            subject = get_subject(text)
            doc_header = {
                "type": item_type.strip() if item_type else "Standard",
                "date": meeting_date.strip(),
                "agenda": f"Agenda Item #{agenda_num}",
                "subject": subject,
            }
            print(f"        => doc_header = {doc_header}")
        # Add one more page to the current doc
        current_doc.append(page)

    if current_doc:
        # Save the last doc in metadata_list
        print(f"       - append metadata (current_doc, doc_header) = (current_doc, {doc_header})")
        metadata_list.append((current_doc, doc_header))

    saved_files = []

    for idx, (pages, meta) in enumerate(metadata_list, 1):
        print(f"pages = {pages}")
        print(f"meta = {meta}")
        date_fmt = meta["date"].replace(",", "")
        filename = f"{meta['agenda']} {meta['type']} {meta['subject']} {date_fmt}".strip()
        filename = sanitize_filename(filename) + ".pdf"
        out_path = OUTPUT_DIR / filename

        new_doc = fitz.open()
        for p in pages:
            new_doc.insert_pdf(p.parent, from_page=p.number, to_page=p.number)
        new_doc.save(out_path)
        saved_files.append(out_path)

        print(f"✅ Saved: {out_path.name}")

    return saved_files

def write_markdown_summary(pdf_paths, md_path):
    sorted_paths = sorted(pdf_paths, key=extract_agenda_number)
    lines = ["# Supplemental Report Index (Sorted by Agenda Item)", ""]
    for path in sorted_paths:
        lines.append(f"- [{path.stem}](split_reports/{path.name})")
    md_path.write_text("\n".join(lines), encoding="utf-8")

# Run both steps
pdfs = split_pdf_and_generate_summary(SOURCE_PDF)
write_markdown_summary(pdfs, SUMMARY_MD)

