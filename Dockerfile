FROM python:3.13-slim
ARG VERSION=0.1.0
ARG REVISION=unknown
LABEL org.opencontainers.image.source="https://github.com/narayana006/incident-rehearsal-lab" \
      org.opencontainers.image.title="Incident Rehearsal Lab" \
      org.opencontainers.image.description="Offline synthetic incident exercises and decision-time evidence" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home learner
USER 10001
ENTRYPOINT ["incident-lab"]
CMD ["demo", "kafka-lag"]
