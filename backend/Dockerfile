# 后端镜像：api 和 worker 共用（docker-compose.yml 里 worker 只是换了启动命令）

# ---- 构建阶段：用 uv 装好依赖，最终镜像只带虚拟环境，不带 uv 和下载缓存 ----
FROM python:3.14-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# 先只装依赖，代码改动时可以复用这一层缓存。
# 不复制 .python-version：镜像里用的就是上面这个 Python，不让 uv 去找别的版本
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project


# ---- 运行阶段 ----
FROM python:3.14-slim

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/app \
    DATA_DIR=/data

# 不用 root 运行服务（入口脚本启动时修正数据目录的属主后再降权，见 docker-entrypoint.sh）
RUN useradd --system --uid 10001 --create-home --home-dir /home/app app \
    && mkdir /data && chown app:app /data

COPY --from=build /opt/venv /opt/venv

WORKDIR /app
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
# --proxy-headers：从前面的 Nginx 传来的 X-Forwarded-For 取真实客户端 IP（登录限流按 IP 计数）
CMD ["uvicorn", "--factory", "app.main:create_app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
