from fastapi import FastAPI, HTTPException
from app.services.outage_service import OutageService
from app.db.database import DatabaseHandler
from datetime import date, datetime
import uvicorn

app = FastAPI(
    title="Khmelnytskyi Outage API",
    description="API для моніторингу графіків погодинних відключень електроенергії",
    version="1.0.0"
)
service = OutageService()
db = DatabaseHandler()

@app.get("/")
def root():
    """Головна сторінка"""
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
    return {
        "queue": queue, 
        "date": target_day, 
        "intervals": data,
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
    return {
        "queue": queue, 
        "date": day, 
        "intervals": data,
        "total_hours": _calculate_outage_hours(data)
    }

@app.get("/all/{day}")
def get_all_schedules(day: str = None):
    """Повертає графіки для всіх черг на дату"""
    target_day = day or date.today().strftime('%Y-%m-%d')
    
    queues = [f"{i}.{j}" for i in range(1, 7) for j in range(1, 3)]
    result = {}
    
    for q in queues:
        intervals = db.get_schedule(q, target_day)
        if intervals:
            result[q] = {
                "intervals": intervals,
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
