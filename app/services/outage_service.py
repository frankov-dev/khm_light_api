from app.logic.scraper import WebScraper
from app.logic.parser import OutageParser
from app.db.database import DatabaseHandler

class OutageService:
    def __init__(self):
        self.scraper = WebScraper()
        self.parser = OutageParser()
        self.db = DatabaseHandler()

    def update_from_web(self):
        text = self.scraper.fetch()
        target_date = self.parser.extract_date(text)
        if target_date:
            data = self.parser.parse_content(text)
            self.db.save_data(data, target_date)
            return target_date
        return None
