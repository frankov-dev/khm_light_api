from app.logic.scraper import WebScraper
from app.logic.parser import OutageParser
from app.db.database import DatabaseHandler

class OutageService:
    def __init__(self):
        self.scraper = WebScraper()
        self.parser = OutageParser()
        self.db = DatabaseHandler()

    def update(self):
        text, alts = self.scraper.fetch_with_meta()
        target_dates = self.parser.extract_dates(text, alts)
        
        if not target_dates: return None

        data = self.parser.parse_content(text)
        for d in target_dates:
            self.db.save_data(data, d)
        
        return target_dates