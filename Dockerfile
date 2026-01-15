# Використовуємо легкий образ Python
FROM python:3.10-slim

# Встановлюємо робочу директорію
WORKDIR /app

# Встановлюємо змінні оточення для оптимізації Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Kyiv

# Встановлюємо системні залежності для Timezone
RUN apt-get update && apt-get install -y tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    rm -rf /var/lib/apt/lists/*

# Копіюємо файл залежностей та встановлюємо їх
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо весь код проекту
COPY . .

# Створюємо папку для бази даних (щоб монтувати volume)
RUN mkdir -p /app/data

# Оголошуємо порт
EXPOSE 8000

# Запускаємо сервер
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
