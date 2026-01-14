import requests
from bs4 import BeautifulSoup

class WebScraper:
    def __init__(self):
        self.url = "https://hoe.com.ua/page/pogodinni-vidkljuchennja"
        self.headers = {"User-Agent": "Mozilla/5.0"}

    def fetch(self):
        try:
            res = requests.get(self.url, headers=self.headers, timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')
            # Шукаємо контент за структурою сайту
            content = soup.find('div', class_='page-content') or soup.find('article')
            return content.get_text(separator="\n", strip=True) if content else ""
        except Exception as e:
            print(f"Scraper error: {e}")
            return ""
