FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REGLENS_RAG_MODE=mock \
    REGLENS_EMBEDDING_PROVIDER=fake \
    REGLENS_LLM_PROVIDER=fake \
    REGLENS_RERANKER_PROVIDER=fake \
    REGLENS_USE_FAKE_EMBEDDINGS=true \
    REGLENS_USE_FAKE_LLM=true \
    REGLENS_USE_FAKE_RERANKER=true \
    REGLENS_DATABASE_URL=sqlite:////app/data/reglens.db

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
