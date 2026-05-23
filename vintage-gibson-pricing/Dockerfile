FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/
COPY app/ ./app/
COPY data/seed/ ./data/seed/
COPY artifacts/ ./artifacts/
COPY scripts/ ./scripts/

RUN pip install --no-cache-dir -e ".[app]"

ENV PYTHONPATH=/app/src
EXPOSE 8501

CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
