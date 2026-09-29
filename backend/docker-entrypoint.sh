#!/bin/sh
# 容器入口：以 root 启动，把挂载进来的数据目录交给 app 用户，然后降权运行真正的命令。
# 这样 `./data` 这样的宿主机目录（Docker 第一次会以 root 身份创建）不用手动 chown 也能写。
set -e

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA_DIR"
    # 只在顶层目录属主不对时才递归修正，避免每次启动都遍历成千上万个页面图
    if [ "$(stat -c %u "$DATA_DIR")" != "$(id -u app)" ]; then
        chown -R app:app "$DATA_DIR"
    fi
    exec setpriv --reuid=app --regid=app --init-groups "$@"
fi

exec "$@"
