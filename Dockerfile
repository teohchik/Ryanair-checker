FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
RUN useradd -m -u 1000 bot
COPY --from=builder /install /usr/local
COPY app app/
COPY alembic alembic/
COPY alembic.ini alembic.ini
COPY entrypoint.sh entrypoint.sh
RUN chmod +x entrypoint.sh && mkdir -p data && chown -R bot:bot /app
USER bot
ENTRYPOINT ["./entrypoint.sh"]
