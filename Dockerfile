FROM python:3.13-slim

LABEL org.opencontainers.image.source="https://github.com/iam-rizz/pricewatch" \
      org.opencontainers.image.description="Pricewatch digitalregistra → WHMCS, notifikasi Telegram" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=UTC \
    STATE_FILE=/data/state.json

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY pricewatch ./pricewatch

# Non-root; /data dibuat di image supaya named volume ikut ownership user app
RUN useradd --system --uid 10001 app && mkdir /data && chown app /data
USER app
VOLUME /data

ENTRYPOINT ["python", "-m", "pricewatch.main"]
CMD ["--loop"]
