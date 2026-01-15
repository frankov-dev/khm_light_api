"""
Khmelnytskyi Outage API

FastAPI application for power outage schedule monitoring.
Data source: hoe.com.ua (Khmelnytskoblenergo)

Usage:
    python main.py              # Run server on port 8000
    uvicorn main:app --reload   # Development with auto-reload
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db.database import Database
from app.services.outage_service import OutageService

# --- Constants ---

KYIV_TZ = ZoneInfo("Europe/Kyiv")
STATIC_DIR = Path(__file__).parent / "app" / "static"

# --- Logging Configuration ---

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# --- Utility Functions ---

def get_kyiv_date() -> str:
    """Get current date in Kyiv timezone (YYYY-MM-DD)."""
    return datetime.now(KYIV_TZ).strftime("%Y-%m-%d")


def validate_queue(queue: str) -> bool:
    """
    Validate queue format.
    
    Args:
        queue: Queue identifier (expected format: "1.1" - "6.2")
    
    Returns:
        True if queue format is valid.
    """
    return bool(re.match(r"^[1-6]\.[1-2]$", queue))


def validate_date(date_str: str) -> bool:
    """
    Validate date format.
    
    Args:
        date_str: Date string (expected format: YYYY-MM-DD)
    
    Returns:
        True if date format is valid.
    """
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return False
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def calculate_hours(intervals: list[dict]) -> float:
    """
    Calculate total outage hours from intervals.
    
    Args:
        intervals: List of dicts with start_time/start and end_time/end keys.
    
    Returns:
        Total hours as float (e.g., 5.5 for 5 hours 30 minutes).
    """
    total_minutes = 0
    for interval in intervals:
        try:
            start_str = interval.get("start_time") or interval.get("start")
            end_str = interval.get("end_time") or interval.get("end")
            start = datetime.strptime(start_str, "%H:%M")
            end = datetime.strptime(end_str, "%H:%M")
            
            # Handle overnight intervals (e.g., 23:00 to 02:00)
            if end > start:
                diff_minutes = (end - start).seconds // 60
            else:
                diff_minutes = (24 * 60 - start.hour * 60 - start.minute 
                               + end.hour * 60 + end.minute)
            total_minutes += diff_minutes
        except (ValueError, TypeError, AttributeError):
            continue
    
    return round(total_minutes / 60, 1)


# --- App Configuration ---

app = FastAPI(
    title="Khmelnytskyi Outage API",
    description="API для моніторингу графіків погодинних відключень електроенергії у Хмельницькому",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS - allow all origins for frontend/mobile integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Dependencies ---

db = Database()
service = OutageService(db)

# Static files for web UI
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --- API Endpoints ---

@app.get("/", response_model=None)
def root():
    """Serve web UI or return API info."""
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return FileResponse(str(html_file))
    return {"name": "Khmelnytskyi Outage API", "version": "1.0.0", "docs": "/docs"}


@app.get("/status")
def health_check() -> dict:
    """
    Health check endpoint.
    
    Returns:
        System status, last scrape time, and available dates.
        Useful for monitoring data freshness.
    """
    return {
        "status": "healthy",
        "last_scrape": db.get_metadata("last_updated"),
        "available_dates": db.get_dates(),
        "total_queues": 12,
    }


@app.get("/update")
def update_data() -> dict:
    """
    Fetch and update schedules from hoe.com.ua.
    
    Scrapes the official website and updates the database.
    
    Returns:
        Status, list of updated dates, and last_updated timestamp.
    """
    try:
        result = service.update()
        if result:
            return {
                "status": "success",
                "dates": result,
                "message": f"Оновлено графіки для {len(result)} дат",
                "last_updated": db.get_metadata("last_updated"),
            }
        return {"status": "error", "message": "Не вдалося отримати дані з сайту"}
    except Exception:
        logger.exception("Error updating schedules")
        return {"status": "error", "message": "Внутрішня помилка сервера"}


@app.get("/schedule/{queue}")
def get_schedule(queue: str, day: Optional[str] = None) -> dict:
    """
    Get outage schedule for a specific queue.
    
    **Parameters:**
    - queue: Queue number (1.1, 1.2, ... 6.2)
    - day: Date in YYYY-MM-DD format (optional, defaults to today)
    
    **Response format (for "СВІТЛО" app integration):**
    ```json
    {
      "queue": "3.1",
      "date": "2026-01-15",
      "status": "active",
      "intervals": [{"start": "04:00", "end": "09:00", "type": "base"}],
      "operational_message": "...",
      "last_updated": "2026-01-15T22:11:42",
      "total_hours_off": 5.0
    }
    ```
    """
    target = day or get_kyiv_date()
    
    if not validate_queue(queue):
        raise HTTPException(status_code=400, detail="Невірний формат черги. Використовуйте: 1.1 - 6.2")
    
    data = db.get_schedule(queue, target)
    intervals = [{"start": i["start_time"], "end": i["end_time"], "type": i["type"]} for i in data]
    
    return {
        "queue": queue,
        "date": target,
        "status": "active" if data else "no_data",
        "intervals": intervals,
        "operational_message": db.get_message(target),
        "last_updated": db.get_metadata("last_updated"),
        "total_hours_off": calculate_hours(data)
    }


@app.get("/schedule/{queue}/{day}")
def get_schedule_by_date(queue: str, day: str):
    """Get outage schedule for a queue on a specific date."""
    if not validate_queue(queue):
        raise HTTPException(status_code=400, detail="Невірний формат черги")
    if not validate_date(day):
        raise HTTPException(status_code=400, detail="Невірний формат дати. Використовуйте: YYYY-MM-DD")
    
    data = db.get_schedule(queue, day)
    intervals = [{"start": i["start_time"], "end": i["end_time"], "type": i["type"]} for i in data]
    
    return {
        "queue": queue,
        "date": day,
        "status": "active" if data else "no_data",
        "intervals": intervals,
        "operational_message": db.get_message(day),
        "last_updated": db.get_metadata("last_updated"),
        "total_hours_off": calculate_hours(data)
    }


@app.get("/all/{day}")
def get_all_schedules(day: str = None):
    """
    Get schedules for all queues on a specific date.
    
    **Parameters:**
    - day: Date in YYYY-MM-DD format (optional, defaults to today)
    """
    target = day or get_kyiv_date()
    
    all_schedules = db.get_all_schedules(target)
    queues = {}
    
    for queue_name, intervals in all_schedules.items():
        normalized = [{"start": i["start_time"], "end": i["end_time"], "type": i["type"]} for i in intervals]
        queues[queue_name] = {
            "intervals": normalized,
            "total_hours_off": calculate_hours(intervals)
        }
    
    return {
        "date": target,
        "last_updated": db.get_metadata("last_updated"),
        "operational_message": db.get_message(target),
        "queues": queues
    }


@app.get("/dates")
def get_dates() -> dict:
    """Get list of available dates in the database."""
    return {"dates": db.get_dates()}


# --- Entry Point ---

def run() -> None:
    """Run the API server (entry point for CLI)."""
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
