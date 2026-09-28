FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    DATA_DIR=/data

WORKDIR /app

# 先只装依赖，代码改动时可以复用这一层缓存
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

EXPOSE 8000

# --proxy-headers：从 Nginx 传来的 X-Forwarded-For 取真实客户端 IP（登录限流按 IP 计数）
CMD ["uvicorn", "--factory", "app.main:create_app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
