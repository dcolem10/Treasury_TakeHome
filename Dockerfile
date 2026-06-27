# Single-container deploy: FastAPI serves both the API and the static frontend.
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY frontend ./frontend

ENV PORT=8000
EXPOSE 8000

# Run from the backend dir so `app` is importable. Honor the platform's $PORT.
WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
