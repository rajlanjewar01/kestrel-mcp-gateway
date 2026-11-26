# ---------- Stage 1: install dependencies ----------
FROM python:3.12-slim AS base

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir . || \
    pip install --no-cache-dir \
        "mcp>=1.0.0" \
        "pydantic>=2.0" \
        "pydantic-settings>=2.0" \
        "httpx>=0.27" \
        "fastapi>=0.115" \
        "uvicorn>=0.32" \
        "python-dotenv>=1.0" \
        "aiofiles>=24.1"

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=base /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=base /usr/local/bin /usr/local/bin

# Copy application source
COPY src/ src/

# Create non-root user
RUN useradd --create-home appuser
USER appuser

ENV PYTHONPATH=/app/src
EXPOSE 8080

CMD ["python", "-m", "kestrel_gateway"]
