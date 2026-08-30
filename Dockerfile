# Deskpilot -- Cloud Run container
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Install deps first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY server.py .
COPY deskpilot ./deskpilot
COPY data ./data

EXPOSE 8080

# get_fast_api_app builds the ASGI app; uvicorn serves it.
CMD ["python", "server.py"]
