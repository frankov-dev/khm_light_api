from fastapi import FastAPI
from app.services.outage_service import OutageService
from app.db.database import DatabaseHandler
from datetime import date
import uvicorn

app = FastAPI(title="Khmelnytskyi Outage API")
service = OutageService()
db = DatabaseHandler()

@app.get("/update")
def trigger_update():
    """Стягує дані з сайту і оновлює базу"""
    res = service.update()
    return {"status": "success", "date": res} if res else {"status": "error"}

@app.get("/schedule/{queue}")
def get_queue_schedule(queue: str, day: str = None):
    """Повертає графік для черги (напр. 1.1) на дату"""
    target_day = day or date.today().strftime('%Y-%m-%d')
    data = db.get_schedule(queue, target_day)
    return {"queue": queue, "date": target_day, "intervals": data}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
