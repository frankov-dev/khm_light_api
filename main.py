from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.services.outage_service import OutageService
from app.db.database import DatabaseHandler
from datetime import date, datetime
import uvicorn
from pathlib import Path

app = FastAPI(
    title="Khmelnytskyi Outage API",
    description="API для моніторингу графіків погодинних відключень електроенергії",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = OutageService()
db = DatabaseHandler()

# Підключаємо статичні файли
static_dir = Path(__file__).parent / "app" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
def root():
    """Головна сторінка API"""
    from fastapi.responses import FileResponse
    html_file = static_dir / "index.html"
    if html_file.exists():
        return FileResponse(str(html_file))
    return {
        "name": "Khmelnytskyi Outage Monitor",
        "endpoints": [
            "/update - оновити дані з сайту",
            "/schedule/{queue} - графік для черги",
            "/schedule/{queue}/{date} - графік для черги на дату",
            "/all/{date} - всі графіки на дату",
            "/dates - доступні дати в базі"
        ]
    }

@app.get("/update")
def trigger_update():
    """Стягує дані з сайту і оновлює базу"""
    try:
        res = service.update()
        if res:
            return {
                "status": "success", 
                "dates": res,
                "message": f"Оновлено графіки для {len(res)} дат"
            }
        return {"status": "error", "message": "Не вдалося отримати дані"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/schedule/{queue}")
def get_queue_schedule(queue: str, day: str = None):
    """Повертає графік для черги (напр. 1.1) на дату"""
    target_day = day or date.today().strftime('%Y-%m-%d')
    
    # Валідація формату черги
    if not _validate_queue(queue):
        raise HTTPException(status_code=400, detail="Невірний формат черги. Використовуйте: 1.1, 1.2, ... 6.2")
    
    data = db.get_schedule(queue, target_day)
    # Нормалізуємо назви полів
    normalized_data = [{"start": item["start_time"], "end": item["end_time"], "type": item["type"]} for item in data]
    return {
        "queue": queue, 
        "date": target_day, 
        "intervals": normalized_data,
        "total_hours": _calculate_outage_hours(data)
    }

@app.get("/schedule/{queue}/{day}")
def get_queue_schedule_by_date(queue: str, day: str):
    """Повертає графік для черги на конкретну дату"""
    if not _validate_queue(queue):
        raise HTTPException(status_code=400, detail="Невірний формат черги")
    
    if not _validate_date(day):
        raise HTTPException(status_code=400, detail="Невірний формат дати. Використовуйте: YYYY-MM-DD")
    
    data = db.get_schedule(queue, day)
    # Нормалізуємо назви полів
    normalized_data = [{"start": item["start_time"], "end": item["end_time"], "type": item["type"]} for item in data]
    return {
        "queue": queue, 
        "date": day, 
        "intervals": normalized_data,
        "total_hours": _calculate_outage_hours(data)
    }

@app.get("/all/{day}")
def get_all_schedules(day: str = None):
    """Повертає графіки для всіх черг на дату"""
    target_day = day or date.today().strftime('%Y-%m-%d')
    
    all_schedules = db.get_all_schedules_for_date(target_day)
    result = {}
    
    for queue, intervals in all_schedules.items():
        # Нормалізуємо назви полів
        normalized_intervals = [{"start": item["start_time"], "end": item["end_time"], "type": item["type"]} for item in intervals]
        result[queue] = {
            "intervals": normalized_intervals,
            "total_hours": _calculate_outage_hours(intervals)
        }
    
    return {"date": target_day, "queues": result}

@app.get("/dates")
def get_available_dates():
    """Повертає список дат, для яких є дані"""
    dates = db.get_available_dates()
    return {"dates": dates}

def _validate_queue(queue: str) -> bool:
    """Перевіряє формат черги"""
    import re
    return bool(re.match(r'^[1-6]\.[1-2]$', queue))

def _validate_date(date_str: str) -> bool:
    """Перевіряє формат дати"""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def _calculate_outage_hours(intervals: list) -> float:
    """Розраховує загальну кількість годин відключення"""
    total_minutes = 0
    for i in intervals:
        try:
            start = datetime.strptime(i['start_time'], '%H:%M')
            end = datetime.strptime(i['end_time'], '%H:%M')
            # Якщо кінець менший за початок - це перехід через опівніч
            if end < start:
                diff = (24 * 60 - (start.hour * 60 + start.minute)) + (end.hour * 60 + end.minute)
            else:
                diff = (end - start).seconds // 60
            total_minutes += diff
        except:
            pass
    return round(total_minutes / 60, 1)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
