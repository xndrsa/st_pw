FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt && playwright install --with-deps chromium

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "10000"]
