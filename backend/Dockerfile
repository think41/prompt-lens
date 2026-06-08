FROM python:3.11-slim

WORKDIR /app

RUN pip install uv --no-cache-dir

COPY requirements.txt .
RUN uv venv /app/.venv --python 3.11 && \
    uv pip install --python /app/.venv/bin/python -r requirements.txt

COPY . .

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
