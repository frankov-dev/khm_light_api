from app.logic.scraper import WebScraper
from app.logic.parser import OutageParser
from app.db.database import DatabaseHandler

class OutageService:
    def __init__(self):
        self.scraper = WebScraper()
        self.parser = OutageParser()
        self.db = DatabaseHandler()

    def update(self):
        """
        Оновлює базу даних графіками з сайту.
        Підтримує парсинг кількох днів одночасно.
        """
        html = self.scraper.fetch_page()
        if not html:
            return None
        
        # Отримуємо блоки графіків (кожен блок - окремий день)
        blocks = self.scraper.extract_schedule_blocks(html)
        
        if not blocks:
            # Fallback на старий метод
            text, alts = self.scraper.fetch_with_meta()
            target_dates = self.parser.extract_dates(text, alts)
            if not target_dates:
                return None
            data = self.parser.parse_content(text)
            for d in target_dates:
                self.db.save_data(data, d)
            return target_dates
        
        saved_dates = []
        
        for block in blocks:
            # Парсимо кожен блок окремо
            parsed = self.parser.parse_schedule_block(block)
            date = parsed["date"]
            queues = parsed["queues"]
            
            if queues:
                # Конвертуємо у формат для бази даних, обробляючи зміни
                data = self._process_intervals(queues)
                
                if data:
                    self.db.save_data(data, date)
                    saved_dates.append(date)
        
        return saved_dates if saved_dates else None
    
    def _process_intervals(self, queues):
        """
        Обробляє інтервали, фільтруючи невалідні та застосовуючи зміни.
        """
        data = {}
        
        for queue_num, intervals in queues.items():
            processed = []
            
            for interval in intervals:
                # Пропускаємо інтервали з None значеннями
                start = interval.get('start')
                end = interval.get('end')
                int_type = interval.get('type', 'base')
                
                if start and end:
                    processed.append({
                        'start': start,
                        'end': end,
                        'type': int_type
                    })
            
            if processed:
                data[queue_num] = processed
        
        return data
    
    def get_schedule_for_queue(self, queue: str, date: str = None):
        """Отримує графік для конкретної черги"""
        from datetime import date as date_type
        target_date = date or date_type.today().strftime('%Y-%m-%d')
        return self.db.get_schedule(queue, target_date)