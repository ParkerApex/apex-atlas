# Apex Atlas generator API — container image for `atlas serve`.
#
# Builds the package (hatchling/PEP 517) and runs the dev API server. The image
# is for hosting the on-demand generator behind the web UI (docs/generator.html).
#
#   docker build -t apex-atlas .
#   docker run --rm -p 8080:8080 apex-atlas
#   curl http://127.0.0.1:8080/health
#
# Most PaaS platforms inject $PORT; `atlas serve` honors it (falls back to 8080).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080 \
    ATLAS_GEN_TIMEOUT=180

WORKDIR /app

# Install the package. Only what the build needs is copied so the layer caches well.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install .

# Run unprivileged.
RUN useradd --create-home --uid 10001 atlas
USER atlas

EXPOSE 8080

# Liveness via the API's own /health (no curl in slim images).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request as u; u.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/health').read()" || exit 1

# Bind all interfaces in a container; honor the platform-injected $PORT.
CMD ["sh", "-c", "atlas serve --host 0.0.0.0 --port ${PORT:-8080}"]
