FROM python:3.11-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- dev target: mount source via volume ---
FROM base AS dev

ARG UID=1000
RUN useradd -m -u ${UID} appuser && mkdir -p /app/data && chown appuser /app/data
USER appuser

COPY src/ ./src/
CMD ["python", "-m", "src.main"]
