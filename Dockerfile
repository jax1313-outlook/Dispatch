FROM python:3.12-slim AS base

LABEL maintainer="CIN-Lite Team"
LABEL description="Hybrid CIN-Lite contract intelligence pipeline"

RUN groupadd --gid 1000 cinlite && \
    useradd --uid 1000 --gid cinlite --create-home cinlite

WORKDIR /app

COPY pyproject.toml README.md ./
COPY cin_lite/ cin_lite/

RUN pip install --no-cache-dir ".[claude]"

RUN mkdir -p /app/logs /app/Archive && \
    chown -R cinlite:cinlite /app/logs /app/Archive

USER cinlite

ENTRYPOINT ["cin-lite"]
CMD ["--help"]
