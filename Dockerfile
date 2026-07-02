FROM rust:1.83-slim AS replay_parser

RUN cargo install wotbreplay-inspector

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=5000

WORKDIR /app

COPY --from=replay_parser /usr/local/cargo/bin/wotbreplay-inspector /usr/local/bin/wotbreplay-inspector
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000
CMD ["sh", "-c", "gunicorn --bind ${HOST}:${PORT} wsgi:app"]
