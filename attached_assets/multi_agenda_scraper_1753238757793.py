
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from pathlib import Path
import argparse

BASE_URL = "https://cupertino.legistar.com/"
DEFAULT_OUTPUT_FOLDER = Path("OUT_MEETING_FOLDER")
DEFAULT_MEETING_URL = (
    #5/6/2025 Council meeting
    #"https://cupertino.legistar.com/MeetingDetail.aspx?"
    #"ID=1245856&GUID=C153DD99-48E6-4B4A-96F5-1281F9C3E758&Options=&Search="
    #7/15/2025 Council meeting
    "https://cupertino.legistar.com/MeetingDetail.aspx?"
    "ID=1245866&GUID=AF191DE8-9112-48C7-A96F-8A6C9B4266B9&Options=&Search="
)
CALENDAR_URL = "https://cupertino.legistar.com/calendar.aspx"

#City Council Page: 
#  - The URL loaded when the "City Council" tag is clicked
#  - The URL loaded when "City Council" is selected from the dropdown menu
CITY_COUNCIL_PAGE = (
    "https://cupertino.legistar.com/DepartmentDetail.aspx?"
    "ID=22534&GUID=759DE527-B7CF-4B4C-88AB-B83875AB732D&Mode=MainBody"
)

#Planning Commission Page: The URL loaded when "Planning Commission" is selected from the dropdown menu
#    "https://cupertino.legistar.com/DepartmentDetail.aspx?"
#    "ID=22538&GUID=D3B7D79F-7049-469E-8B05-0E51C580B6E5&R=52887ca9-76fe-4f53-864e-6c2a32a58047"

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "_", name.strip())

def fetch_soup(url, args):
    if args.verbose: 
        print(f"🌐 Fetching: {url}")
    resp = requests.get(url)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")

# Return: List of tuples: (date string, time string, full meeting URL)
def fetch_meetings_for_date(target_date: str, args):
    soup = fetch_soup(CITY_COUNCIL_PAGE, args)
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
                detail_url = urljoin("https://cupertino.legistar.com/", link_tag["href"])
                matches.append((date, time, detail_url))
    return matches

def infer_filename_with_extension(href, default_name,response):
    """
    Infers the proper filename with extension based on:
    1. Content-Disposition header (if present)
    2. URL path (if it contains an extension)
    3. Content-Type header via mimetypes
    Falls back to .bin if all else fails.
    """
    # 1. Check Content-Disposition header - the filename used for "Save Link As"
    cd = response.headers.get("Content-Disposition", "")
    if "filename=" in cd:
        # Try to match filename="Agenda.pdf"
        filename = cd.split("filename=")[-1].strip().strip('"')
        return sanitize_filename(filename)

    # 2. Check extension in URL path
    parsed_path = Path(urlparse(href).path)
    if parsed_path.suffix:
        return sanitize_filename(parsed_path.name)

    # 3. Infer from Content-Type
    content_type = response.headers.get("Content-Type", "")
    extension = mimetypes.guess_extension(content_type.split(";")[0].strip())

    return sanitize_filename(default_name) + (extension if extension else ".bin")

def download_file_to_folder(href, default_name, folder_path, args):
    try:
        response = requests.get(href)
        response.raise_for_status()
        filename = infer_filename_with_extension(href, default_name, response)
        full_path = folder_path / filename
        if full_path.exists():
            if args.verbose: print(f"📥 Skipping since file exists: {filename}")
        else:
            if args.verbose: print(f"📥 File downloaded: {filename}")
            if not args.not_download_files:
                full_path.write_bytes(response.content)
    except Exception as e:
        print(f"❌ Failed to download file from {href}: {e}")

# Return a tuple of (lable, file-name, href-to-file), such as
#    ("Published agenda", "Agenda", "https://...View.ashx?M=A&...")
def extract_meeting_extras(soup, verbose=False):
    extras = []
    EXTRA_LABELS = [
        "Published agenda",
        "Published minutes",
        "Meeting Extra1",
        "Meeting Extra2",
        "Meeting Extra3"
    ]
    all_tds = soup.find_all("td")
    i = 2 # skip entry 0 and 1, which are <td> of the outer cell
    while i < len(all_tds) - 1:
        label_td = all_tds[i]
        link_td = all_tds[i + 1]
        label = label_td.get_text(strip=True).rstrip(":")
        if label == "":
          i = i+1
          continue
        if label in EXTRA_LABELS:
            for a in link_td.find_all("a"):
                link_text = a.text.strip()
                href = urljoin(BASE_URL, a.get("href", "")) if a.get("href") else ""
                extras.append((label, link_text, href))
                if verbose:
                    no_link = " (No Link)" if href == "" else ""
                    print(f"📎 Extra: {label} — {link_text}{no_link}")
        i += 2  # move to next label+value pair
    return extras

def download_meeting_extras(dest, extras, args):
    for i, (label, text, href) in enumerate(extras, 1):
        if href == "":
            if args.verbose: print(f"📥 Skipping extra: {text} (No Link)")
            continue
        default_filename = f"Extra{i:02d} - {text}"
        download_file_to_folder(href, default_filename, dest, args)

