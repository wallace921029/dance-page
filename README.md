# 萤火（Firefly Tales）

一个 Web 端的儿童绘本阅读器：管理员上传绘本（PDF）并管理书架，孩子在平板上像翻真书一样阅读；AI 让绘本"会说话"（多角色朗读）、"会动"（画面里的主角动起来）。自用 / 小范围使用，凭邀请码注册。

- 前端：React 19 + TypeScript + Vite + Tailwind v4 + shadcn/ui
- 后端：Python + FastAPI + SQLite，另有一个后台任务 Worker（PDF 拆页、AI 生成）
- 文档：[docs/](./docs/README.md)（需求、技术设计、路线图、决策记录、交接进度）

## 一键部署（Docker）

需要装好 Docker 和 Docker Compose。

```bash
cp .env.example .env      # 编辑：管理员账号密码、AI 服务商的 Key；没有 HTTPS 时把 COOKIE_SECURE 改成 false
docker-compose up -d      # 新版 Docker 也可以写 docker compose up -d；第一次会构建镜像，需要几分钟
```

然后访问 `http://服务器:8080`，用 `.env` 里的管理员账号登录，在"用户管理 → 邀请码"里生成邀请码，把注册链接发给读者。

| 服务 | 作用 |
| --- | --- |
| `web` | Nginx：托管前端页面，把 `/api` 转发给后端；对外只有这一个端口（`WEB_PORT`，默认 8080） |
| `api` | 后端接口，启动时自动执行数据库迁移 |
| `worker` | 后台任务：PDF 拆页、AI 分析 / 朗读 / 动画视频 |

- **数据**：数据库、原始 PDF、页面图片、AI 产物都在宿主机的 `DATA_PATH` 目录（默认 `./data`），备份它即可。
- **已有自己的 Nginx（域名、HTTPS）**：`.env` 里设 `WEB_BIND=127.0.0.1`，让你的 Nginx 把整个站点转发到 `http://127.0.0.1:8080`，并带上 `X-Forwarded-For`。
- **更新版本**：`git pull && docker-compose up -d --build`。
- **AI 功能**：`.env` 里填好服务商的 Key（`DASHSCOPE_API_KEY` 等，见 `.env.example`），再登录后台的"AI 配置"选择各能力使用的服务商和模型。不填 Key 也能正常使用阅读和管理功能。
- 部署细节（镜像版本、启动顺序、非 root 运行、Nginx 配置、备份）见 [docs/05-tech-design.md 第 4 节](./docs/05-tech-design.md#4-部署)。

## 本地开发

需要 Node 24、[uv](https://docs.astral.sh/uv/)（自动安装 Python）、Google Chrome（生成图标和端到端测试用）。

```bash
scripts/dev.sh            # 一键启动：API + Worker（改代码自动重启）+ 前端；加 --lan 让局域网里的 iPad 也能访问
                          # 首次会自动安装依赖，并从模板创建 backend/.env（里面有管理员账号密码）
```

浏览器打开 `http://localhost:5173`。常用命令：

```bash
npm run build && npm run lint             # 前端类型检查、构建、检查
cd backend && uv run pytest               # 后端测试
cd backend && uv run ruff check . && uv run ruff format .
```

更多（换电脑接手、环境注意事项、端到端测试的做法）见 [docs/progress.md](./docs/progress.md)。
