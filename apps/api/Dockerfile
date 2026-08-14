# Backend image. Built from the repository root so the shared packages and
# projects are available:
#
#     docker build -f apps/api/Dockerfile .
#
# This is what Render (or any container host) builds. It is deliberately a
# Dockerfile rather than a native Python runtime, because PDF export needs
# system libraries that a managed Python environment will not let us install.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Where the application should look for repo-relative files.
#
# Stated explicitly because auto-detection cannot work in an image: it looks
# for requirements.txt, package.json and pyproject.toml together, and this
# image copies only the first. Without this the detector falls through to the
# working directory, and every repo-relative path — the Demo Mode recordings
# among them — silently points at apps/api instead of /repo.
ENV AIOPS_REPO_ROOT=/repo

# WeasyPrint renders PDFs through Pango, which is a system library rather than
# a Python one — this is exactly what is missing on a stock Windows machine and
# why PDF export does not work locally. Installing it here is what makes PDF
# export work in production (CLAUDE.md Section 9 requires PDF export).
#
# fonts-dejavu-core matters too: without a font installed, WeasyPrint produces
# a PDF containing no visible text.
RUN apt-get update && apt-get install --no-install-recommends -y \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libffi8 \
        shared-mime-info \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /repo

# Dependency manifests first, so editing application code does not invalidate
# the slow pip layer.
COPY requirements.txt ./

# Editable installs need the package directories present at install time.
# `projects/` is included because requirements.txt installs the SOP Generator
# from there — omitting it fails the build.
COPY packages ./packages
COPY services ./services
COPY projects ./projects
COPY apps/api ./apps/api

RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    # WeasyPrint is an optional extra locally (its native libraries are absent
    # on Windows). Here the libraries exist, so install it and enable PDF.
    && pip install "weasyprint>=62"

COPY scripts ./scripts
COPY data ./data

# The synthetic datasets are reproducible from the generator and gitignored, so
# they are produced at build time rather than shipped in the repository.
RUN python scripts/generate_demo_data.py

# Fail the build if the image cannot actually see what it needs at runtime.
#
# This exists because the opposite happened: an image shipped with the Demo
# Mode recordings present but unreachable, and the only symptom was the app
# quietly reporting zero of them in production. A build that is wrong should
# not produce a running service.
RUN python -c "\
from aiops_config import demo_cache_dir, repo_root; \
import sys; \
root = repo_root(); \
cache = demo_cache_dir(); \
found = len(list(cache.glob('*.json'))) if cache.is_dir() else 0; \
print(f'repo_root={root}  demo_cache={cache}  recordings={found}'); \
sys.exit(0 if str(root) == '/repo' and found > 0 else 1)"

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /repo
USER appuser

WORKDIR /repo/apps/api

# Render, Railway, and Fly all assign a port through $PORT. Hard-coding 8000
# means the platform's health check never reaches the app and the deploy hangs.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT','8000')}/health\")"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
