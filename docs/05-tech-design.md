# 技术设计（第一期）

> 状态：已确认 · 最后更新 2026-09-28

本文把 [第一期 MVP 范围](./04-mvp-scope.md) 落到技术方案上，同时为 AI 阶段预留扩展位置。产品规则以 01–04 文档为准，本文只讲"怎么做"。

## 1. 总体架构

```
平板 / 电脑浏览器
   │
   ▼
Nginx（用户自行配置，含域名 / HTTPS）
   ├── /          → 前端静态文件（Vite 构建产物，React SPA）
   └── /api/*     → FastAPI（uvicorn，127.0.0.1:8000）
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
| 反向代理 | Nginx（用户自行配置） | 用户已有 Nginx 运维经验；域名、HTTPS 均由用户负责（D39） |
| 部署 | Docker Compose（api / worker 两个服务） | 一条命令启动，环境可复现 |

## 2. 后端

### 2.1 目录结构

```
backend/
├── pyproject.toml          # uv 管理依赖（Python 3.13）
├── Dockerfile
├── alembic.ini
├── migrations/             # 数据库迁移（API 启动时自动执行 upgrade head）
├── app/
│   ├── main.py             # 应用工厂 create_app()：迁移、同步管理员、挂载路由
│   ├── config.py           # 配置（pydantic-settings，读取环境变量 / backend/.env）
│   ├── db.py               # 数据库连接、UTC 时间列类型
│   ├── clock.py            # 统一取当前时间（测试可快进）
│   ├── deps.py             # 公共依赖：数据库会话、当前用户、require_user / require_admin
│   ├── errors.py           # 错误响应统一为 {"detail": "中文提示"}
│   ├── models.py           # 数据表定义
│   ├── auth/               # 登录、注册、会话、密码、限流、管理员同步
│   ├── invites/            # 邀请码
│   ├── readers/            # 读者管理
│   ├── books/              # 绘本（管理端 + 阅读端接口）、文件访问（M2）
│   └── worker/             # Worker 主循环、任务定义、PDF 拆页（M2）
├── scripts/                # 开发用脚本（M0 样本拆页）
└── tests/                  # pytest
```

主要依赖：`fastapi`、`uvicorn`、`sqlalchemy`、`alembic`、`pydantic-settings`、`pypdfium2`（PDF 渲染）、`pillow`（WebP 编码）、`argon2-cffi`（密码哈希）、`python-multipart`（文件上传）。开发工具：`ruff`（检查与格式化）、`pytest`。

### 2.2 配置（环境变量）

| 变量 | 说明 |
| --- | --- |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 管理员账号密码。启动时同步到 users 表（不存在则创建，密码变化则更新） |
| `DATA_DIR` | 数据目录，存放 `app.db` 和所有绘本文件 |
| `MAX_UPLOAD_MB` | 上传上限，默认 200 |
| `DASHSCOPE_API_KEY`、`VOLCENGINE_ARK_API_KEY`、`VOLCENGINE_SPEECH_API_KEY` | AI 阶段的服务商凭据（D82），见 [06 第 3 节](./06-ai-tech-design.md#3-ai-配置)；不用的服务商可以留空 |
| `COOKIE_SECURE` | 会话 Cookie 是否带 `Secure`，默认 `true`；未配置 HTTPS 时设为 `false` |
| `API_PORT` | 仅 Docker Compose 使用：API 在本机监听的端口，默认 8000 |

部署时写在仓库根目录的 `.env`（模板 `.env.example`），本地开发写在 `backend/.env`（模板 `backend/.env.example`）。

### 2.3 数据模型

```
users
  id, username (唯一，不区分大小写), password_hash, role ('admin' | 'sub_admin' | 'reader')，
  is_disabled, created_at, last_active_at（登录和会话续期时更新，读者列表显示"最近使用"）

sessions
  id, token_hash (唯一), user_id, created_at, expires_at, last_seen_at

invite_codes
  id, code (唯一), created_at, expires_at, revoked_at,
  used_by_user_id, used_at
  → 状态由字段推导：未使用 / 已使用 / 已过期 / 已作废

