# Khmelnytskyi Outage API

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

API для моніторингу графіків погодинних відключень електроенергії у Хмельницькому.

Дані з офіційного сайту [hoe.com.ua](https://hoe.com.ua/page/pogodinni-vidkljuchennja) (Хмельницькобленерго).

## 🚀 Швидкий старт

```bash
# Клонування репозиторію
git clone https://github.com/username/khm-outage-monitor.git
cd khm-outage-monitor

# Створення віртуального середовища
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/macOS

# Встановлення залежностей
pip install -r requirements.txt

# Запуск сервера
python main.py
```

Сервер буде доступний за адресою: http://localhost:8000

### Розробка

```bash
# Встановлення dev-залежностей
pip install -e ".[dev]"

# Запуск з автоперезавантаженням
uvicorn main:app --reload

# Запуск тестів
pytest

# Перевірка коду (linting)
ruff check .

# Перевірка типів
mypy .
```

## 📚 API Endpoints

### Health Check
```
GET /status
```
Повертає статус системи та час останнього оновлення.

```json
{
  "status": "healthy",
  "last_scrape": "2026-01-15T22:11:42",
  "available_dates": ["2026-01-16", "2026-01-15"],
  "total_queues": 12
}
```

### Оновлення даних
```
GET /update
```
Завантажує актуальні графіки з сайту hoe.com.ua.

### Графік для черги
```
GET /schedule/{queue}
GET /schedule/{queue}/{date}
```

**Параметри:**
- `queue` — номер черги (1.1, 1.2, ... 6.2)
- `date` — дата у форматі YYYY-MM-DD (опціонально)

**Приклад відповіді:**
```json
{
  "queue": "3.1",
  "date": "2026-01-15",
  "status": "active",
  "intervals": [
    {"start": "04:00", "end": "09:00", "type": "base"},
    {"start": "13:00", "end": "18:00", "type": "base"}
  ],
  "operational_message": "У підчерги 3.1 відключення розпочнеться раніше – о 20:00",
  "last_updated": "2026-01-15T22:11:42",
  "total_hours_off": 10.0
}
```

### Всі графіки на дату
```
GET /all/{date}
```

### Доступні дати
```
GET /dates
```

## 📖 Документація

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## 🧪 Тестування

Проєкт містить 28 unit тестів для API:

```bash
# Запуск всіх тестів
pytest tests/ -v

# Запуск з coverage
pytest tests/ -v --cov=app --cov=main
```

**Тестові категорії:**
- `TestHealthCheck` — перевірка /status endpoint
- `TestScheduleEndpoints` — тести для /schedule/{queue}
- `TestAllSchedulesEndpoint` — тести для /all/{day}
- `TestDatesEndpoint` — тести для /dates
- `TestUpdateEndpoint` — тести оновлення з мокованим scraper
- `TestResponseFormat` — перевірка формату відповідей для "СВІТЛО" інтеграції
- `TestTotalHoursCalculation` — тести підрахунку годин
- `TestEdgeCases` — edge cases (минулі/майбутні дати, спец. символи)
- `TestCORS` — перевірка CORS headers
- `TestDocumentation` — доступність OpenAPI/Swagger/ReDoc

## 🗂️ Структура проєкту

```
khm_outage_monitor/
├── main.py                 # FastAPI додаток
├── requirements.txt        # Залежності
├── outages.db             # SQLite база даних
├── tests/
│   ├── conftest.py        # Pytest конфігурація
│   └── test_api.py        # Unit тести API
└── app/
    ├── core/
    │   └── models.py      # Pydantic моделі
    ├── db/
    │   └── database.py    # Робота з базою даних
    ├── logic/
    │   ├── scraper.py     # Парсинг сайту hoe.com.ua
    │   └── parser.py      # Обробка тексту графіків
    ├── services/
    │   └── outage_service.py  # Бізнес-логіка
    └── static/
        └── index.html     # Веб-інтерфейс
```

## 🗄️ База даних

SQLite з таблицями:

| Таблиця | Опис |
|---------|------|
| `queues` | Черги (1.1 — 6.2) |
| `schedules` | Інтервали відключень |
| `daily_messages` | Оперативні повідомлення |
| `metadata` | Час останнього оновлення |

## 🔧 Технології

- **Python 3.10+**
- **FastAPI** — веб-фреймворк
- **SQLite** — база даних
- **BeautifulSoup4** — парсинг HTML
- **pytest** — тестування
- **Requests** — HTTP-запити
- **Uvicorn** — ASGI сервер
- **zoneinfo** — підтримка часових поясів (Europe/Kyiv)

## ⏰ Часовий пояс

API використовує київський час (`Europe/Kyiv`) для визначення поточної дати.
Це важливо при розгортанні на серверах в інших часових поясах (AWS, GCP тощо).

```python
from zoneinfo import ZoneInfo
KYIV_TZ = ZoneInfo("Europe/Kyiv")
```

## 📱 Інтеграція

API спроєктовано для інтеграції з мобільними застосунками (наприклад, «СВІТЛО»).

**CORS** налаштований для доступу з будь-яких доменів.

### Приклад запиту (JavaScript)
```javascript
const response = await fetch('http://localhost:8000/schedule/3.1/2026-01-15');
const data = await response.json();

console.log(`Черга ${data.queue}: ${data.total_hours_off} год. без світла`);
data.intervals.forEach(i => console.log(`  ${i.start} - ${i.end}`));
```

### Приклад запиту (Python)
```python
import requests

response = requests.get("http://localhost:8000/schedule/3.1")
data = response.json()

print(f"Черга {data['queue']}: {data['total_hours_off']} год. без світла")
for interval in data["intervals"]:
    print(f"  {interval['start']} - {interval['end']}")
```

## 📝 Ліцензія

MIT — дивіться файл [LICENSE](LICENSE) для деталей.

---

**Автор:** Франков Дмитро
**Джерело даних:** [hoe.com.ua](https://hoe.com.ua) (Хмельницькобленерго)
