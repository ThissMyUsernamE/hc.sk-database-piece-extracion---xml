import argparse
import requests
from bs4 import BeautifulSoup
import re
import time
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

def get_shortcuts(url):
    query_parameters = parse_qs(urlparse(url).query)
    shortcuts = []
    for parameter_name, values in query_parameters.items():
        if parameter_name in {"skratky", "skratky[]"} or re.fullmatch(r"skratky\[\d+\]", parameter_name):
            shortcuts.extend(value.strip() for value in values if value.strip())
    return list(dict.fromkeys(shortcuts))

def get_works_by_shortcut(url, shortcuts, session=None):
    # Download the web page.
    if session is None:
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    response = session.get(url, timeout=30)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find the composer name in the page heading.
    composer_name = "Unknown composer"
    heading = soup.find('h1')
    if heading:
        composer_name = heading.text.strip()
    else:
        # Fall back to the composer name in the URL.
        match = re.search(r'osobnost-detail/\d+-([^/]+)', url)
        if match:
            name_parts = match.group(1).split('-')
            composer_name = " ".join(part.capitalize() for part in reversed(name_parts))

    works = []
    
    # Find all works in the timeline.
    work_items = soup.find_all('div', class_='timeline-item')
    
    filter_skratok = re.compile(
        "|".join(rf"(?<!\w)\d*\s*{re.escape(shortcut)}(?!\w)" for shortcut in shortcuts)
    ) if shortcuts else None

    for item in work_items:
        title = ""
        subtitle_type = ""
        year_created = ""
        instrumentation = ""
        
        # Extract the work title.
        main_text = item.find('p', class_='maintext')
        if main_text:
            title = main_text.text.strip()
            
        # Extract the remaining work details.
        subtexts = item.find_all('p', class_='subtext')
        for subtext in subtexts:
            text = subtext.text.strip()
            
            if text.startswith("Rok vzniku:"):
                year_created = text.replace("Rok vzniku:", "").strip()
            elif text.startswith("Obsadenie:"):
                instrumentation = text.replace("Obsadenie:", "").strip()
            elif not subtitle_type and "Text:" not in text and "Vydavateľ:" not in text:
                # Ignore source, publisher, and year labels when identifying the subtitle or work type.
                subtitle_type = text
                
        if instrumentation and filter_skratok and filter_skratok.search(instrumentation):
            works.append({
                "composer": composer_name,
                "title": title,
                "subtitle_type": subtitle_type,
                "instrumentation": instrumentation,
                "year_created": year_created
            })
            
    return works

def get_composer_urls(session, url):
    pages_to_visit = [url]
    visited_pages = set()
    composer_urls = []
    found_urls = set()

    while pages_to_visit:
        page_url = pages_to_visit.pop(0)
        if page_url in visited_pages:
            continue

        visited_pages.add(page_url)
        response = session.get(page_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        for link in soup.select("li.result-block.diela-result > a[href*='/osobnost-detail/']"):
            composer_url = urljoin(page_url, link['href'])
            if composer_url not in found_urls:
                found_urls.add(composer_url)
                composer_urls.append(composer_url)

        for link in soup.select('ul.page-nav a[href]'):
            next_page_url = urljoin(page_url, link['href'])
            if next_page_url not in visited_pages and next_page_url not in pages_to_visit:
                pages_to_visit.append(next_page_url)

        print(f"Loaded listing page {len(visited_pages)}: {len(composer_urls)} composers")
        if pages_to_visit:
            time.sleep(0.25)

    return composer_urls

def write_xml(works, output_path="repertoire.xml"):
    # Create the XML root element.
    root = ET.Element("Works")
    
    for row in works:
        work = ET.SubElement(root, "Work")
        ET.SubElement(work, "Composer").text = row["composer"]
        ET.SubElement(work, "Title").text = row["title"]
        ET.SubElement(work, "SubtitleType").text = row["subtitle_type"]
        ET.SubElement(work, "Instrumentation").text = row["instrumentation"]
        ET.SubElement(work, "YearCreated").text = row["year_created"]
        
    # Format the XML with indentation.
    xml_string = ET.tostring(root, encoding='utf-8')
    parsed_xml = minidom.parseString(xml_string)
    pretty_xml = parsed_xml.toprettyxml(indent="    ")
    
    # Write the XML file.
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(pretty_xml)
    print(f"Found {len(works)} works; XML saved to '{output_path}'.")

# Run the scraper.
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export works matching selected HC database shortcuts."
    )
    parser.add_argument(
        "listing_url",
        help="URL of an HC works listing filtered by one or more database shortcuts.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).with_name("output"),
        help="Folder for generated XML files (default: output beside this script).",
    )
    arguments = parser.parse_args()
    listing_url = arguments.listing_url
    shortcuts = get_shortcuts(listing_url)
    if not shortcuts:
        parser.error("listing_url must include a selected shortcut, such as skratky%5B0%5D=tr")

    output_dir = arguments.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Selected shortcuts: {', '.join(shortcuts)}")

    with requests.Session() as session:
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        composer_urls = get_composer_urls(session, listing_url)
        print(f"Processing {len(composer_urls)} composers...")

        xml_count = 0
        for index, composer_url in enumerate(composer_urls, start=1):
            if index > 1:
                time.sleep(0.25)
            print(f"[{index}/{len(composer_urls)}] {composer_url}")

            try:
                filtered_works = get_works_by_shortcut(composer_url, shortcuts, session)
            except requests.RequestException as error:
                print(f"Composer download failed: {error}")
                continue

            if not filtered_works:
                print("No works found for the selected shortcuts.")
                continue

            composer_name = filtered_works[0]["composer"]
            safe_name = re.sub(r'[<>:"/\\|?*]', "-", composer_name).strip(" .")
            safe_shortcuts = "_".join(re.sub(r'[<>:"/\\|?*]', "-", shortcut) for shortcut in shortcuts)
            output_path = output_dir / f"{safe_name}_{safe_shortcuts}_repertoire.xml"
            write_xml(filtered_works, output_path)
            xml_count += 1

        print(f"Done. XML files created: {xml_count}.")