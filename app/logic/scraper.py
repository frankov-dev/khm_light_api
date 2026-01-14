import requests
from bs4 import BeautifulSoup

class WebScraper:
    def __init__(self):
        self.url = "https://hoe.com.ua/page/pogodinni-vidkljuchennja"
        self.headers = {"User-Agent": "Mozilla/5.0"}

    def fetch_with_meta(self):
        try:
            res = requests.get(self.url, headers=self.headers, timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')
            content = soup.find('div', class_='page-content') or soup.find('article')
            
            if not content: return "", []

            # Збираємо alt-тексти картинок для пошуку дат
            alts = [img.get('alt', '') for img in content.find_all('img')]
            text = content.get_text(separator="\n", strip=True)
            
            return text, alts
        except Exception as e:
            return "", []
