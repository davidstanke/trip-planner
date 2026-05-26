FROM python:3.12-slim

WORKDIR /app

COPY server_cloudrun.py ./server.py
COPY static/ ./static/

RUN pip install --no-cache-dir fastapi uvicorn google-cloud-aiplatform python-dotenv

EXPOSE 8080

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
