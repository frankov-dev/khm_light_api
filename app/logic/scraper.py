import requests
from bs4 import BeautifulSoup
import re

class WebScraper:
    def __init__(self):
        self.url = "https://hoe.com.ua/page/pogodinni-vidkljuchennja"
        self.headers = {"User-Agent": "Mozilla/5.0"}

    def fetch_page(self):
        """Завантажує HTML сторінки"""
        try:
            res = requests.get(self.url, headers=self.headers, timeout=15)
            res.raise_for_status()
            return res.text
        except Exception as e:
            print(f"Помилка завантаження: {e}")
            return None

    def extract_schedule_blocks(self, html):
        """
        Розбиває контент на блоки по датах.
        Кожен блок містить дату та відповідний графік.
        Дата витягується з alt атрибуту картинки (формат: ГПВ-15.01.26)
        Повертає: [{"date": "2026-01-15", "schedule_text": "...", "extras_text": "..."}, ...]
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Знаходимо основний контент
        content = soup.find('div', class_='post') or soup.find('article')
        if not content:
            return []

        date_pattern = re.compile(r'ГПВ-(\d{2})\.(\d{2})\.(\d{2,4})')
        blocks = []
        
        # Отримуємо всі елементи в порядку їх появи
        all_elements = content.find_all(['img', 'ul', 'p', 'hr', 'h2', 'h3'])
        
        current_block = None
        hr_count = 0  # Рахуємо hr теги після початку блоку
        
        for elem in all_elements:
            if elem.name == 'img':
                alt = elem.get('alt', '')
                match = date_pattern.search(alt)
                if match:
                    # Зберігаємо попередній блок, якщо є
                    if current_block and current_block.get('schedule_text'):
                        blocks.append(current_block)
                    
                    # Формуємо дату
                    day, month, year = match.groups()
                    if len(year) == 2:
                        year = f"20{year}"
                    date_str = f"{year}-{month}-{day}"
                    
                    current_block = {
                        "date": date_str,
                        "schedule_text": "",
                        "extras_text": ""
                    }
                    hr_count = 0
            
            elif elem.name == 'ul' and current_block:
                # Це список з підчергами
                text = elem.get_text(separator="\n", strip=True)
                if 'підчерга' in text.lower():
                    current_block['schedule_text'] += text + "\n"
            
            elif elem.name == 'p' and current_block:
                text = elem.get_text(strip=True)
                # Оперативні зміни (додаткові відключення, раніше, довше)
                if any(kw in text.lower() for kw in ['додатково', 'раніше', 'довше', 'розпочнеться', 'триватиме']):
                    current_block['extras_text'] += text + "\n"
            
            elif elem.name == 'hr' and current_block:
                hr_count += 1
                # Якщо вже був список з підчергами і це 2+ hr - завершуємо блок
                # (перший hr після списку відділяє оперативні зміни, другий - наступний день)
                if current_block.get('schedule_text') and hr_count >= 2:
                    blocks.append(current_block)
                    current_block = None
                    hr_count = 0
            
            elif elem.name in ['h2', 'h3'] and current_block:
                # Заголовки типу "Файли співставлення адрес" означають кінець графіків
                text = elem.get_text(strip=True).lower()
                if any(kw in text for kw in ['файли', 'архів', 'рем', 'городоцький', "кам'янець"]):
                    if current_block.get('schedule_text'):
                        blocks.append(current_block)
                    current_block = None
        
        # Додаємо останній блок
        if current_block and current_block.get('schedule_text'):
            blocks.append(current_block)
        
        return blocks

    # Залишаємо старий метод для сумісності
    def fetch_with_meta(self):
        """Старий метод - для зворотної сумісності"""
        html = self.fetch_page()
        if not html:
            return "", []
        
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.find('div', class_='post') or soup.find('article')
        
        if not content:
            return "", []

        alts = [img.get('alt', '') for img in content.find_all('img')]
        text = content.get_text(separator="\n", strip=True)
        
        return text, alts
