"""
Outage service - business logic layer.

Orchestrates scraping, parsing, and database operations.
This is the main entry point for fetching and storing outage data.
"""

import logging
from typing import Optional

from app.db.database import Database
from app.logic.parser import Parser
from app.logic.scraper import Scraper

logger = logging.getLogger(__name__)


class OutageService:
    """
    Main service for outage schedule management.
    
    Coordinates:
        - Fetching data from hoe.com.ua (Scraper)
        - Parsing schedule content (Parser)
        - Storing/retrieving from database (Database)
    
    Example:
        >>> service = OutageService()
        >>> dates = service.update()
        >>> print(f"Updated: {dates}")
    """
    
    def __init__(self, db: Optional[Database] = None) -> None:
        """
        Initialize service with dependencies.
        
        Args:
            db: Database instance (creates new one if not provided).
        """
        self.scraper = Scraper()
        self.parser = Parser()
        self.db = db or Database()
    
    def update(self) -> Optional[list[str]]:
        """
        Update database with latest schedules from website.
        
        Fetches the page, extracts schedule blocks, parses them,
        and saves to database.
        
        Returns:
            List of updated dates (YYYY-MM-DD), or None if failed.
        """
        html = self.scraper.fetch()
        if not html:
            logger.warning("Failed to fetch HTML from website")
            return None
        
        blocks = self.scraper.extract_blocks(html)
        if not blocks:
            logger.warning("No schedule blocks found in HTML")
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
                logger.info(f"Saved schedule for {parsed['date']} ({len(parsed['queues'])} queues)")
        
        return saved_dates if saved_dates else None
