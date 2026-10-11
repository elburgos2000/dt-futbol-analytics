FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Crear directorio para persistencia de datos
RUN mkdir -p /app/data
ENV DB_PATH=/app/data/dt_futbol.db

CMD ["python", "bot.py"]
