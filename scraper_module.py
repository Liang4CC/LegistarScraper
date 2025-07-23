import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
from pathlib import Path
import mimetypes
import logging
import fitz  # PyMuPDF

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class ScraperInterface:
    """Interface class for the Cupertino meeting scraper"""
    
    def __init__(self):
        self.BASE_URL = "https://cupertino.legistar.com/"
        self.CALENDAR_URL = "https://cupertino.legistar.com/calendar.aspx"
        self.CITY_COUNCIL_PAGE = (
            "https://cupertino.legistar.com/DepartmentDetail.aspx?"
            "ID=22534&GUID=759DE527-B7CF-4B4C-88AB-B83875AB732D&Mode=MainBody"
        )

    def sanitize_filename(self, name):
        """Sanitize filename for safe filesystem storage"""
        # Remove invalid characters and limit length
        sanitized = re.sub(r'[\\/*?:"<>|]', "_", name.strip())
        # Limit to 100 characters to prevent filesystem issues
        if len(sanitized) > 100:
            sanitized = sanitized[:100].rstrip('_')
        return sanitized

    def fetch_soup(self, url):
        """Fetch and parse HTML from URL"""
        logging.debug(f"Fetching: {url}")
        resp = requests.get(url)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")

    def fetch_meetings_for_date(self, target_date):
        """Return list of tuples: (date string, time string, full meeting URL)"""
        soup = self.fetch_soup(self.CITY_COUNCIL_PAGE)
        matches = []
        
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 5:
                date = cells[0].get_text(strip=True)
                if target_date != date:
                    continue
                time = cells[2].get_text(strip=True)
                link_tag = cells[4].find("a", href=True)
                if link_tag and "MeetingDetail.aspx" in link_tag["href"]:
                    detail_url = urljoin(self.BASE_URL, link_tag["href"])
                    matches.append((date, time, detail_url))
        
        return matches

    def fetch_meetings_for_date_range(self, start_date, end_date):
        """Return list of tuples for meetings in date range: (date string, time string, full meeting URL)"""
        from datetime import datetime
        
        # Parse dates
        try:
            start_dt = datetime.strptime(start_date, '%m/%d/%Y')
            end_dt = datetime.strptime(end_date, '%m/%d/%Y')
        except ValueError as e:
            raise ValueError(f"Invalid date format. Use MM/DD/YYYY: {e}")
        
        if start_dt > end_dt:
            raise ValueError("Start date must be before or equal to end date")
        
        soup = self.fetch_soup(self.CITY_COUNCIL_PAGE)
        matches = []
        
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 5:
                date_str = cells[0].get_text(strip=True)
                if not date_str:
                    continue
                    
                try:
                    # Parse the meeting date
                    meeting_dt = datetime.strptime(date_str, '%m/%d/%Y')
                    
                    # Check if meeting date is within range
                    if start_dt <= meeting_dt <= end_dt:
                        time = cells[2].get_text(strip=True)
                        link_tag = cells[4].find("a", href=True)
                        if link_tag and "MeetingDetail.aspx" in link_tag["href"]:
                            detail_url = urljoin(self.BASE_URL, link_tag["href"])
                            matches.append((date_str, time, detail_url))
                except ValueError:
                    # Skip rows with invalid date formats
                    continue
        
        # Sort by date
        matches.sort(key=lambda x: datetime.strptime(x[0], '%m/%d/%Y'))
        return matches

    def infer_filename_with_extension(self, href, default_name, response):
        """Infer proper filename with extension"""
        # Check Content-Disposition header
        cd = response.headers.get("Content-Disposition", "")
        if "filename=" in cd:
            filename = cd.split("filename=")[-1].strip().strip('"')
            return self.sanitize_filename(filename)

        # Check extension in URL path
        parsed_path = Path(urlparse(href).path)
        if parsed_path.suffix:
            return self.sanitize_filename(parsed_path.name)

        # Infer from Content-Type
        content_type = response.headers.get("Content-Type", "")
        extension = mimetypes.guess_extension(content_type.split(";")[0].strip())

        return self.sanitize_filename(default_name) + (extension if extension else ".bin")

    def download_file_to_folder(self, href, default_name, folder_path, skip_download=False):
        """Download file to specified folder"""
        try:
            response = requests.get(href)
            response.raise_for_status()
            filename = self.infer_filename_with_extension(href, default_name, response)
            full_path = folder_path / filename
            
            if full_path.exists():
                logging.debug(f"Skipping existing file: {filename}")
                return filename
            else:
                logging.debug(f"Downloading file: {filename}")
                if not skip_download:
                    full_path.write_bytes(response.content)
                return filename
        except Exception as e:
            logging.error(f"Failed to download file from {href}: {e}")
            return None

    def extract_meeting_extras(self, soup):
        """Extract meeting extras like agenda and minutes"""
        extras = []
        EXTRA_LABELS = [
            "Published agenda",
            "Published minutes",
            "Meeting Extra1",
            "Meeting Extra2",
            "Meeting Extra3"
        ]
        
        all_tds = soup.find_all("td")
        i = 2  # skip entry 0 and 1
        
        while i < len(all_tds) - 1:
            label_td = all_tds[i]
            link_td = all_tds[i + 1]
            label = label_td.get_text(strip=True).rstrip(":")
            
            if label == "":
                i += 1
                continue
                
            if label in EXTRA_LABELS:
                for a in link_td.find_all("a"):
                    link_text = a.text.strip()
                    href = urljoin(self.BASE_URL, a.get("href", "")) if a.get("href") else ""
                    extras.append((label, link_text, href))
                    logging.debug(f"Extra: {label} — {link_text}")
            i += 2
            
        return extras

    def download_meeting_extras(self, dest, extras, skip_download=False):
        """Download meeting extra documents"""
        downloaded_files = []
        for i, (label, text, href) in enumerate(extras, 1):
            if href == "":
                logging.debug(f"Skipping extra: {text} (No Link)")
                continue
            default_filename = f"Extra{i:02d} - {text}"
            filename = self.download_file_to_folder(href, default_filename, dest, skip_download)
            if filename:
                downloaded_files.append(filename)
        return downloaded_files

    def parse_meeting_header(self, soup, meeting_url):
        """Parse meeting header information"""
        title = soup.find("title").text.strip()
        
        date_span = soup.find("span", id="ctl00_ContentPlaceHolder1_lblDate")
        meeting_date = date_span.text.strip() if date_span else "Not Found"
        
        time_span = soup.find("span", id="ctl00_ContentPlaceHolder1_lblTime")
        meeting_time = time_span.text.strip() if time_span else "Not Found"
        
        meeting_dt = f"{meeting_date} {meeting_time}"
        logging.debug(f"Meeting date/time: {meeting_dt}")

        # Extract extras
        extras = self.extract_meeting_extras(soup)

        # Extract agenda items
        items = []
        table = soup.find("table", id=re.compile(r"gridMain", re.IGNORECASE))
        if table:
            for i, row in enumerate(table.find_all("tr")[1:], 1):
                cols = row.find_all("td")
                if len(cols) >= 6:
                    subj = cols[5].get_text("\n", strip=True)
                    subj = subj.split("Subject:", 1)[-1].strip()
                    href = cols[0].find("a", href=True)
                    if href:
                        url = urljoin(self.BASE_URL, href['href'])
                        items.append((i, subj, url))
                        logging.debug(f"Item{i}: {subj}")

        return title, meeting_dt, extras, items

    def write_meeting_header(self, output_folder, title, meeting_dt, extras, items):
        """Write meeting header markdown file"""
        lines = [
            f"# {title}",
            "",
            f"**Meeting date/time:** {meeting_dt}",
            "",
        ]
        
        if extras:
            lines.append("")
            lines.append("## Additional Documents")
            lines.append("")
            for label, text, href in extras:
                lines.append(f"- {label}: [{text}]({href})")
            lines.append("")
            
        for i, subj, url in items:
            lines.append(f"{i}. [{subj}]({url})")
            
        path = output_folder / "AgendaHeader.md"
        path.write_text("\n".join(lines), encoding="utf-8")

    def process_agenda_item(self, index, subj, url, base_folder, selection=None, skip_download=False):
        """Process individual agenda item"""
        soup = self.fetch_soup(url)

        # Get item date/time
        dt_span = soup.find("span", id=re.compile(r"lblOnAgenda2", re.IGNORECASE))
        item_dt = dt_span.text.strip() if dt_span else "Not Found"
        
        meta = soup.find("meta", {"name": "description"})
        desc = meta["content"].strip() if meta else ""

        # Create folder name
        words = re.findall(r"\b\w+\b", subj)
        short = " ".join(words[:6])
        folder_name = f"Item{index} - {self.sanitize_filename(short)}"
        folder = base_folder / folder_name
        folder.mkdir(parents=True, exist_ok=True)

        # Write item header
        lines = [
            f"# Item {index}: {subj}",
            f"**On agenda:** {item_dt}",
            "",
            desc,
            "",
            "## Attachments",
            ""
        ]
        
        attachments = []
        downloaded_files = []
        
        for a in soup.select("a[href*='View.ashx?M=F']"):
            link = urljoin(self.BASE_URL, a['href'])
            text = a.text.strip() or f"Attachment{len(attachments)+1}"
            attachments.append((text, link))
            lines.append(f"- [{text}]({link})")
            logging.debug(f"Attachment: {text}")

        # Write agenda header
        (folder / "AgendaHeader.md").write_text("\n".join(lines), encoding="utf-8")

        # Download attachments
        for idx, (text, href) in enumerate(attachments, 1):
            default_filename = f"Attachment{idx:02d} - {text}"
            filename = self.download_file_to_folder(href, default_filename, folder, skip_download)
            if filename:
                downloaded_files.append(filename)

        logging.debug(f"Finished processing Item {index}: downloaded {len(downloaded_files)} attachments")
        return downloaded_files

    def parse_item_numbers(self, selection):
        """Parse item number selection"""
        if not selection:
            return None
            
        selected = set()
        for token in selection:
            if "-" in token:
                start, end = token.split("-")
                selected.update(range(int(start), int(end) + 1))
            else:
                selected.add(int(token))
        return selected

    def process_meeting(self, meeting_url, dest, params):
        """Process a complete meeting"""
        import shutil
        
        dest = Path(dest)
        
        # Remove existing folder if requested
        if params.get('remove_output') and dest.exists():
            logging.debug(f"Removing existing folder: {dest}")
            shutil.rmtree(dest)
            
        dest.mkdir(parents=True, exist_ok=True)
        logging.debug(f"Output folder: {dest}")
        
        # Fetch meeting page
        soup = self.fetch_soup(meeting_url)
        
        # Parse meeting information
        title, meeting_dt, extras, items = self.parse_meeting_header(soup, meeting_url)
        
        # Write meeting header
        self.write_meeting_header(dest, title, meeting_dt, extras, items)
        
        # Download meeting extras
        skip_download = params.get('skip_download', False)
        extra_files = self.download_meeting_extras(dest, extras, skip_download)
        
        # Process agenda items
        selected_items = self.parse_item_numbers(params.get('selection'))
        processed_items = []
        
        for idx, subj, url in items:
            if selected_items is None or idx in selected_items:
                logging.debug(f"Processing Item{idx}: {subj}")
                item_files = self.process_agenda_item(idx, subj, url, dest, selected_items, skip_download)
                processed_items.append({
                    'index': idx,
                    'subject': subj,
                    'files': item_files
                })
            else:
                logging.debug(f"Skipping Item {idx}: {subj}")
        
        result = {
            'title': title,
            'meeting_dt': meeting_dt,
            'output_folder': str(dest),
            'extras_count': len(extras),
            'items_count': len(items),
            'processed_items': processed_items,
            'extra_files': extra_files
        }
        
        # Process supplemental reports if enabled and found
        if params.get('split_supplemental', True):  # Default True for backward compatibility
            self.process_supplemental_reports(dest, processed_items)
        
        logging.debug("Meeting processing completed")
        return result

    def find_supplemental_reports(self, meeting_folder):
        """Find supplemental report PDFs in the meeting folder"""
        patterns = ['*supplemental*', '*Supplemental*', '*SUPPLEMENTAL*']
        supplemental_files = []
        
        for pattern in patterns:
            supplemental_files.extend(meeting_folder.glob(f"**/{pattern}.pdf"))
        
        return supplemental_files

    def split_supplemental_pdf(self, pdf_path, agenda_items):
        """Split supplemental PDF into separate files for each agenda item"""
        logging.debug(f"Processing supplemental PDF: {pdf_path}")
        
        # Patterns to detect headers and subject
        break_pattern = re.compile(
            r"CITY COUNCIL STAFF REPORT\s+(DESK ITEM|SUPPLEMENTAL 1)?\s*Meeting: (\w+ \d{1,2}, \d{4})\s+Agenda Item #(\d+)",
            re.MULTILINE,
        )
        subject_pattern = re.compile(r"Subject\s*(.*?)\s*(?=\n|\r|$)", re.DOTALL)
        
        def get_subject(text_block):
            match = subject_pattern.search(text_block)
            if match:
                subject_line = match.group(1).strip()
                return " ".join(subject_line.split()[:6])
            return "NoSubject"
        
        try:
            all_docs = fitz.open(pdf_path)
            current_doc = []
            metadata_list = []
            doc_header = {}
            
            for idx, page in enumerate(all_docs):
                text = page.get_text()
                match = break_pattern.search(text)
                if match:
                    if doc_header:
                        # Save the last doc in metadata_list
                        metadata_list.append((current_doc, doc_header))
                    # Start a new doc
                    current_doc = []
                    item_type, meeting_date, agenda_num = match.groups()
                    subject = get_subject(text)
                    doc_header = {
                        "type": item_type.strip() if item_type else "Standard",
                        "date": meeting_date.strip(),
                        "agenda": f"Agenda Item #{agenda_num}",
                        "agenda_num": agenda_num,
                        "subject": subject,
                    }
                # Add page to current doc
                current_doc.append(page)
            
            if current_doc:
                # Save the last doc
                metadata_list.append((current_doc, doc_header))
            
            split_files = []
            
            for pages, meta in metadata_list:
                agenda_num = meta["agenda_num"]
                
                # Find or create corresponding agenda item folder
                target_folder = None
                
                # Determine meeting root folder
                meeting_root = pdf_path.parent
                if pdf_path.parent.name.startswith('Item'):
                    meeting_root = pdf_path.parent.parent
                
                # First, check if any agenda item folder already exists for this agenda number
                existing_folders = list(meeting_root.glob(f"Item{agenda_num}_*"))
                if existing_folders:
                    # Use the first existing folder found
                    target_folder = existing_folders[0]
                    print(f"📁 Using existing folder for agenda item #{agenda_num}: {target_folder.name}")
                else:
                    # Try to find folder from processed items
                    for item in agenda_items:
                        if str(item['index']) == agenda_num:
                            item_folder_name = f"Item{item['index']}_{self.sanitize_filename(item['subject'])}"
                            target_folder = meeting_root / item_folder_name
                            break
                    
                    # If no processed item found, create one based on supplemental report info
                    if target_folder is None:
                        item_folder_name = f"Item{agenda_num}_{self.sanitize_filename(meta['subject'])}"
                        target_folder = meeting_root / item_folder_name
                    
                    # Only create folder if it doesn't exist
                    if not target_folder.exists():
                        target_folder.mkdir(exist_ok=True)
                        print(f"📁 Created new folder for agenda item #{agenda_num}: {target_folder.name}")
                    else:
                        print(f"📁 Using existing folder for agenda item #{agenda_num}: {target_folder.name}")
                
                if target_folder:
                    # Ensure target folder exists
                    target_folder.mkdir(exist_ok=True)
                    
                    # Create filename
                    date_fmt = meta["date"].replace(",", "")
                    filename = f"{meta['agenda']} {meta['type']} {meta['subject']} {date_fmt}".strip()
                    filename = self.sanitize_filename(filename) + ".pdf"
                    out_path = target_folder / filename
                    
                    # Create new PDF with selected pages
                    new_doc = fitz.open()
                    for p in pages:
                        new_doc.insert_pdf(p.parent, from_page=p.number, to_page=p.number)
                    new_doc.save(out_path)
                    new_doc.close()
                    
                    split_files.append(out_path)
                    print(f"✅ Added supplemental file: {filename} -> {target_folder.name}")
                    logging.debug(f"✅ Split supplemental: {filename} -> {target_folder.name}")
                else:
                    logging.debug(f"⚠️ Could not create folder for agenda item #{agenda_num}")
            
            all_docs.close()
            return split_files
            
        except Exception as e:
            logging.error(f"Error splitting supplemental PDF {pdf_path}: {e}")
            return []

    def process_supplemental_reports(self, meeting_folder, processed_items):
        """Find and split supplemental reports into agenda item folders"""
        supplemental_files = self.find_supplemental_reports(meeting_folder)
        
        if not supplemental_files:
            logging.debug("No supplemental reports found")
            return
        
        print(f"🔄 Processing {len(supplemental_files)} supplemental report(s)...")
        
        for supp_file in supplemental_files:
            print(f"📄 Splitting supplemental report: {supp_file.name}")
            logging.debug(f"Found supplemental report: {supp_file.name}")
            split_files = self.split_supplemental_pdf(supp_file, processed_items)
            
            if split_files:
                print(f"✅ Successfully split {supp_file.name} into {len(split_files)} files")
                logging.debug(f"Successfully split {supp_file.name} into {len(split_files)} files")
            else:
                print(f"⚠️ No agenda items found in {supp_file.name}")
                logging.debug(f"No files were split from {supp_file.name}")
