"""
Outage service - business logic layer.

Orchestrates scraping, parsing, and database operations.
"""

from app.logic.scraper import Scraper
from app.logic.parser import Parser
from app.db.database import Database
from typing import Optional


class OutageService:
    """
    Main service for outage schedule management.
    
    Coordinates:
        - Fetching data from hoe.com.ua
        - Parsing schedule content
        - Storing/retrieving from database
    """
    
    def __init__(self, db: Optional[Database] = None):
        self.scraper = Scraper()
        self.parser = Parser()
        self.db = db or Database()
    
    def update(self) -> Optional[list]:
        """
        Update database with latest schedules from website.
        
        Returns:
            List of updated dates, or None if failed.
        """
        html = self.scraper.fetch()
        if not html:
            return None
        
        blocks = self.scraper.extract_blocks(html)
        if not blocks:
            return None
        
        saved_dates = []
        for block in blocks:
            parsed = self.parser.parse_block(block)
            
            if parsed["queues"]:
                self.db.save_schedule(
                    date=parsed["date"],
                    schedules=parsed["queues"],
                    message=parsed["message"]
                )
                saved_dates.append(parsed["date"])
        
        return saved_dates if saved_dates else None
