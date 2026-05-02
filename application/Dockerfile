FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && rm -rf /root/.cache

COPY orders_api ./orders_api

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

USER 1001

CMD ["uvicorn", "orders_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
