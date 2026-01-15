"""
Web scraper for hoe.com.ua power outage schedules.

Extracts schedule blocks with dates from the official Khmelnytskoblenergo website.
Uses image alt attributes (e.g., "ГПВ-15.01.26") for reliable date detection.
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import Optional


class Scraper:
    """
    Scraper for hoe.com.ua outage schedules page.
    
    The page structure:
        [operational changes] - BEFORE the image
        <img alt="ГПВ-DD.MM.YY"> - date marker
        <ul>base schedule</ul>
        <hr> - separator
        [next day's content]
    """
    
    URL = "https://hoe.com.ua/page/pogodinni-vidkljuchennja"
    HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    TIMEOUT = 15
    
    # Regex for date extraction from image alt (e.g., "ГПВ-15.01.26")
    DATE_PATTERN = re.compile(r'ГПВ-(\d{2})\.(\d{2})\.(\d{2,4})')
    
    def fetch(self) -> Optional[str]:
        """Fetch HTML content from the website."""
        try:
            response = requests.get(self.URL, headers=self.HEADERS, timeout=self.TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"[Scraper] Error fetching page: {e}")
            return None
    
    def extract_blocks(self, html: str) -> list:
        """
        Extract schedule blocks from HTML.
        
        Returns:
            List of dicts: [{"date": "YYYY-MM-DD", "schedule_text": "...", "extras_text": "..."}]
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("div", class_="post") or soup.find("article")
        
        if not content:
            return []
        
        elements = content.find_all(["img", "ul", "p", "hr", "h2", "h3"])
        
        # Find all date-marked images
        date_markers = []
        for i, elem in enumerate(elements):
            img = elem if elem.name == "img" else elem.find("img") if elem.name == "h2" else None
            if img:
                match = self.DATE_PATTERN.search(img.get("alt", ""))
                if match:
                    day, month, year = match.groups()
                    year = f"20{year}" if len(year) == 2 else year
                    date_markers.append({"index": i, "date": f"{year}-{month}-{day}"})
        
        blocks = []
        for idx, marker in enumerate(date_markers):
            img_index = marker["index"]
            date_str = marker["date"]
            
            # Find extras start (after previous hr or beginning)
            extras_start = 0
            if idx > 0:
                prev_index = date_markers[idx - 1]["index"]
                for j in range(prev_index + 1, img_index):
                    if elements[j].name == "hr":
                        extras_start = j + 1
                        break
            
            # Find schedule end (next hr or next date image)
            schedule_end = len(elements)
            for j in range(img_index + 1, len(elements)):
                elem = elements[j]
                if elem.name == "hr":
                    schedule_end = j
                    break
                img = elem if elem.name == "img" else elem.find("img") if elem.name == "h2" else None
                if img and self.DATE_PATTERN.search(img.get("alt", "")):
                    schedule_end = j
                    break
            
            # Collect extras text (before image)
            extras_text = ""
            keywords = ["підчерг", "відключення", "знеструм", "раніше", "довше", "додатково", "укренерго"]
            for j in range(extras_start, img_index):
                if elements[j].name == "p":
                    text = elements[j].get_text(strip=True)
                    if not text.startswith("Електроенергія у підчерг"):
                        if any(kw in text.lower() for kw in keywords):
                            extras_text += text + "\n"
            
            # Collect schedule text (after image)
            schedule_text = ""
            for j in range(img_index + 1, schedule_end):
                if elements[j].name == "ul":
                    text = elements[j].get_text(separator="\n", strip=True)
                    if "підчерга" in text.lower():
                        schedule_text += text + "\n"
            
            if schedule_text:
                blocks.append({
                    "date": date_str,
                    "schedule_text": schedule_text,
                    "extras_text": extras_text.strip()
                })
        
        return blocks
