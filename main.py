"""
Khmelnytskyi Outage API

FastAPI application for power outage schedule monitoring.
Data source: hoe.com.ua (Khmelnytskoblenergo)
"""

import re
from datetime import date, datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db.database import Database
from app.services.outage_service import OutageService

# --- App Configuration ---

app = FastAPI(
    title="Khmelnytskyi Outage API",
    description="API для моніторингу графіків погодинних відключень електроенергії у Хмельницькому",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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
STATIC_DIR = Path(__file__).parent / "app" / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --- Utility Functions ---

def validate_queue(queue: str) -> bool:
    """Validate queue format (1.1 - 6.2)."""
    return bool(re.match(r"^[1-6]\.[1-2]$", queue))


def validate_date(date_str: str) -> bool:
    """Validate date format (YYYY-MM-DD)."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def calculate_hours(intervals: list) -> float:
    """Calculate total outage hours from intervals."""
    total_minutes = 0
    for i in intervals:
        try:
            start = datetime.strptime(i.get("start_time") or i.get("start"), "%H:%M")
            end = datetime.strptime(i.get("end_time") or i.get("end"), "%H:%M")
            diff = (end - start).seconds // 60 if end > start else (24 * 60 - start.hour * 60 - start.minute + end.hour * 60 + end.minute)
            total_minutes += diff
        except (ValueError, TypeError):
            pass
    return round(total_minutes / 60, 1)


# --- API Endpoints ---

@app.get("/")
def root():
    """Web UI or API info."""
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return FileResponse(str(html_file))
    return {"name": "Khmelnytskyi Outage API", "version": "1.0.0", "docs": "/docs"}


@app.get("/status")
def health_check():
    """
    Health check endpoint.
    
    Returns system status and last successful scrape time.
    Useful for monitoring data freshness.
    """
    return {
        "status": "healthy",
        "last_scrape": db.get_metadata("last_updated"),
        "available_dates": db.get_dates(),
        "total_queues": 12
    }


@app.get("/update")
def update_data():
    """
    Fetch and update schedules from hoe.com.ua.
    
    Scrapes the official website and updates the database.
    Returns list of dates that were updated.
    """
    try:
        result = service.update()
        if result:
            return {
                "status": "success",
                "dates": result,
                "message": f"Оновлено графіки для {len(result)} дат",
                "last_updated": db.get_metadata("last_updated")
            }
        return {"status": "error", "message": "Не вдалося отримати дані з сайту"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schedule/{queue}")
def get_schedule(queue: str, day: str = None):
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
    target = day or date.today().strftime("%Y-%m-%d")
    
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
    target = day or date.today().strftime("%Y-%m-%d")
    
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
def get_dates():
    """Get list of available dates in the database."""
    return {"dates": db.get_dates()}


# --- Entry Point ---

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
