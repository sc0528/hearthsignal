FROM docker:29-cli AS docker-cli

FROM python:3.12-alpine

ARG VERSION=dev
LABEL org.opencontainers.image.title="Hearthsignal" \
      org.opencontainers.image.description="Privacy-first daily health briefings for home labs" \
      org.opencontainers.image.source="https://github.com/sc0528/hearthsignal" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}"

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

WORKDIR /app
COPY assets/ assets/
COPY sample-data/ sample-data/
COPY scripts/ scripts/
COPY templates/ templates/
COPY config.example.json config.live.example.json ./

RUN addgroup -S hearthsignal && adduser -S -G hearthsignal hearthsignal \
    && mkdir -p /app/reports /app/runtime \
    && chown -R hearthsignal:hearthsignal /app

ENV HEARTHSIGNAL_MODE=demo \
    HEARTHSIGNAL_INTERVAL=86400 \
    HEARTHSIGNAL_PORT=8080 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER hearthsignal
EXPOSE 8080
VOLUME ["/app/reports", "/app/runtime"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1

ENTRYPOINT ["python", "scripts/run_hearthsignal.py"]
