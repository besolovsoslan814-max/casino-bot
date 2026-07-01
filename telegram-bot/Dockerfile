FROM python:3.11-slim

WORKDIR /app

# Build context is repo root, so reference telegram-bot/ explicitly
COPY telegram-bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY telegram-bot/ .

CMD ["python", "main.py"]