def parse_meeting_header(soup, meeting_url, args):
    # Get the <title> tag and get its 'text' and strip leading and tailing spaces
    title = soup.find("title").text.strip()
    date_span = soup.find("span", id="ctl00_ContentPlaceHolder1_lblDate")
    meeting_date = date_span.text.strip() if date_span else "Not Found"
    time_span = soup.find("span", id="ctl00_ContentPlaceHolder1_lblTime")
    meeting_time = time_span.text.strip() if time_span else "Not Found"
    meeting_dt = f"{meeting_date} {meeting_time}"
    if args.verbose: print(f"📆 Meeting date/time: {meeting_dt}")

    # List extra items
    extras = extract_meeting_extras(soup, args)

    # List agenda items
    items = []
    table = soup.find("table", id=re.compile(r"gridMain", re.IGNORECASE))
    for i, row in enumerate(table.find_all("tr")[1:], 1):
        cols = row.find_all("td")
        if len(cols) >= 2:
            subj = cols[5].get_text("\n", strip=True)
            subj = subj.split("Subject:",1)[-1].strip()
            href = cols[0].find("a", href=True)
            if href:
                url = urljoin(BASE_URL, href['href'])
                items.append((i, subj, url))
                if args.verbose:
                    print(f"  → Item{i}: {subj}")
    return title, meeting_dt, extras, items

def write_meeting_header(output_folder, title, meeting_dt, extras, items):
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

def process_agenda_item(index, subj, url, base_folder, args):
    soup = fetch_soup(url, args) # The agenda Item page

    # On agenda date/time for item (if present)
    dt_span = soup.find("span", id=re.compile(r"lblOnAgenda2", re.IGNORECASE))
    item_dt = dt_span.text.strip() if dt_span else "Not Found"
    meta = soup.find("meta", {"name": "description"})
    desc = meta["content"].strip() if meta else ""

    # Subject short: first 6 words
    words = re.findall(r"\b\w+\b", subj)
    short = " ".join(words[:6])
    folder_name = f"Item{index} - {sanitize_filename(short)}"
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
    for a in soup.select("a[href*='View.ashx?M=F']"):
        link = urljoin(BASE_URL, a['href'])
        text = a.text.strip() or f"Attachment{len(attachments)+1}"
        attachments.append((text, link))
        lines.append(f"- [{text}]({link})")
        if args.verbose: print(f"  📎 {text}")
    #Write AgendaHeader.md
    (folder / "AgendaHeader.md").write_text("\n".join(lines), encoding="utf-8")

    # Download each attachment
    for idx, (text, href) in enumerate(attachments, 1):
        default_filename = f"Attachment{idx:02d} - {text}"
        download_file_to_folder(href, default_filename, folder, args)
    if args.verbose: print(f"✅ Finished processing Item {index}: downloaded {len(attachments)} attachments")

def extract_agenda_links(soup):
    return [a["href"] for a in soup.find_all("a", href=True) if "LegislationDetail.aspx" in a["href"]]

def parse_item_numbers(selection):
    selected = set()
    for token in selection:
        if "-" in token:
            start, end = token.split("-")
            selected.update(range(int(start), int(end) + 1))
        else:
            selected.add(int(token))
    return selected

import shutil
def process_one_meeting(meeting_url, dest, args):
    dest = Path(dest)
    if args.remove_output_folder and dest.exists():
        print(f"    🗑️ Removing existing folder: {dest}")
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    print(f"    📂 Output folder: {dest}")
    soup = fetch_soup(meeting_url, args) # The main meeting page

    #Method 1: extract all links to "LegislationDetail.aspx"
    #agenda_urls = extract_agenda_links(soup)
    #print(f"📋 Found {len(agenda_urls)} agenda items")
    #for i, relative_url in enumerate(agenda_urls, 1):
    #    full_url = urljoin(BASE_URL, relative_url)
    #    process_agenda_item(full_url, dest, i, args.verbose)

    title, meeting_dt, extras, items = parse_meeting_header(soup, meeting_url, args)
    print(f"    📋 Found {len(extras)} agenda extras")
    print(f"    📋 Found {len(items)} agenda items")
    write_meeting_header(dest, title, meeting_dt, extras, items)
    download_meeting_extras(dest, extras, args)

    selected_items = parse_item_numbers(args.selection)
    for idx, subj, url in items:
        if selected_items is None or idx in selected_items:
            print(f"\n⏩ Processing Item{idx}: {subj}")
            process_agenda_item(idx, subj, url, dest, args)
        else:
            print(f"⏩ Skipping Item {idx}: {subj}")
    print("\n✅ All done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download all agenda items and attachments from a Legistar meeting page.")
    parser.add_argument("-s", "--selection", type=str, nargs="+", help="Only download specific agenda item numbers (e.g. -i 1 3 5-7)")
    parser.add_argument("-d", "--date", type=str, metavar="MM/DD/YYYY", help="Retrieve all meetings on the date (e.g. 7/15/2025)")
    parser.add_argument("-g", "--get", type=int, help="Select the Meeting Index to get agenda (e.g. -g 1)")
    parser.add_argument("-url", "--url", type=str, default=str(DEFAULT_MEETING_URL), help="Meeting page URL")
    parser.add_argument("-o", "--output", type=str, default=str(DEFAULT_OUTPUT_FOLDER), help="Destination folder")
    parser.add_argument("-rm", "--remove-output-folder", action="store_true", help="Remove the output folder first")
    parser.add_argument("-nd", "--not-download-files", action="store_true", help="Not download files, for easier testing")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    if args.date:
        #Usage: First run "-date 7/15/2025" without "--get" to see a list of meeting indices. Then, run with "--get 1" to get the agenda downloaded
        meeting_urls = fetch_meetings_for_date(args.date, args)
        if meeting_urls:
            if args.get is None:
                print(f"Found {len(meeting_urls)} meetings on the date {args.date}:")
                for idx, (date, time_text, url) in enumerate(meeting_urls, 1):
                    print(f"    Meeting{idx} at {time_text} — {url}")
            else:
                idx = args.get
                (date, time_text, url) = meeting_urls[idx - 1]
                print(f"🔍 Getting the agenda for the Meeting{idx} on {date} at {time_text} — {url}")
                process_one_meeting(url, args.output, args)
        else:
            print(f"❌ No meetings found for {args.date}")
    else: 
        process_one_meeting(args.url, args.output, args)