books
  id (UUID), title, original_filename, file_size,
  language ('zh' | 'en' | 空), orientation ('portrait' | 'landscape'，拆页完成前为空),
  cover_page_index, page_count,
  spread_start_detected (2 | 3 | 空), spread_start_override (2 | 3 | 空)
    → 实际配对 = override ?? detected ?? 2（D43）
  visibility ('listed' | 'unlisted'),
  processing_status ('processing' | 'ready' | 'failed'), processing_error,
  assets_version（页面图或封面变化时加 1，拼进图片地址使缓存失效）,
  created_at, updated_at

pages
  id, book_id, page_index (从 0 开始), width, height（渲染后的像素尺寸）

jobs
  id, type ('render_pdf'), book_id,
  status ('queued' | 'running' | 'done' | 'failed'),
  progress_done, progress_total, error, attempts,
  created_at, started_at, finished_at

favorites（D55）
  user_id, book_id（联合主键；删除用户或绘本时级联删除）, created_at
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
- **会话**：登录后生成随机令牌，写入 Cookie（`HttpOnly`、`SameSite=Lax`；`Secure` 由环境变量 `COOKIE_SECURE` 控制，默认开启，纯 HTTP 访问时需关闭），数据库只存令牌的哈希。
- **30 天滑动续期**：每次请求检查会话，距上次续期超过 1 天就把过期时间顺延到 30 天后。
- **禁用读者**：立即删除该读者的所有会话，下一次请求即被登出。
- **重置密码**：同样删除该读者的所有会话，所有设备需用新密码重新登录。
- **管理员同步**：启动时以环境变量为准，保证只有一个管理员：没有则创建；用户名或密码变化则更新（密码变化时登出管理员的所有设备）；管理员用户名与已有读者冲突时拒绝启动。
- **防暴力破解**（内存计数，15 分钟窗口）：登录失败每个 IP 20 次、每个用户名 10 次；注册时邀请码错误每个 IP 10 次。超过后返回 429"尝试次数过多，请 N 分钟后再试"。IP 取自 Nginx 的 `X-Forwarded-For`（uvicorn `--proxy-headers`）。
- **登录错误提示**：用户名不存在和密码错误统一提示"用户名或密码错误"，且耗时相同，无法借此判断用户名是否存在。
- **用户名 / 密码规则**：见 [阅读端需求 - 账户](./02-reader.md#账户)（D44）。
- **邀请码格式**：8 位，去掉易混淆字符（0/O、1/I/L），显示为 `K7M3-Q9TX`。注册链接为 `/register?code=K7M3Q9TX`。注册时忽略大小写、空格和 `-`。有效期 1–365 天，默认 7 天。已使用的邀请码不能作废。
- **权限**：三个 FastAPI 依赖：`require_user`（任意已登录、未禁用的用户，管理员也可以用阅读端预览）、`require_staff`（管理员或小小管理员：绘本模块，即 `/admin/books/**` 和绘本 AI 工作台 `/admin/ai/units/**`）和 `require_admin`（仅管理员：邀请码、读者、AI 配置）。角色每次请求都从数据库读取，授予 / 取消小小管理员立即生效（D109）。
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
| GET | `/api/books/{id}` | 绘本信息（含对开配对 `spread_start_page`）+ 页面列表（每页的宽高和图片地址） |
| GET | `/api/books/{id}/cover` | 小封面图片 |
| GET | `/api/books/{id}/pages/{index}` | 页面图片 |
| PUT | `/api/books/{id}/favorite` | 收藏（重复调用无副作用；只能收藏自己能看到的绘本） |
| DELETE | `/api/books/{id}/favorite` | 取消收藏（重复调用无副作用；绘本已下架也可以取消） |

书架列表和绘本详情会带上 `is_favorite`、`favorited_at`（当前用户），以及 `cover_aspect`（封面宽高比，书架在图片加载前就能排好封面框，收藏按钮贴在封面左上角）。搜索在前端按书名筛选，不需要接口。

图片接口先校验登录，再由 FastAPI 返回文件，并带长期缓存头（`Cache-Control: private`）。图片地址带版本参数，更换封面或重新渲染后地址变化，缓存自动失效。

**管理端**（`require_admin` 仅管理员；绘本相关接口是 `require_staff`，见上）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/admin/books` | 上传 PDF（multipart），返回新绘本 |
| GET | `/api/admin/books` | 全部绘本（含下架、处理中、失败） |
| GET | `/api/admin/books/{id}` | 绘本详情 + 处理进度 |
| PATCH | `/api/admin/books/{id}` | 修改书名、语言、版式、封面页、对开配对、上下架（只改请求中出现的字段；语言、对开配对传 null 表示清空） |
| DELETE | `/api/admin/books/{id}` | 删除绘本（数据库记录 + 文件目录） |
| POST | `/api/admin/invites` | 生成邀请码（可指定有效天数，默认 7） |
| GET | `/api/admin/invites` | 邀请码列表 |
| POST | `/api/admin/invites/{id}/revoke` | 作废邀请码 |
| DELETE | `/api/admin/invites/{id}` | 删除邀请码：没被用过的（未使用、已过期、已作废）可以删，已使用的返回 409（D108） |
| GET | `/api/admin/readers` | 读者列表（含小小管理员，带 `role`） |
| PATCH | `/api/admin/readers/{id}` | 禁用 / 启用（`is_disabled`）、授予 / 取消小小管理员（`role`: `sub_admin` / `reader`，D109），字段都可选，至少给一个 |
| POST | `/api/admin/readers/{id}/reset-password` | 管理员设置新密码 |

### 2.7 PDF 上传与拆页流程

```
1. 上传：前端显示上传进度
   后端流式写入磁盘（不把 200MB 读进内存），校验大小 ≤ 200MB、文件头为 %PDF
   → 创建 book（processing）+ 保存 original.pdf + 创建 render_pdf 任务
2. Worker 领取任务：
   用 pypdfium2 打开 PDF（加密或损坏 → 标记 failed，写入中文错误原因）
   低分辨率扫描全书，求所有页面内容的并集，得到统一的裁白边比例（D42）
   逐页渲染：裁掉白边、长边缩放到 2048px → WebP（质量 80）→ 写入 pages/，更新进度
   按多数页面的宽高比判断整本书是横版还是竖版
   比较相邻两页接缝处的像素，检测跨页大图的配对方式（D43）
   用封面页生成小封面 cover.webp
3. 完成：processing_status = ready，visibility = listed（默认上架）
```

- 管理端详情页轮询进度，显示"处理中 12 / 30"。
- 2048px、质量 80 是初始值（`app/books/render.py` 中的常量）。样本书实测：30 页约 11 秒处理完，单页平均 290KB。
- Worker 启动时，把上次中断的 `running` 任务重新放回队列。
- 处理过程中绘本被删除时，Worker 每渲染一页检查一次，发现绘本已删除就终止任务。
- 更换封面时同步重新生成 `cover.webp`。
- 上传大小分两道检查：请求头 `Content-Length` 明显超限时直接返回 413；复制文件时再按实际大小检查。
- 本地开发由 `scripts/dev.sh` 同时启动 Worker（`watchfiles` 监听代码变化自动重启）。

## 3. 前端

### 3.1 应用结构

一个 Vite 应用，两块区域按路由拆分，分别打包、按需加载：

| 路由 | 页面 | 风格 |
| --- | --- | --- |
| `/login`、`/register` | 登录、注册（注册页从 `?code=` 读取邀请码；两页均在已登录时直接跳走） | 小剧场 |
| `/` | 书架（平板横屏 3 列，竖屏和手机 2 列，大屏 4 列） | 小剧场 |
| `/books/:id` | 阅读页 | 小剧场 |
| `/admin/books`、`/admin/books/:id` | 绘本列表、绘本详情与编辑 | shadcn/ui 工具风 |
| `/admin/users`（`/admin/users/invites`、`/admin/users/readers`） | 用户管理：邀请码、读者两个标签（D107）；旧地址 `/admin/invites`、`/admin/readers` 会跳转过来 | shadcn/ui 工具风 |

- **路由守卫**：进入页面前请求 `/api/auth/me`，未登录跳转登录页，读者访问 `/admin` 跳回书架。
- **数据请求**：继续使用现有的 axios 实例，新增 `@tanstack/react-query` 管理缓存、加载状态和进度轮询。
- **小剧场主题**：配色（见 [阅读端需求](./02-reader.md#视觉风格小剧场)）和字体注册为 Tailwind 主题色（`src/index.css` 的 `@theme`，如 `bg-stage-night`、`font-stage-title`），只新增、不修改 shadcn 的全局主题，Admin 端不受影响。
- **字体自托管**：ZCOOL XiaoWei、Noto Sans SC 通过 `@fontsource` 打包进项目（按字符范围拆分，只下载用到的字）；ZCOOL QingKe HuangYou 用于 AI 阶段的"Dance Ready!"招牌，届时再加。不使用 Google Fonts CDN，国内访问更稳定。

### 3.2 仿真翻页

- **采用 StPageFlip（`page-flip`，MIT 许可）的 HTML 模式**，已在桌面浏览器验证并正式接入（`src/pages/stage/flip-book.tsx`）；iPad 真机结论待补充。
- 该库近几年更新不活跃，接入时绕开了它的几处限制（不用 `showCover`、自行控制单页 / 对开、封面左侧放"舞台页"等），细节见 `docs/progress.md` 的"阅读页实现要点"。
- 排版规则按 [阅读端需求](./02-reader.md#横竖版排版) 实现：竖版书横屏对开、封面单独一页，其余情况单页。平板旋转时重新计算排版。
- **预加载**（P1）：只给当前页前后 4 页设置图片地址（兼作预加载），离得远的页释放图片以节省平板内存；封面始终保留。
- **全屏**：使用浏览器全屏 API（iPad Safari 需要带 webkit 前缀）；从主屏幕打开时本身就是全屏，隐藏全屏按钮。

### 3.3 添加到主屏幕（P1）

- `public/manifest.webmanifest`（`display: standalone`、主题色 `#141833`）和 `index.html` 里 iOS 所需的 `apple-mobile-web-app-*` meta、`apple-touch-icon`（D59）。
- 图标在 `public/icons/`，由 `uv run scripts/make-icons.py` 用本机 Chrome 把 SVG 渲染成 PNG；改图案时改脚本里的 SVG 再重新生成。
- iOS 状态栏为 `black-translucent`：页面延伸到状态栏下面。书架、阅读页（按钮、页码、书本留白）和 Admin 顶栏都用 `env(safe-area-inset-*)` 让出安全区；阅读页的书本留白定义在 `src/pages/stage/reader-layout.ts`（`BOOK_PADDING_CSS`），书架"翻开进入阅读"的落点计算也用它。
- 从主屏幕打开时隐藏全屏按钮（`display-mode: standalone` 或 iOS 的 `navigator.standalone`）。
- iOS 上主屏幕 App 与 Safari 的 Cookie 不共享，第一次从主屏幕打开需要重新登录一次。
- 第一期不做离线缓存（不引入 Service Worker）。

## 4. 部署

```
docker compose（仓库根目录 docker-compose.yml；M1 只有 api，worker 在 M2 加入）
├── api      # uvicorn --factory app.main:create_app（单进程），端口只绑定 127.0.0.1:8000
└── worker   # python -m app.worker
共享数据目录：仓库根目录 ./data → 容器内 /data

用户自行配置的 Nginx
├── /       → 前端构建产物 dist/（SPA，未命中的路径回退到 index.html）
└── /api/   → http://127.0.0.1:8000
```

- 域名和 HTTPS 由用户在 Nginx 上自行配置，本项目不处理。
- 项目提供一份 Nginx 配置参考片段，需要注意：
  - `client_max_body_size 210m`，略高于应用层的 200MB，以便由后端返回清晰的中文错误提示；
  - 上传接口适当调大 `proxy_read_timeout` / `proxy_request_buffering`，避免大文件上传超时。
- 如果不配 HTTPS，需设置 `COOKIE_SECURE=false`，否则浏览器不会保存登录 Cookie。
- **备份建议**：每天用 SQLite 的在线备份命令导出一份 `app.db`，连同 `books/` 目录同步到另一个位置（对象存储或另一块磁盘）。原始 PDF 在书在，页面图片可以重新生成。

## 5. 为 AI 阶段预留

第一期不实现，以下内容只为确认现有结构不需要推倒重来。

> **注意**：AI 阶段需求已细化（D61–D75：故事与角色、按开页的生成单元、多角色朗读、朗读与动画相互独立），下面的字段设计已过时，以 [06 AI 阶段技术设计](./06-ai-tech-design.md) 为准。


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
| M4 打磨与上线 | 预加载、添加到主屏幕、Docker Compose 部署、Nginx 参考配置、备份 | 在云服务器上通过用户的 Nginx 访问 |
