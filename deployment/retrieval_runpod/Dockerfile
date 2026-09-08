ARG BASE_IMAGE=pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app \
    ARTIFACT_ROOT=/workspace/artifacts

WORKDIR ${APP_HOME}

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates bash \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
COPY deployment/retrieval_runpod/requirements.txt deployment/retrieval_runpod/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY configs configs
COPY scripts scripts
COPY services services
COPY src src
COPY deployment/retrieval_runpod/start_services.sh /usr/local/bin/start_services.sh

RUN sed -i 's/\r$//' /usr/local/bin/start_services.sh \
    && chmod +x /usr/local/bin/start_services.sh

EXPOSE 8000 8001 8002 8003
CMD ["/usr/local/bin/start_services.sh"]
