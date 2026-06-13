FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen

COPY lib/ ./lib/
COPY main.py ./

ENTRYPOINT ["uv", "run", "python", "main.py"]
CMD ["watch"]
