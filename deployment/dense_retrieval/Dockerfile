FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1 \
    DENSE_INDEX_DIR=/workspace/dense-index \
    DENSE_DEVICE=cuda HF_HOME=/workspace/huggingface
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY deployment/dense_retrieval/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY src /app/src
COPY services /app/services
EXPOSE 8002
CMD ["python", "-m", "uvicorn", "services.dense_service:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]
