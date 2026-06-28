FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN groupadd --system --gid 1000 app && \
    useradd --system --uid 1000 --gid app --create-home --home-dir /app app

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY lib/ ./lib/
COPY main.py ./

RUN chown -R app:app /app

USER 1000

ENTRYPOINT ["uv", "run", "python", "main.py"]
CMD ["watch"]
