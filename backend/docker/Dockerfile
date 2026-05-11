FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install -e .

COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts

EXPOSE 8000

CMD ["gunicorn", "-k", "eventlet", "-w", "1", "-b", "0.0.0.0:8000", "app:create_wsgi_app()"]
