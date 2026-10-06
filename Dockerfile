FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    fastapi \
    uvicorn \
    sqlalchemy \
    psycopg2-binary \
    pydantic \
    pyyaml \
    httpx \
    pytest \
    ruff \
    bandit \
    radon \
    sentence-transformers

COPY . .
RUN pip install --no-cache-dir -e .

EXPOSE 8000 8089

CMD ["uvicorn", "mas.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
