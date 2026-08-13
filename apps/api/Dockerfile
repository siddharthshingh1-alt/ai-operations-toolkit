# Backend image. Built from the repo root so the shared packages are available:
#   docker build -f apps/api/Dockerfile .

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /repo

# Copy only what the dependency install needs first, so editing application
# code does not invalidate the (slow) pip layer.
COPY requirements.txt ./
COPY packages/config/pyproject.toml ./packages/config/
COPY packages/utils/pyproject.toml ./packages/utils/
COPY packages/ai/pyproject.toml ./packages/ai/
COPY packages/database/pyproject.toml ./packages/database/
COPY packages/adapters/pyproject.toml ./packages/adapters/
COPY services/workflow-engine/pyproject.toml ./services/workflow-engine/
COPY services/analytics/pyproject.toml ./services/analytics/
COPY services/document-processing/pyproject.toml ./services/document-processing/

# Editable installs need the package directories to exist at install time.
COPY packages ./packages
COPY services ./services
RUN pip install -r requirements.txt

COPY apps/api ./apps/api
COPY scripts ./scripts

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /repo
USER appuser

WORKDIR /repo/apps/api
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
