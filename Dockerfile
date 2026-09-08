# Playwright's image ships Chromium + system deps already.
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app
ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .

COPY alembic.ini ./
COPY alembic ./alembic
COPY config ./config

EXPOSE 8000
CMD ["uvicorn", "bot.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
