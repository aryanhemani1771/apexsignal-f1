# ApexSignal F1 — single-container portfolio image.
# NOTE: not build-verified in the Phase 0 authoring environment (no local Docker).
# See ROADMAP.md "Verification status". CI (deploy.yml) is the source of truth for the build.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_MODE=fixture \
    EXECUTION_MODE=paper \
    ENABLE_LIVE_TRADING=false

# uv for fast, reproducible installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install deps first for layer caching.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --extra api --extra dashboard --extra data --extra models --extra sim

COPY . .

EXPOSE 8501 8000

# Default: the public portfolio dashboard in fixture mode (no credentials required).
CMD ["uv", "run", "streamlit", "run", "dashboard/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
