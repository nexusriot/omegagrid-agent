FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    jq \
    ripgrep \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -U pip

COPY gateway/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY gateway /app/gateway
COPY core /app/core
COPY memory /app/memory
COPY llm /app/llm
COPY tools /app/tools
COPY skills /app/skills
COPY observability /app/observability
COPY integrations /app/integrations
COPY scheduler /app/scheduler

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
