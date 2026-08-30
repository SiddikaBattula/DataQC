# =============================================================================
# DataQC API - container image
#
# Two stages so the shipped image carries only the interpreter, the installed
# packages and the app - no compilers, no uv, no build cache.
#
# Dependencies are installed from uv.lock with --frozen, so every machine that
# builds this image gets byte-identical package versions.
# =============================================================================

# ---------- Stage 1: build the virtualenv -----------------------------------
FROM python:3.12-slim AS builder

# uv installs from uv.lock far faster than pip, and refuses to silently
# re-resolve. Pinned to the same uv that wrote the lock file (revision 3).
COPY --from=ghcr.io/astral-sh/uv:0.11.24 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Copy only the dependency manifests first: while these two files are
# unchanged Docker reuses the cached install layer and rebuilds take seconds.
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project


# ---------- Stage 2: runtime -------------------------------------------------
FROM python:3.12-slim AS runtime

# PYTHONUNBUFFERED is what makes log lines show up in `docker logs` straight
# away instead of sitting in a buffer until the process exits.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    HOST=0.0.0.0 \
    PORT=8000 \
    LOG_LEVEL=INFO \
    LOG_COLOR=always

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

# Run as an unprivileged user rather than root
RUN useradd --create-home --uid 1000 appuser

# Application code. data/ holds ranges.json, activity.json and conditions.json,
# which the validation modules open by relative path - hence WORKDIR /app.
COPY --chown=appuser:appuser data/ ./data/
COPY --chown=appuser:appuser *.py ./

# Writable mount point for the daily CSVs. Logs go to the terminal only.
RUN mkdir -p /app/output && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Marks the container unhealthy if the API stops answering.
# Uses urllib because curl is not installed in the slim image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/', timeout=4).status == 200 else 1)"

# Started through main.py so HOST/PORT env vars apply and uvicorn is launched
# with log_config=None, leaving our own log formatting in place.
#
# Deliberately one worker: the realtime checks hold their SPP/TotalSPM/ROP
# baselines in module globals, which are per-process and would be split if
# several workers ran side by side.
CMD ["python", "main.py"]
