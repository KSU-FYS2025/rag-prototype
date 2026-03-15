FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN UV_LINK_MODE=copy uv sync --frozen --python-preference system

COPY . .

EXPOSE 8000

CMD ["uv", "run", "--python-preference", "system", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]