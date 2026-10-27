# Backend image for Hugging Face Spaces (Docker SDK) and local use.
# Build context is backend/:  docker build -t portfolio-risk-backend backend
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# The deploy workflow replaces this default with the commit being deployed; /health reports it.
ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}

# Spaces runs containers as uid 1000, so use the same id.
RUN useradd --create-home --uid 1000 app
WORKDIR /app

# Dependencies first, so code changes do not reinstall them.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=app:app app/ app/
COPY --chown=app:app data/ data/
# The price cache is the only place the app writes; it is disposable.
RUN mkdir -p data/price_cache && chown -R app:app data/price_cache

USER app
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
