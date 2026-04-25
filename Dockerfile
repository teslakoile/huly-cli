FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir build && python -m build --wheel

FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/teslakoile/huly-cli"
LABEL org.opencontainers.image.description="CLI for Huly project management"
LABEL org.opencontainers.image.licenses="MIT"

COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

RUN useradd --create-home --uid 1000 huly
USER huly
WORKDIR /home/huly

ENTRYPOINT ["huly"]
