# Built with uv, from uv.lock, so the image installs exactly the versions that
# were tested — transitive dependencies included.
FROM python:3.13-slim

# UV_LINK_MODE=copy: copy into the image rather than symlinking to a build
# cache that will not exist at runtime.
#
# UV_PROJECT_ENVIRONMENT sits outside /app on purpose. docker-compose
# bind-mounts ./backend over /app in development, which would otherwise shadow
# the image's virtualenv with the host's — and a Windows-built venv does not
# run on Linux.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# libpq for psycopg, build tools only while installing.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /usr/local/bin/uv

# Dependencies first, application code second: editing a view should not
# invalidate the dependency layer. --locked fails the build if uv.lock is out
# of step with pyproject.toml, rather than quietly resolving something else.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project \
    && apt-get purge -y build-essential && apt-get autoremove -y

COPY . .

# Never run as root in a container that accepts uploads.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health/ || exit 1

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
