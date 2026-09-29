# 技术设计

> 最后更新 2026-09-29 · 这是整个系统的技术设计。AI 相关的服务商对接、数据表、生成流程和接口在 [06 AI 技术设计](./06-ai-tech-design.md)，本文只讲全局架构和非 AI 的部分，并给出 AI 部分的入口。产品规则以 [01–03](./01-product-overview.md) 为准，本文只讲"怎么做"。

## 1. 总体架构

```
平板 / 电脑浏览器
   │
   ▼
（可选）用户自己的 Nginx / 负载均衡：域名、HTTPS
   │
   ▼
web（Docker 里的 Nginx）
   ├── /          → 前端静态文件（Vite 构建产物，React SPA）
   └── /api/*     → api：FastAPI（uvicorn，只在 Docker 内部网络里监听 8000）
                        │
                        ├── SQLite（app.db，WAL 模式）
                        ├── 本地磁盘 DATA_DIR（原始 PDF、页面图片、AI 产物）
                        └── 外部：阿里云百炼、火山引擎（只有 Worker 调用，见 06）
                        ▲
Worker 进程（后台任务）──┘  轮询 jobs 表：PDF 拆页、AI 分析 / 草稿 / 音色 / 朗读 / 动画视频
```

| 组件 | 选择 | 理由 |
| --- | --- | --- |
| 后端框架 | Python + FastAPI | PDF 处理与 AI 生态最成熟（D38）；默认端口 8000，与前端 `/api` 代理一致 |
| 数据库 | SQLite + SQLAlchemy 2.0 + Alembic | 单服务器、小范围使用，无需单独维护数据库服务；Alembic 管理表结构迁移，**API 启动时自动执行 `upgrade head`** |
| 文件存储 | 服务器本地磁盘 | 512GB 足够，见 [01 - 存储](./01-product-overview.md#存储与图片质量) |
| 后台任务 | 独立 Worker 进程 + 数据库任务表 | 拆页、视频下载处理是重活，不能拖慢 API；任务记录在库里，服务重启不丢；不需要引入 Redis |
| 前端托管与反向代理 | Docker 里的 Nginx（`web` 服务） | 一条命令带起整套；域名、HTTPS 仍由用户在前面自己的 Nginx 上配置（D39、D113） |
| 部署 | Docker Compose（`web` / `api` / `worker` 三个服务） | `docker-compose up -d` 一键部署，环境可复现 |

## 2. 后端

### 2.1 目录结构

```
backend/
├── pyproject.toml          # uv 管理依赖（Python 3.13）
├── Dockerfile
├── alembic.ini
├── migrations/             # 数据库迁移（写出后不再修改，补字段就新建一个）
├── app/
│   ├── main.py             # 应用工厂 create_app()：迁移、同步管理员、挂载路由
│   ├── config.py           # 配置（pydantic-settings，读取环境变量 / backend/.env）
│   ├── db.py               # 数据库连接、UTC 时间列类型
│   ├── clock.py            # 统一取当前时间（测试可快进）
│   ├── deps.py             # 公共依赖：DbSession、AppSettings、CurrentUser / CurrentStaff / CurrentAdmin
│   ├── errors.py           # 错误响应统一为 {"detail": "中文提示"}
│   ├── models.py           # 数据表定义
│   ├── auth/               # 登录、注册、会话、密码、限流、管理员同步
│   ├── invites/            # 邀请码
│   ├── readers/            # 读者管理（含授予 / 取消小小管理员）
│   ├── books/              # 绘本：管理端接口 admin_router.py、阅读端接口 router.py、拆页 render.py、文件路径 storage.py
│   ├── ai/                 # AI：服务商目录与配置、适配器 providers/、绘本 AI 工作台接口（见 06）
│   └── worker/             # Worker 主循环 runner.py：拆页、AI 各类任务
├── scripts/                # render_samples.py（拆页参数对比）、ai_trial.py（A0 试验）
└── tests/                  # pytest，按模块分文件；共用夹具在 conftest.py
```

主要依赖：`fastapi`、`uvicorn`、`sqlalchemy`、`alembic`、`pydantic-settings`、`pypdfium2`（PDF 渲染）、`pillow`（WebP 编码、拼图）、`argon2-cffi`（密码哈希）、`python-multipart`（文件上传）、`httpx`（调服务商，不读系统代理）、`av`（PyAV：音频拼接、视频处理）、`numpy`。开发工具：`ruff`、`pytest`。

### 2.2 配置（环境变量）

| 变量 | 说明 |
| --- | --- |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 管理员账号密码（最少 6 位）。启动时同步到 users 表（不存在则创建，密码变化则更新） |
| `DATA_DIR` | 数据目录，存放 `app.db` 和所有绘本文件 |
| `MAX_UPLOAD_MB` | 上传上限，默认 200 |
| `COOKIE_SECURE` | 会话 Cookie 是否带 `Secure`，默认 `true`；未配置 HTTPS 时设为 `false` |
| `DASHSCOPE_API_KEY`、`VOLCENGINE_ARK_API_KEY`、`VOLCENGINE_SPEECH_API_KEY` | AI 服务商凭据（D82），见 [06 第 3 节](./06-ai-tech-design.md#3-ai-配置)；不用的服务商可以留空 |
| `WEB_PORT`、`WEB_BIND`、`DATA_PATH` | 仅 Docker Compose 使用：网站对外端口（默认 8080）、监听的网卡（默认 `0.0.0.0`；前面有自己的 Nginx 时设 `127.0.0.1`）、数据目录在宿主机上的位置（默认 `./data`），见第 4 节 |

部署时写在仓库根目录的 `.env`（模板 `.env.example`），本地开发写在 `backend/.env`（模板 `backend/.env.example`）。

### 2.3 数据模型

```
users
  id, username (唯一，不区分大小写), password_hash,
  role ('admin' | 'sub_admin' | 'reader')，
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
  + AI 字段（故事、朗读顺序、Voice / Dance Ready 确认时间、封面动画），见 06 第 4 节

pages
  id, book_id, page_index (从 0 开始), width, height（渲染后的像素尺寸）

favorites（D55）
  user_id, book_id（联合主键；删除用户或绘本时级联删除）, created_at

jobs
  id, type, book_id, unit_id, character_id（可空）,
  status ('queued' | 'running' | 'waiting' | 'done' | 'failed'),
  progress_done, progress_total, error, attempts, payload（JSON）,
  remote_task_id, next_poll_at（视频任务"提交后等待查询"用）,
  created_at, started_at, finished_at
  type：'render_pdf' | 'ai_analyze_book' | 'ai_draft_unit' | 'ai_voice' | 'ai_tts_unit'
        | 'ai_cover_video' | 'ai_video_unit'

AI 专用的表（都在 06 第 4 节）：ai_capabilities、ai_capability_configs、characters、character_voices、ai_units
```

- 阅读端书架只返回 `visibility = listed` 且 `processing_status = ready` 的绘本；管理员和小小管理员可以在阅读端预览下架的绘本。
- 页面文件路径由 `book_id + page_index` 推导，不存进数据库；所有路径的拼接都在 `app/books/storage.py`。
- 所有时间都经 `app.clock.utcnow()` 取得、以 UTC 存储（`UTCDateTime` 列类型）；测试用 `clock.offset` 快进。

### 2.4 文件存储布局

```
DATA_DIR/
├── app.db
└── books/{book_id}/
    ├── original.pdf           # 保留原始文件，便于重新渲染
    ├── pages/0000.webp        # 页面大图（长边 2048px）
    ├── pages/0001.webp
    ├── cover.webp             # 书架用的小封面（长边 480px）
    └── ai/                    # AI 产物：audio/、video/、voices/（见 06 第 5 节）
```

书架只加载小封面，打开绘本后才加载页面大图。

### 2.5 账户、会话与权限

- **密码**：argon2id 哈希存储。
- **会话**：登录后生成随机令牌，写入 Cookie（`HttpOnly`、`SameSite=Lax`；`Secure` 由 `COOKIE_SECURE` 控制，默认开启，纯 HTTP 访问时需关闭），数据库只存令牌的哈希。
- **30 天滑动续期**：每次请求检查会话，距上次续期超过 1 天就把过期时间顺延到 30 天后。
- **禁用读者**：立即删除该读者的所有会话，下一次请求即被登出。
- **重置密码**：同样删除该读者的所有会话，所有设备需用新密码重新登录。
- **管理员同步**：启动时以环境变量为准，保证只有一个 `admin` 角色的账号：没有则创建；用户名或密码变化则更新（密码变化时登出管理员的所有设备）；管理员用户名与已有读者冲突时拒绝启动。
- **防暴力破解**（内存计数，15 分钟窗口）：登录失败每个 IP 20 次、每个用户名 10 次；注册时邀请码错误每个 IP 10 次。超过后返回 429"尝试次数过多，请 N 分钟后再试"。IP 取自 Nginx 的 `X-Forwarded-For`（uvicorn `--proxy-headers`）。
- **登录错误提示**：用户名不存在和密码错误统一提示"用户名或密码错误"，且耗时相同，无法借此判断用户名是否存在。
- **用户名 / 密码规则**：见 [02 - 账户](./02-reader.md#账户)（D44）。
- **邀请码格式**：8 位，去掉易混淆字符（0/O、1/I/L），显示为 `K7M3-Q9TX`。注册链接为 `/register?code=K7M3Q9TX`。注册时忽略大小写、空格和 `-`。有效期 1–365 天，默认 7 天。已使用的邀请码不能作废、不能删除。
- **角色与依赖**（D109）：三种角色对应三个 FastAPI 依赖：
  - `require_user`（`CurrentUser`）：任意已登录、未禁用的用户；
  - `require_staff`（`CurrentStaff`）：`admin` 或 `sub_admin`（小小管理员）——绘本模块，即 `/admin/books/**` 和绘本 AI 工作台 `/admin/ai/units/**`；
  - `require_admin`（`CurrentAdmin`）：仅 `admin`——邀请码、读者、AI 配置。

  角色每次请求都从数据库读取，授予 / 取消小小管理员立即生效，不需要对方重新登录。
- **CSRF**：`SameSite=Lax` Cookie，加上非上传接口只接受 JSON 请求体，足以覆盖本项目场景。

### 2.6 API 概览

所有接口以 `/api` 开头，错误统一为 `{"detail": "<中文提示>"}`。

**账户**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/logout` | 退出 |
| POST | `/api/auth/register` | 邀请码 + 用户名 + 密码注册，成功后直接登录 |
| GET | `/api/auth/me` | 当前用户，含 `role`（前端路由守卫用） |

**阅读端**（`require_user`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/books` | 书架列表，按上传时间倒序 |
| GET | `/api/books/{id}` | 绘本信息（含对开配对 `spread_start_page`）+ 页面列表 + AI 产物（`read_order`、`units`，见 06 第 7 节） |
| GET | `/api/books/{id}/cover` | 小封面图片 |
| GET | `/api/books/{id}/pages/{index}` | 页面图片 |
| PUT / DELETE | `/api/books/{id}/favorite` | 收藏 / 取消收藏（重复调用无副作用；只能收藏自己能看到的绘本；已下架的可以取消） |
| GET | `/api/books/{id}/cover-video`、`/ai/audio/{uid}`、`/ai/video/{uid}` | 封面动画、单元朗读、单元动画（见 06 第 7 节） |

书架列表和绘本详情会带上 `is_favorite`、`favorited_at`（当前用户）、`cover_aspect`（封面宽高比，书架在图片加载前就能排好封面框）、`voice_ready`、`dance_ready`、`cover_video_url`。搜索在前端按书名筛选，不需要接口。

图片、音频、视频接口都先校验登录再返回文件，带长期缓存头（`Cache-Control: private`）和版本参数（更换封面、重新渲染、重新生成后地址变化，缓存自动失效）；视频、音频用 `FileResponse`，支持 iPad Safari 需要的分段请求（Range）。

**管理端**

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/admin/books` | staff | 上传 PDF（multipart），返回新绘本 |
| GET | `/api/admin/books` | staff | 全部绘本（含下架、处理中、失败） |
| GET / PATCH / DELETE | `/api/admin/books/{id}` | staff | 详情 + 处理进度；修改书名、语言、版式、封面页、对开配对、上下架（只改请求中出现的字段；语言、对开配对传 null 表示清空）；删除（数据库记录 + 文件目录） |
| `*` | `/api/admin/books/{id}/ai/**`、`/api/admin/ai/units/**` | staff | 绘本 AI 工作台（06 第 7 节） |
| GET / PUT / POST | `/api/admin/ai/settings`、`/api/admin/ai/capabilities/**` | admin | AI 配置（06 第 7 节） |
| POST / GET | `/api/admin/invites` | admin | 生成邀请码（可指定有效天数，默认 7）/ 列表 |
| POST | `/api/admin/invites/{id}/revoke` | admin | 作废邀请码 |
| DELETE | `/api/admin/invites/{id}` | admin | 删除邀请码：没被用过的（未使用、已过期、已作废）可以删，已使用的返回 409（D108） |
| GET | `/api/admin/readers` | admin | 读者列表（含小小管理员，带 `role`） |
| PATCH | `/api/admin/readers/{id}` | admin | 禁用 / 启用（`is_disabled`）、授予 / 取消小小管理员（`role`: `sub_admin` / `reader`，D109），字段都可选，至少给一个；管理员账号本身不在这里管理 |
| POST | `/api/admin/readers/{id}/reset-password` | admin | 管理员设置新密码 |

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
- 2048px、质量 80 是初始值（`app/books/render.py` 中的常量）。样本书实测：30 页约 11 秒处理完，单页平均 290KB；裁掉底部 20.2% 空白后页面为 1815×2048。
- 处理过程中绘本被删除时，Worker 每渲染一页检查一次，发现绘本已删除就终止任务。
- 更换封面时同步重新生成 `cover.webp`。
- 上传大小分两道检查：请求头 `Content-Length` 明显超限时直接返回 413；复制文件时再按实际大小检查。

### 2.8 Worker

- `python -m app.worker`；一次只做一个任务，按 `jobs` 表里的类型分发：PDF 拆页、AI 整本分析、单元草稿、音色、朗读、封面视频、开页视频。API 处理函数**只入队、不做重活**，外部 AI 调用只在 Worker 里发生。
- 启动时把上次中断的 `running` 任务重新放回队列；已提交给服务商的视频任务改为 `waiting`、继续查询，**不重新提交**（避免重复付费）。
- 视频任务拆成"提交"和"查询"两步，`waiting` 期间不占用 Worker，每 15 秒查询一次，服务商那边最多同时 3 个，30 分钟没好算超时；细节见 [06 第 6.7 节](./06-ai-tech-design.md#67-worker-调度)。
- **失败不自动重试**（D65）：出错即标记失败并记录中文原因，管理员点"重试"重新入队。
- 只有 API 进程执行数据库迁移，Worker 启动时等待迁移完成。

## 3. 前端

Vite + React 19 + TypeScript + Tailwind v4 + shadcn/ui（`base-nova` 风格，建在 Base UI 上，不是 Radix）+ `@tanstack/react-query` + `react-router` 8 + `motion`。

### 3.1 应用结构

一个 Vite 应用，两块区域按路由拆分，分别打包、按需加载（读者不会加载管理后台的代码）：

| 路由 | 页面 | 守卫 | 风格 |
| --- | --- | --- | --- |
| `/login`、`/register` | 登录、注册（注册页从 `?code=` 读取邀请码；已登录时直接跳走） | `redirectIfLoggedIn` | 小剧场 |
| `/` | 书架 | `requireUser` | 小剧场 |
| `/favorites` | 我的收藏（与书架同一个页面） | `requireUser` | 小剧场 |
| `/books/:id` | 阅读页 | `requireUser` | 小剧场 |
| `/admin/books`、`/admin/books/:id` | 绘本列表、绘本详情（含 AI 工作台） | `requireStaff` | shadcn/ui 工具风 |
| `/admin/users/invites`、`/admin/users/readers` | 用户管理的两个标签（D107；`/admin/users` 跳到邀请码；旧地址 `/admin/invites`、`/admin/readers` 会跳转过来） | `requireAdmin` | 同上 |
| `/admin/ai` | AI 配置 | `requireAdmin` | 同上 |

- **路由守卫**（`src/router/guards.ts`）：进入页面前请求 `/api/auth/me`。未登录跳登录页；`requireStaff` 放行管理员和小小管理员，读者访问 `/admin` 回到书架；`requireAdmin` 只放行管理员，小小管理员访问时回到"绘本"。前端只是体验层，真正的权限在服务端。
- **角色工具**：`src/lib/roles.ts`（`isStaff`、`isFullAdmin`、`ROLE_LABELS`）。
- **数据层**：每类资源一个 `src/api/*.ts`（react-query hooks），类型统一在 `src/api/types.ts`；共享的 `queryClient` 在 `src/lib/query-client.ts`（已登录的会话遇到 401 时跳回登录页）；报错提示用 `getErrorMessage()`，通知用 `toast.add()`。
- **页面 UI 一律用 `src/components/ui/` 里的 shadcn 组件**，不手写等价物；阅读端的小剧场外观只是套在它们上面的 class。管理后台的模块和表格行用 `src/pages/admin/motion.tsx` 的入场动画助手（`Reveal`、`AnimatedTableRow`、`RevealItem`，D86）。
- **小剧场主题**：配色和字体注册为 Tailwind 主题色（`src/index.css` 的 `@theme`，如 `bg-stage-night`、`font-stage-title`），只新增、不修改 shadcn 的全局主题，管理后台不受影响。
- **字体自托管**：ZCOOL XiaoWei、Noto Sans SC、ZCOOL QingKe HuangYou（只加载拉丁字符，用于"Dance Ready!"招牌）通过 `@fontsource` 打包，不使用 Google Fonts CDN，国内访问更稳定。
- **手绘图标**：读者端的按钮和标记用 SVG 手绘（`src/pages/stage/doodle-*.tsx`：爱心、翻页箭头、小喇叭、音符、动效星星、主题图标、头像 / 齿轮 / 门），统一"贴纸白边 + 蜡笔填充 + 两遍墨线"的画法。管理后台用 lucide 线条图标。

### 3.2 仿真翻页

采用 `page-flip`（StPageFlip，MIT 许可）的 **HTML 模式**，在 `src/pages/stage/flip-book.tsx` 里以命令式方式封装。桌面浏览器已验证；iPad 真机待测（见 [04 路线图](./04-roadmap.md)）。该库近几年更新不活跃，接入时绕开了它的几处限制，**改这个组件之前要先读下面的要点**：

- 用 HTML 模式（canvas 模式不处理 devicePixelRatio，在 iPad 高清屏上会发虚）。
- 单页 / 对开由我们自己决定（竖版书且横屏 → 对开）：设 `minWidth = maxWidth = 页宽`，根元素宽度为 1 倍或 2 倍页宽。排版规则见 [02 - 横竖版排版](./02-reader.md#横竖版排版)。
- 库会把根元素宽度改成 `100%`，所以外面要套一层定宽容器；库的 `destroy()` 会把根元素一起删掉，因此**根元素由代码动态创建，不交给 React 管理**；排版变化（旋转屏幕等）时销毁重建，并保持当前页。
- 库绘制时会用 `style.cssText` 覆盖页面元素自身的内联样式，底色等样式要放在内层子元素上。
- **不用 `showCover`**：它会把封面设成硬页（整张翻转、没有卷页），而且往回翻到封面时左侧会残留当前左页。改为对开时在封面左边放一张"舞台页"（内层是与舞台背景对齐的背景），按 (0,1)(2,3)… 配对；`spread_start_page = 3` 时在封面后插入空白页；`loadFromHTML` 之后对所有页调用 `getPage(i).setDensity("soft")`。
- 合上书本用 `pageFlip.flip(封面位置)`：无论隔多少页都只播放一次翻页动画。
- **图片预加载**：只给当前页前后 4 页设置地址（兼作预加载），其余页释放以节省平板内存；封面始终保留（合书时要用）。
- **对外接口**：`onVisibleChange(pages, slots)`——`slots` 按位置给页码（单页 1 项，对开 [左, 右]，舞台页 / 空白页为 null）；`onFlippingChange`——拖动或翻页动画中为 true；`overlay`——叠在书上方、与书同尺寸的 React 层。小喇叭（`read-aloud.tsx`）、封面动画和开页动画（`page-videos.tsx`）都通过它绘制。对开时起始位置要对齐到偶数（左页），否则左右会算反。
- **全屏**：浏览器全屏 API（iPad Safari 需要 webkit 前缀，`use-fullscreen.ts`）；从主屏幕打开时本身就是全屏，隐藏全屏按钮。

### 3.3 阅读端的组成

`src/pages/stage/` 下：

| 模块 | 文件 |
| --- | --- |
| 书架 | `shelf.tsx`（页面、分页、一屏排版）、`shelf-item.tsx`（一本书）、`shelf-search.tsx`、`shelf-themes.ts`（四套主题）、`shelf-backdrop.tsx`（背景装饰）、`shelf-motion.ts`（进场、点按、萤火虫、动效开关）、`book-opening.ts`（封面飞入阅读页的过渡层） |
| 书架顶栏 | 主题按钮 `ThemeButton`、动效按钮 `MotionButton`、收藏 `FavoritesButton`（都在 `shelf.tsx`）、头像和账户弹窗 `account-dialog.tsx` |
| 阅读页 | `reader.tsx`、`flip-book.tsx`、`reader-layout.ts`（书与安全区的排版计算，书架"翻开进入"的落点也用它） |
| 朗读 | `story-audio.ts`（Web Audio 单例播放器）、`use-read-aloud.ts`（自动朗读逻辑）、`read-aloud.tsx`（小喇叭、自动朗读开关） |
| 动画 | `loop-video.tsx`（叠在静态画面上的循环视频：封面动画、开页动画共用）、`page-videos.tsx`（阅读页开页动画）、`dance-ready-sign.tsx`（书架招牌） |
| 公共 | `common.tsx`（小剧场配色、`StageBrand`、`StageRoundButton`、登录 / 注册外框） |

- **书架**一屏显示、不出现滚动条：每页 8 本，排法随屏幕方向变化；横屏时按封面宽高比估算行高，书名按一行估算。这套估算在 `shelf.tsx` 的 `useLandscapeRows`。
- **动效**：`motion` 库负责书架翻页滑动、管理后台入场；系统开启"减少动态效果"时统一关闭或退化为淡入。

### 3.4 管理后台的组成

`src/pages/admin/` 下：`layout.tsx`（顶栏：品牌胶囊、按角色过滤的导航、读者首页入口、头像菜单；`PageHeader`）、`books.tsx` / `book-detail.tsx` / `book-actions.tsx` / `book-status.tsx`（绘本）、`ai-workbench.tsx`（绘本详情页的 AI 工作台，见 [06 第 8.1 节](./06-ai-tech-design.md#81-后台绘本详情页的页面模块)）、`video-options.tsx`（生成动画时临时选时长和清晰度）、`users.tsx`（用户管理标签）、`invites.tsx`、`readers.tsx`、`ai-settings.tsx`、`query-state.tsx`、`motion.tsx`。

### 3.5 添加到主屏幕

- `public/manifest.webmanifest`（`display: standalone`、主题色 `#141833`）和 `index.html` 里 iOS 所需的 `apple-mobile-web-app-*` meta、`apple-touch-icon`（D59）。
- 图标在 `public/icons/`，由 `uv run scripts/make-icons.py` 用本机 Chrome 把 SVG 渲染成 PNG；改图案时改脚本里的 SVG 再重新生成。
- iOS 状态栏为 `black`（D124）：不透明的黑色状态栏，页面排在它下面（原来的 `black-translucent` 会让 iOS 26 的网页视图矮一截，底部露白条，见 D123）。书架、阅读页（按钮、页码、书本留白）和管理后台顶栏仍用 `env(safe-area-inset-*)` 让出安全区（此时顶部为 0，底部横条仍有）；阅读页的书本留白定义在 `reader-layout.ts`（`BOOK_PADDING_CSS`）。
- 从主屏幕打开时隐藏全屏按钮（`display-mode: standalone` 或 iOS 的 `navigator.standalone`）。
- iOS 上主屏幕 App 与 Safari 的 Cookie 不共享，第一次从主屏幕打开需要重新登录一次。
- 不做离线缓存（不引入 Service Worker）。

## 4. 部署

一条命令部署（D113）：

```bash
cp .env.example .env    # 填好管理员账号密码、AI Key；没有 HTTPS 时把 COOKIE_SECURE 设为 false
docker-compose up -d    # 新版 Docker 也可以写 docker compose up -d；第一次会构建镜像，需要几分钟
# 然后访问 http://服务器:8080
```

```
docker compose（仓库根目录 docker-compose.yml）
├── web      # Dockerfile.web：node:24 构建前端 → nginx:stable-alpine 托管，并把 /api/ 转发给 api；对外发布 WEB_PORT
├── api      # backend/Dockerfile：uvicorn --factory app.main:create_app（单进程）；不对外发布端口；启动时自动迁移数据库
└── worker   # 同一个镜像，命令 python -m app.worker；等 api 健康后才启动

数据：宿主机的 DATA_PATH（默认 ./data）→ 容器内 /data，api 和 worker 共用
```

- **镜像版本**：Node 24（当前 LTS）、Python 3.14（Python 没有 LTS，用最新稳定版；后端测试在 3.14 上全部通过，开发环境的 `.python-version` 仍是 3.13，`requires-python` 是 `>=3.13`，两者都受支持）、Nginx `stable` 分支、uv 固定小版本。后端 Dockerfile 是多阶段构建，最终镜像不带 uv 和下载缓存。
- **启动顺序**：api 通过健康检查（数据库迁移完成、开始提供服务）之后，worker 和 web 才启动；api 重启后 web 的 Nginx 会通过 Docker DNS 自动找到新地址，不需要重启 web。
- **内存上限（D114）**：三个容器都设了 `mem_limit`（同值的 `memswap_limit`，即不许用 swap）：api 768m、worker 2g、web 256m，`.env` 里的 `API_MEM_LIMIT` / `WORKER_MEM_LIMIT` / `WEB_MEM_LIMIT` 可调。目的是哪个容器失控只会被系统杀掉、由 `restart: unless-stopped` 拉起，不会把 2 核 4G 的服务器拖到卡死。worker 被杀时正在跑的 PDF 拆页任务会重试一次；再被杀就标记失败，提示"处理时服务器内存不足…请压缩 PDF 后重新上传"（`runner.recover()`）。拆页本身内存不随页数增长（一次只渲染一页，跨页检测只保留每页两条 3 像素宽的边缘，见 `render.py`），峰值取决于单页内嵌图片的大小。
- **CPU 上限（D115）**：worker 还限制了 `cpus`（默认 1.0，`.env` 的 `WORKER_CPUS` 可调）和较低的 `cpu_shares`，PDF 拆页再吃 CPU 也留得出一个核给 SSH 和网站；代价是拆页会慢一些。
- **非 root 运行**：api / worker 进程以普通用户运行。入口脚本 `backend/docker-entrypoint.sh` 以 root 启动，把挂载进来的数据目录交给该用户后再降权，所以宿主机上的 `./data`（Docker 第一次会以 root 身份创建）不用手动 `chown`。
- **Nginx 配置**在 `deploy/nginx.conf`：单页应用回退到 `index.html`；`/assets/`（带哈希的构建产物）缓存一年、`index.html` 不缓存；`client_max_body_size 210m`（略高于应用层的 200MB，由后端返回清晰的中文错误提示）；上传接口不在 Nginx 里整个缓存请求体、超时放宽到 600 秒；视频、音频的 Range 请求原样透传；`.webmanifest` 的 MIME 类型。
- **真实客户端 IP**（登录、注册限流按 IP 计数）：`web` 只信任私有地址段发来的 `X-Forwarded-For`，从公网直接连进来的请求自带的 `X-Forwarded-For` 一律忽略，防止伪造 IP 绕过限流；前面有自己的 Nginx 时，让它带上 `X-Forwarded-For` 即可。
- **前面有自己的 Nginx（域名、HTTPS）时**：`.env` 里设 `WEB_BIND=127.0.0.1`，让你的 Nginx 把整个站点转发到 `http://127.0.0.1:8080`（不需要再单独配置 `/api` 和静态文件），并带上 `X-Forwarded-For`。
- 如果不配 HTTPS，需设置 `COOKIE_SECURE=false`，否则浏览器不会保存登录 Cookie。
- **更新版本**：`git pull && docker-compose up -d --build`。数据库迁移在 api 启动时自动执行。
- **备份建议**：每天用 SQLite 的在线备份命令导出一份 `app.db`，连同 `books/` 目录同步到另一个位置（对象存储或另一块磁盘）；直接备份整个 `DATA_PATH` 目录也可以。原始 PDF 在书在，页面图片可以重新生成；AI 产物（朗读、动画）重新生成要花钱，值得一起备份。

## 5. 开发与测试

```bash
scripts/dev.sh                    # 本地一键启动：API + Worker（改代码自动重启）+ Vite；--lan 让局域网设备（iPad）访问
                                  # 缺 backend/.env 时从模板创建；8000 被占用时自动换端口并让前端代理跟着切换

npm run build                     # tsc -b（类型检查）+ vite build，是唯一的类型检查步骤
npm run lint                      # oxlint

cd backend && uv run pytest       # 后端测试（TestClient + 临时 DATA_DIR）
uv run ruff check . && uv run ruff format .
uv run alembic revision --autogenerate -m "..."   # 改了 app/models.py 之后
```

- **后端测试**：不调用真实服务商，用 `monkeypatch` 替换 `providers.http_client`（`httpx.MockTransport`）；共用夹具在 `tests/conftest.py`（`admin`、`reader`、`worker`、`ready_book`、`advance` 等）。
- **前端没有测试框架**：改动靠 `npm run build` 类型检查、`npm run lint`，以及浏览器里的端到端验证。端到端验证用**独立的第二套环境**（独立端口、临时数据目录、独立 Vite 缓存、无效的 AI Key），不碰开发中的 `backend/data`；做法见 [progress.md 的操作注意事项](./progress.md#给-claude-的操作注意事项)。
- **迁移规则**：迁移一旦写出就不再修改（开发服务器会在代码变化时自动执行迁移，改已执行过的迁移不会再生效），补字段就新建一个迁移。

## 6. 风险与技术验证

| 风险 | 状态 / 应对 |
| --- | --- |
| StPageFlip 在 iPad Safari 上的效果、性能不达标，或无法强制横版书单页显示 | 桌面浏览器已验证；**iPad 真机待测**。不达标则换用其他库或自研 CSS 3D 翻页 |
| 扫描版 PDF 体积大、页数多，拆页耗时长 | 逐页渲染、实时显示进度；Worker 独立进程，不影响其他操作 |
| SQLite 并发写入 | 开启 WAL 模式；只有一个 Worker 进程，写入冲突极少 |
| 国内访问外部资源不稳定 | 字体和前端依赖全部打包自托管，不依赖外部 CDN；AI 请求不走系统代理，国内服务直连（D81） |
| iPad 上 Web Audio 自动朗读解锁、静音视频自动播放、多个视频同时播放的内存占用 | 已按 Safari 的限制设计（用户点击时解锁），**待真机验证**；AI 部分的风险与实测结论见 06 第 9 节 |
