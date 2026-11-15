FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home learner
USER 10001
ENTRYPOINT ["incident-lab"]
CMD ["demo", "kafka-lag"]
