# 技术设计（第一期）

> 状态：初稿，待确认 · 最后更新 2026-09-28

本文把 [第一期 MVP 范围](./04-mvp-scope.md) 落到技术方案上，同时为 AI 阶段预留扩展位置。产品规则以 01–04 文档为准，本文只讲"怎么做"。

## 1. 总体架构

```
平板 / 电脑浏览器
   │  HTTPS
   ▼
Caddy（自动 HTTPS 证书）
   ├── /          → 前端静态文件（Vite 构建产物，React SPA）
   └── /api/*     → FastAPI（uvicorn）
                        │
                        ├── SQLite（app.db，WAL 模式）
                        └── 本地磁盘 DATA_DIR（原始 PDF、页面图片）
                        ▲
Worker 进程（后台任务）──┘  轮询 jobs 表，执行 PDF 拆页；AI 阶段执行生成任务
```

| 组件 | 选择 | 理由 |
| --- | --- | --- |
| 后端框架 | Python + FastAPI | PDF 处理与 AI 生态最成熟（D38）；默认端口 8000，与前端现有 `/api` 代理一致 |
| 数据库 | SQLite + SQLAlchemy 2.0 + Alembic | 单服务器、小范围使用，无需单独维护数据库服务；Alembic 管理表结构迁移 |
| 文件存储 | 服务器本地磁盘 | 512GB 足够，见 [产品概述 - 存储](./01-product-overview.md#存储与图片质量) |
| 后台任务 | 独立 Worker 进程 + 数据库任务表 | 拆页是 CPU 密集任务，不能拖慢 API；任务记录在库里，服务重启不丢；AI 阶段的长任务直接复用；不需要引入 Redis |
| 反向代理 | Caddy | 自动申请和续期 HTTPS 证书，配置最少 |
| 部署 | Docker Compose（caddy / api / worker 三个服务） | 一条命令启动，环境可复现 |

## 2. 后端

### 2.1 目录结构

```
backend/
├── pyproject.toml          # uv 管理依赖
├── alembic.ini
├── migrations/             # 数据库迁移
├── app/
│   ├── main.py             # FastAPI 应用入口，挂载各路由
│   ├── config.py           # 配置（pydantic-settings，读取环境变量）
│   ├── db.py               # 数据库连接
│   ├── models.py           # 数据表定义
│   ├── auth/               # 登录、注册、会话、权限依赖
│   ├── invites/            # 邀请码
│   ├── readers/            # 读者管理
│   ├── books/              # 绘本（管理端 + 阅读端接口）、文件访问
│   └── worker/             # Worker 主循环、任务定义、PDF 拆页
└── tests/                  # pytest
```

主要依赖：`fastapi`、`uvicorn`、`sqlalchemy`、`alembic`、`pydantic-settings`、`pypdfium2`（PDF 渲染）、`pillow`（WebP 编码）、`argon2-cffi`（密码哈希）、`python-multipart`（文件上传）。开发工具：`ruff`（检查与格式化）、`pytest`。

### 2.2 配置（环境变量）

| 变量 | 说明 |
| --- | --- |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 管理员账号密码。启动时同步到 users 表（不存在则创建，密码变化则更新） |
| `DATA_DIR` | 数据目录，存放 `app.db` 和所有绘本文件 |
| `MAX_UPLOAD_MB` | 上传上限，默认 200 |
| `APP_SECRET_KEY` | AI 阶段用于加密存储 API Key；第一期可先配置好 |

### 2.3 数据模型

```
users
  id, username (唯一), password_hash, role ('admin' | 'reader'),
  is_disabled, created_at

sessions
  id, token_hash (唯一), user_id, created_at, expires_at, last_seen_at

invite_codes
  id, code (唯一), created_at, expires_at, revoked_at,
  used_by_user_id, used_at
  → 状态由字段推导：未使用 / 已使用 / 已过期 / 已作废

books
  id (UUID), title, original_filename, file_size,
  language ('zh' | 'en' | 空), orientation ('portrait' | 'landscape'),
  cover_page_index, page_count,
  visibility ('listed' | 'unlisted'),
  processing_status ('processing' | 'ready' | 'failed'), processing_error,
  created_at, updated_at

pages
  id, book_id, page_index (从 0 开始), width, height（渲染后的像素尺寸）

jobs
  id, type ('render_pdf'), book_id,
  status ('queued' | 'running' | 'done' | 'failed'),
  progress_done, progress_total, error, attempts,
  created_at, started_at, finished_at
```

- 阅读端书架只返回 `visibility = listed` 且 `processing_status = ready` 的绘本。
- 页面文件路径由 `book_id + page_index` 推导，不存进数据库。
- AI 阶段新增的字段和表见 [第 5 节](#5-为-ai-阶段预留)。

### 2.4 文件存储布局

```
DATA_DIR/
├── app.db
└── books/{book_id}/
    ├── original.pdf           # 保留原始文件，便于重新渲染
    ├── pages/0000.webp        # 页面大图（长边 2048px）
    ├── pages/0001.webp
    └── cover.webp             # 书架用的小封面（长边 480px）
```

书架只加载小封面，打开绘本后才加载页面大图。

### 2.5 账户、会话与权限

- **密码**：argon2id 哈希存储。
- **会话**：登录后生成随机令牌，写入 Cookie（`HttpOnly`、`Secure`、`SameSite=Lax`），数据库只存令牌的哈希。
- **30 天滑动续期**：每次请求检查会话，距上次续期超过 1 天就把过期时间顺延到 30 天后。
- **禁用读者**：立即删除该读者的所有会话，下一次请求即被登出。
- **防暴力破解**：登录和注册接口按 IP 和用户名限制失败次数（内存计数即可）。
- **邀请码格式**：8 位，去掉易混淆字符（0/O、1/I/L），显示为 `K7M3-Q9TX`。注册链接为 `/register?code=K7M3Q9TX`。
- **权限**：两个 FastAPI 依赖：`require_user`（任意已登录、未禁用的用户，管理员也可以用阅读端预览）和 `require_admin`。
- **CSRF**：`SameSite=Lax` Cookie，加上非上传接口只接受 JSON 请求体，足以覆盖本项目场景。

### 2.6 API 概览

所有接口以 `/api` 开头。

**账户**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/logout` | 退出 |
| POST | `/api/auth/register` | 邀请码 + 用户名 + 密码注册，成功后直接登录 |
| GET | `/api/auth/me` | 当前用户（前端路由守卫用） |

**阅读端**（`require_user`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/books` | 书架列表，按上传时间倒序 |
| GET | `/api/books/{id}` | 绘本信息 + 页面列表（每页的宽高和图片地址） |
| GET | `/api/books/{id}/cover` | 小封面图片 |
| GET | `/api/books/{id}/pages/{index}` | 页面图片 |

图片接口先校验登录，再由 FastAPI 返回文件，并带长期缓存头（`Cache-Control: private`）。图片地址带版本参数，更换封面或重新渲染后地址变化，缓存自动失效。

**管理端**（`require_admin`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/admin/books` | 上传 PDF（multipart），返回新绘本 |
| GET | `/api/admin/books` | 全部绘本（含下架、处理中、失败） |
| GET | `/api/admin/books/{id}` | 绘本详情 + 处理进度 |
| PATCH | `/api/admin/books/{id}` | 修改书名、语言、版式、封面页、上下架 |
| DELETE | `/api/admin/books/{id}` | 删除绘本（数据库记录 + 文件目录） |
| POST | `/api/admin/invites` | 生成邀请码（可指定有效天数，默认 7） |
| GET | `/api/admin/invites` | 邀请码列表 |
| POST | `/api/admin/invites/{id}/revoke` | 作废邀请码 |
| GET | `/api/admin/readers` | 读者列表 |
| PATCH | `/api/admin/readers/{id}` | 禁用 / 启用 |
| POST | `/api/admin/readers/{id}/reset-password` | 管理员设置新密码 |

### 2.7 PDF 上传与拆页流程

```
1. 上传：前端显示上传进度
   后端流式写入磁盘（不把 200MB 读进内存），校验大小 ≤ 200MB、文件头为 %PDF
   → 创建 book（processing）+ 保存 original.pdf + 创建 render_pdf 任务
2. Worker 领取任务：
   用 pypdfium2 打开 PDF（加密或损坏 → 标记 failed，写入中文错误原因）
   逐页渲染：长边缩放到 2048px → WebP（质量 80）→ 写入 pages/，更新进度
   按多数页面的宽高比判断整本书是横版还是竖版
   用第 0 页生成小封面 cover.webp
3. 完成：processing_status = ready，visibility = listed（默认上架）
```

- 管理端详情页轮询进度，显示"处理中 12 / 30"。
- 2048px、质量 80 是初始值，放在配置常量里，用真实绘本实测后再校准。
- Worker 启动时，把上次中断的 `running` 任务重新放回队列。
- 处理过程中绘本被删除时，Worker 每渲染一页检查一次，发现绘本已删除就终止任务。
- 更换封面时同步重新生成 `cover.webp`。

## 3. 前端

### 3.1 应用结构

一个 Vite 应用，两块区域按路由拆分，分别打包、按需加载：

| 路由 | 页面 | 风格 |
| --- | --- | --- |
| `/login`、`/register` | 登录、注册（注册页从 `?code=` 读取邀请码） | 小剧场 |
| `/` | 书架 | 小剧场 |
| `/books/:id` | 阅读页 | 小剧场 |
| `/admin/books`、`/admin/books/:id` | 绘本列表、绘本详情与编辑 | shadcn/ui 工具风 |
| `/admin/invites`、`/admin/readers` | 邀请码、读者管理 | shadcn/ui 工具风 |

- **路由守卫**：进入页面前请求 `/api/auth/me`，未登录跳转登录页，读者访问 `/admin` 跳回书架。
- **数据请求**：继续使用现有的 axios 实例，新增 `@tanstack/react-query` 管理缓存、加载状态和进度轮询。
- **小剧场主题**：在阅读端根元素下定义一套独立的 CSS 变量（配色见 [阅读端需求](./02-reader.md#视觉风格小剧场)），不修改 shadcn 的全局主题，Admin 端不受影响。
- **字体自托管**：ZCOOL XiaoWei、ZCOOL QingKe HuangYou、Noto Sans SC 通过 `@fontsource` 打包进项目。不使用 Google Fonts CDN，国内访问更稳定。

### 3.2 仿真翻页

- **候选库：StPageFlip（`page-flip`，MIT 许可）**。它支持卷页效果、触屏拖拽、封面单独显示、单页 / 双页模式。
- 该库近几年更新不活跃，因此**开发第一步先做技术验证**（见第 6 节），确认在 iPad Safari 上可用后再正式接入。
- 排版规则按 [阅读端需求](./02-reader.md#横竖版排版) 实现：竖版书横屏对开、封面单独一页，其余情况单页。平板旋转时重新计算排版。
- **预加载**（P1）：当前页前后各 2 页的图片提前加载。
- **全屏**：使用浏览器全屏 API（iPad Safari 需要带 webkit 前缀）；从主屏幕打开时本身就是全屏，隐藏全屏按钮。

### 3.3 添加到主屏幕（P1）

- 提供 `manifest.webmanifest` 和 iOS 所需的 `apple-mobile-web-app-*` meta 标签、图标。
- 第一期不做离线缓存（不引入 Service Worker）。

## 4. 部署

```
docker compose
├── caddy    # 对外 80/443；托管前端构建产物；/api 转发给 api
├── api      # uvicorn app.main:app（单进程）
└── worker   # python -m app.worker
共享数据卷：DATA_DIR
```

- 需要一个指向云服务器的**域名**，Caddy 用它自动申请 HTTPS 证书。
- Caddy 请求体上限设为 210MB，略高于应用层的 200MB，以便返回清晰的中文错误提示。
- **备份建议**：每天用 SQLite 的在线备份命令导出一份 `app.db`，连同 `books/` 目录同步到另一个位置（对象存储或另一块磁盘）。原始 PDF 在书在，页面图片可以重新生成。

## 5. 为 AI 阶段预留

第一期不实现，以下内容只为确认现有结构不需要推倒重来：

- **pages 表新增字段**：`script_text`（朗读台词）、`script_source`（`ocr` / `edited`）、`audio_script_hash`（生成音频时台词的哈希，与当前台词不一致即说明音频已过期，只需重做该页）、音频和视频的生成状态。
- **books 表新增字段**：`ai_status`（未处理 / 处理中 / Dance Ready!）。
- **jobs 表新增任务类型**：`ocr_page`、`tts_page`、`video_page`，每页一个任务，天然支持单页重做和部分失败重试。
- **新增 ai_settings 表**：OCR、TTS、视频分别存储服务商、模型、Base URL、API Key。API Key 用 `APP_SECRET_KEY` 加密存储，接口永远不返回明文。
- **文件**：`books/{book_id}/audio/`、`books/{book_id}/video/`，访问方式与页面图片相同。

## 6. 风险与技术验证

| 风险 | 应对 |
| --- | --- |
| StPageFlip 在 iPad Safari 上的效果、性能不达标，或无法强制横版书单页显示 | **开发第一步**：用 2–3 本真实绘本（横竖版各有）做验证，检查卷页效果、30+ 页的流畅度、横竖屏切换、单页 / 双页切换。不达标则换用其他库或自研 CSS 3D 翻页 |
| 扫描版 PDF 体积大、页数多，拆页耗时长 | 逐页渲染、实时显示进度；Worker 独立进程，不影响其他操作 |
| SQLite 并发写入 | 开启 WAL 模式；只有一个 Worker 进程，写入冲突极少 |
| 国内访问外部资源不稳定 | 字体和前端依赖全部打包自托管，不依赖外部 CDN |

## 7. 开发顺序

| 里程碑 | 内容 | 完成标志 |
| --- | --- | --- |
| M0 技术验证 | 仿真翻页库在 iPad Safari 上的验证 | 确定翻页方案 |
| M1 后端骨架与账户 | 项目结构、数据库迁移、管理员同步、登录 / 注册 / 会话、邀请码、读者管理 | 可以用邀请码注册读者并登录 |
| M2 上传与拆页 | 上传接口、Worker、拆页、Admin 绘本列表与编辑 | 上传一本 PDF 后能在 Admin 看到处理进度和页面 |
| M3 阅读端 | 小剧场书架、阅读页、横竖版排版、全屏 | 读者在 iPad 上完整读完一本书 |
| M4 打磨与上线 | 预加载、添加到主屏幕、Docker Compose 部署、备份 | 在云服务器上通过 HTTPS 访问 |
