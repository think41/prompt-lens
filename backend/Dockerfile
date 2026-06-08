FROM python:3.11-slim

WORKDIR /app

RUN pip install uv --no-cache-dir

COPY requirements.txt .
RUN uv venv /app/.venv --python 3.11 && \
    uv pip install --python /app/.venv/bin/python -r requirements.txt

RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app

COPY --chown=appuser:appuser . .

USER appuser

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=4)"

CMD ["gunicorn", "app.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-"]
