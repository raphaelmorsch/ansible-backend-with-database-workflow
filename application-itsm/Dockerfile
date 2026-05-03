FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && rm -rf /root/.cache

COPY app.py .
COPY static ./static

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

USER 1001

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
