# 项目进度与断点

> 最后更新：2026-09-28
>
> **给 Claude**：用户说"继续我们的任务"时，先读完本文件，再按"下次开始时"一节执行。每次工作结束前更新本文件。

## 当前位置

```
[✅] 产品需求讨论（第一期）  →  docs/01–04 已确认
[✅] 技术设计               →  docs/05-tech-design.md 已确认（部署改为用户自配 Nginx，D39）
[🟡] M0 仿真翻页技术验证      →  桌面浏览器验证通过；等待 iPad 真机实测（现在直接测正式阅读页）
[✅] M1 后端骨架与账户
[✅] M2 上传与拆页          →  后端 + 登录页 + Admin 前端（绘本 / 邀请码 / 读者）
[✅] M3 阅读端              →  注册页、小剧场书架、阅读页（对开 / 单页、跨页配对、读完合书、全屏）；桌面浏览器模拟 iPad / 手机验证通过
[🟡] M4 打磨与上线           →  添加到主屏幕已完成；待做 Nginx 参考配置、部署说明、备份
[✅] AI 阶段需求讨论         →  需求已确认（D61–D85），技术设计 `06-ai-tech-design.md` 已确认
[✅] AI A1 AI 配置             →  服务商 Key 写在 .env（D82）；后台"AI 配置"页查看 Key 是否已设置、每种能力选服务商 / 模型、测试连接
[ ] AI A0 试验                →  等用户在 .env 里填好两家的 Key
```

## 断点：等待用户的事项

| # | 事项 | 何时需要 | 状态 |
| --- | --- | --- | --- |
| 1 | 在 iPad 上实测阅读页，按下方"iPad 验证清单"反馈结果 | 上线之前 | 待测试 |
| 2 | 再提供 1–2 本 PDF，**至少一本横版**，放到 `samples/`（目前只有一本竖版：《波西和皮普 大怪兽》；横版目前只用生成的测试 PDF 验证过） | 上线之前 | 待提供 |
| 3 | 在 `backend/.env`（本地）或部署目录的 `.env` 里填写 `DASHSCOPE_API_KEY`、`VOLCENGINE_ARK_API_KEY`、`VOLCENGINE_SPEECH_API_KEY`，重启后在后台"AI 配置"页各点一次"测试连接" | AI 试验（A0）之前 | 待填写 |

## 下次开始时（Claude 执行步骤）

1. 读 `docs/README.md` 和本文件。
2. 向用户简要汇报当前位置，确认两个断点：
   - iPad 实测结果如何？有问题先修；全部通过后把 M0 结论写入 `05-tech-design.md` 第 3.2 节，并在 `decision-log.md` 记录（下一个编号 **D86**）。不达标时给出 2–3 个替代方案（其他库 / 自研 CSS 3D 翻页）并附推荐。
   - `ls samples/` 检查是否有新 PDF；有则在 Admin 上传，重点看横版书和跨页检测结果。
3. 进入 **M4 打磨与上线**（见 05 第 4 节、第 7 节）：
   - ~~添加到主屏幕~~（已完成，D59）；
   - Nginx 参考配置（`.webmanifest` 需要 `application/manifest+json` 类型，较旧的 Nginx `mime.types` 里没有；`client_max_body_size 210m`、上传超时、SPA 回退到 `index.html`、`/api/` 转发）；
   - 部署说明（README）：`.env`、`docker compose up -d --build`、前端 `npm run build` 后把 `dist/` 交给 Nginx、`COOKIE_SECURE`；
   - 备份：SQLite 在线备份命令 + `books/` 目录同步的脚本或说明；
   - 视情况：Admin 页面预览用的缩略图（现在直接加载 2048px 大图）、Docker 镜像瘦身（多阶段构建）。

## 阅读页实现要点（M0 验证得出，已用于 `src/pages/stage/flip-book.tsx`）

- 用 `page-flip` 的 HTML 模式（canvas 模式不处理 devicePixelRatio，在 iPad 高清屏上会发虚）。
- 单页 / 对开由我们自己决定（竖版书且横屏 → 对开）：设 `minWidth = maxWidth = 页宽`，根元素宽度为 1 倍或 2 倍页宽。
- 库会把根元素宽度改成 `100%`，所以外面要套一层定宽容器；库的 `destroy()` 会把根元素一起删掉，因此根元素由代码动态创建，不交给 React 管理；排版变化（旋转屏幕等）时销毁重建，并保持当前页。
- 库绘制时会用 `style.cssText` 覆盖页面元素自身的内联样式，底色等样式要放在内层子元素上。
- **不用 `showCover`**：它会把封面设成硬页（整张翻转、没有卷页），而且往回翻到封面时左侧会残留当前左页。改为对开时在封面左边放一张"舞台页"（内层是与舞台背景对齐的背景），按 (0,1)(2,3)… 配对；`spread_start_page = 3` 时在封面后插入空白页；`loadFromHTML` 之后对所有页调用 `getPage(i).setDensity("soft")`。
- 合上书本用 `pageFlip.flip(封面位置)`：无论隔多少页都只播放一次翻页动画。
- 图片只给当前页前后 4 页设置地址（兼作预加载），其余页释放以节省内存；封面始终保留（合书时要用）。
- 样本实测（《波西和皮普 大怪兽》，30 页，PDF 7.6MB）：裁掉底部 20.2% 空白后页面为 1815×2048，单页平均 290KB，处理约 11 秒。

### iPad 实测方法

1. 电脑上运行 `scripts/dev.sh --lan`，iPad 与电脑连同一个 Wi-Fi。
2. 电脑上登录 `http://localhost:5173/login`（管理员账号密码见 `backend/.env`），在"绘本"里上传样本 PDF；在"邀请码"里生成邀请码。
3. iPad Safari 打开 `[web]` 日志里 Network 一行的地址，用注册链接注册读者（或直接用管理员账号登录），打开绘本。

### iPad 验证清单

- [ ] 卷页效果流畅、手势跟手
- [ ] 30 页的绘本来回快速翻页不卡顿、不崩溃
- [ ] 竖版书横屏对开、封面单独一页，跨页大图拼接正确
- [ ] 竖版书竖屏单页；横版书始终单页（需要横版样本）
- [ ] 平板横竖屏切换后排版正确，且停留在同一页
- [ ] 全屏按钮可用
- [ ] 翻到最后一页出现"故事讲完啦！"提示，点"合上书本"后动画回到封面
- [ ] 书架、登录、注册页在 iPad 上显示正常，字体（站酷小薇）加载正常
- [ ] Safari"分享 → 添加到主屏幕"后图标、名称正确；从主屏幕打开没有地址栏，夜幕背景铺到状态栏下，按钮不被状态栏和底部横条遮挡，没有全屏按钮

## 协作约定

- **语言**：与用户用中文交流，文档用中文。
- **角色**：Claude 以产品经理 + 技术负责人的身份推进，每轮给出**带推荐方案的问题**（表格形式），用户常以"都同意"一次确认。
- **文档规则**：
  - 只把**已确认**的内容写入 `docs/01–05`；未确认的放 [open-questions.md](./open-questions.md)。
  - 每个决策追加到 [decision-log.md](./decision-log.md)，编号连续（当前最后一条是 **D85**）。
  - 每次工作结束前更新本文件的"当前位置""断点""下次开始时"。
- **视觉风格**：阅读端为"B 小剧场"。示意图的本地副本在 [design/reader-style-options.html](./design/reader-style-options.html)，在线版在 https://claude.ai/artifact/3TwChZ4w49eXKvKkSMSW1z（需要登录用户本人的 claude.ai 账号）。

## 代码现状

- **前端**（`src/`）：
  - 阅读端（小剧场风格）：登录 `/login`、注册 `/register?code=`、书架 `/`、阅读页 `/books/:id`（`src/pages/stage/`、`src/pages/login.tsx`、`src/pages/register.tsx`）；主题色和字体在 `src/index.css` 的 `@theme`（`bg-stage-*`、`font-stage-title`）。
  - 管理后台（shadcn/ui 工具风）：`/admin/books`、`/admin/books/:id`、`/admin/invites`、`/admin/readers`（`src/pages/admin/`）。
  - 数据请求：`src/api/*.ts`（react-query hooks + 接口类型 `src/api/types.ts`）；路由守卫 `src/router/guards.ts`；会话过期统一跳回登录页（`src/lib/query-client.ts`）。
- **后端**（`backend/app/`）：账户、邀请码、读者、绘本上传与接口；Worker 拆页（`app/worker/`、`app/books/render.py`）；AI 配置（`app/ai/`）；96 个 pytest 测试。
  - 本地运行：仓库根目录执行 `scripts/dev.sh`（API + Worker + Vite 一起启动，Ctrl+C 一起停止；`--lan` 让 iPad 等局域网设备可访问）。首次运行会自动创建 `backend/.env`、安装依赖。
  - 测试与检查：`cd backend && uv run pytest`、`uv run ruff check . && uv run ruff format .`；前端 `npm run build`、`npm run lint`。
  - 新增数据表：改 `app/models.py` 后运行 `uv run alembic revision --autogenerate -m "说明"`，检查生成的迁移文件。
  - `backend/scripts/render_samples.py`：把 `samples/*.pdf` 渲染到 `samples/rendered/`，用于调整拆页参数（长边、质量）时对比效果。
  - **注意**：用户这台电脑的 8000 端口常被另一个项目（constellation）占用；`scripts/dev.sh` 会自动改用下一个空闲端口。Claude 做端到端测试时要用独立端口、临时 `DATA_DIR` 和独立的 Vite 缓存目录（如 `DATA_DIR=<临时目录>/data VITE_CACHE_DIR=<临时目录>/vite BACKEND_PORT=8010 FRONTEND_PORT=5180 scripts/dev.sh`），不要碰用户正在运行的开发环境、`backend/data` 和 `node_modules/.vite`（共用 Vite 缓存曾导致用户页面加载到两份 React 而报错）。
- **部署**：仓库根目录 `docker-compose.yml`（api + worker）+ `.env.example`；api 已实际构建并启动验证过。数据在仓库根目录 `./data`。
- **仓库**：git 仓库，远程为 `github.com/wallace921029/dance-page`（`samples/` 已在 `.gitignore` 中排除）。

## 工作记录

| 日期 | 内容 |
| --- | --- |
| 2026-09-28 | 生成 `CLAUDE.md`；完成第一期产品需求讨论（D1–D37）；制作阅读端四个风格方向的对比页，选定 B 小剧场；确定后端 Python + FastAPI（D38）；完成技术设计初稿 05；`.gitignore` 加入 `samples/` |
| 2026-09-28 | 确认 05 技术设计，部署改为用户自配 Nginx（D39、D40）；M0：完成拆页脚本（裁白边、跨页检测）和翻页原型，桌面浏览器验证通过；发现裁白边和跨页配对两个待决问题 |
| 2026-09-28 | 阅读端新增读完提示与"合上书本"（D41），已在原型中实现 |
| 2026-09-28 | M1：后端骨架（FastAPI + SQLAlchemy + Alembic）、管理员同步、登录 / 注册 / 会话、邀请码、读者管理、登录限流；43 个测试；Dockerfile 与 docker-compose 实测通过；用户名 / 密码规则按推荐实现，待确认 |
| 2026-09-28 | 原型：封面翻页改为与其他页一致的卷页效果，封面左侧改用"舞台页"（合书时不再残留白页）；新增 `scripts/dev.sh` 一键启动前后端 |
| 2026-09-28 | 确认裁白边、跨页配对、账户规则（D42–D44）；M2 完成：拆页模块 `app/books/render.py`、Worker、绘本接口、登录页与 Admin 前端；dev.sh 与 docker-compose 加入 worker |
| 2026-09-28 | M3 完成：注册页、小剧场书架、正式阅读页（由 M0 原型重写，删除 `/prototype`）；自托管站酷小薇 / 思源黑体 |
| 2026-09-28 | 按用户要求全局改用 shadcn/ui 组件（Card、Field、Progress、Alert、Empty、Item、Avatar、NavigationMenu、Button 链接等），不再手写按钮、进度条、卡片；规则写入 CLAUDE.md |
| 2026-09-28 | 管理后台下拉框改用 shadcn `Select`；产品命名为"萤火 / Firefly Tales"（D45），更新页面标题、网站图标、`index.html` 元信息和界面品牌文字 |
| 2026-09-28 | 绘本列表每行加下架 / 上架、删除操作，下架与删除均需二次确认（D46）；修复删除后多余的 404 请求 |
| 2026-09-28 | 修复开发环境 `useId` 报错（浏览器加载了两份 React）：`vite.config.ts` 启动时预打包全部依赖（`optimizeDeps.entries`），并支持 `VITE_CACHE_DIR` 让测试环境使用独立缓存 |
| 2026-09-28 | 书架页四套主题 + 主题切换（D47），主题定义在 `src/pages/stage/shelf-themes.ts`、装饰在 `shelf-backdrop.tsx`；方案对比页存档到 `docs/design/shelf-style-options.html` |
| 2026-09-28 | 阅读端书架按每页 8 本分页，翻页按钮固定在视口两侧高度居中、不挤占书格（D48）；阅读页返回书架时保留所在页码 |
| 2026-09-28 | 书架翻页改用 `motion` 实现方向感滑动动画（D49），首次加载与减少动态效果模式下不播放 |
| 2026-09-28 | 书架上一页 / 下一页按钮移到页码左右两侧（D50），与绘本布局分离 |
| 2026-09-28 | 书架的翻页按钮与页码固定到视口底部，预留设备安全区与绘本下方空间（D51） |
| 2026-09-28 | 书架书本动效（D52）：`shelf-motion.ts`（进场、点按光点、萤火虫、动效开关）、`book-opening.ts`（封面飞入阅读页的过渡层）、`reader-layout.ts`（书架与阅读页共用的排版计算）；阅读页从书架进入时自动翻开封面 |
| 2026-09-28 | 书架页一屏显示、不出现滚动条（D53）：按屏幕方向 4×2 / 3×3 / 2×4 排列，书格随剩余空间缩放；7 种屏幕尺寸验证无滚动条 |
| 2026-09-28 | 书架搜索（D54，`shelf-search.tsx`）与收藏（D55：后端 `favorites` 表、`PUT/DELETE /api/books/{id}/favorite`；前端 `shelf-item.tsx` 爱心按钮、`/favorites` 我的收藏）；共享测试夹具移到 `tests/conftest.py`，后端 77 个测试 |
| 2026-09-28 | 收藏图标改为手绘涂鸦贴纸爱心 + 收藏反馈动画（D56）；收藏页标题、头像菜单也改用同一个爱心 |
| 2026-09-28 | 书架翻页按钮改为手绘涂鸦风格（D57），页码加手画波浪线 |
| 2026-09-28 | "我的收藏"入口改为头像左侧的手绘爱心按钮（D58），头像菜单不再包含收藏入口 |
| 2026-09-28 | M4：添加到主屏幕（D59）——`manifest.webmanifest`、iOS meta、`scripts/make-icons.py` 生成的 PNG 图标，书架 / 阅读页 / Admin 顶栏让出设备安全区；修复阅读页书本四周留白被重复扣除（书比设计小一圈，书架"翻开"的落点也与真实封面对不上） |
| 2026-09-28 | 横屏书架两排按封面宽高比计算合适行高并居中（D60）；修正仅改 `gap` 没有消除两排间大片留白的问题，为底部翻页多留空间，保持一屏显示和翻页栏位置不变 |
| 2026-09-28 | 开始讨论 AI 阶段需求：确认分两步（朗读 → Voice Ready，动画 → Dance Ready!）、每页朗读按钮 + 自动朗读、音色按书选定、动画只让主角做简单循环动作、多模态大模型识别台词、失败人工处理、国内服务商（D61–D66） |
| 2026-09-28 | AI 需求：朗读与动画相互独立；所有 AI 操作在绘本详情页"页面"模块按开页进行——大模型先分析整本故事、角色和音色提示词，管理员逐个开页选择分别 / 合并生成；多角色朗读；竖屏单页的合并开页播放规则（D67–D75） |
| 2026-09-28 | AI 需求：百炼、火山两家都接入，三种能力各自可随时切换服务商；视频时长、清晰度可配置（D76、D77） |
| 2026-09-28 | 切换服务商与视频参数的细节确认（D78、D79）；调研百炼 / 火山接口（百炼可按描述设计音色、万相首尾帧固定 5 秒；火山无音色设计接口），完成 AI 阶段技术设计初稿 `docs/06-ai-tech-design.md` |
| 2026-09-28 | API Key 改为管理员在后台录入、加密存入 SQLite（D80）；开发顺序调整为先 A1 AI 配置、再 A0 试验 |
| 2026-09-28 | AI A1：后端 `app/ai/`（服务商目录、Fernet 加密、配置读写、百炼 / 火山连接测试）、`ai_providers` / `ai_capabilities` / `ai_capability_configs` 三张表；后台"AI 配置"页 `/admin/ai`；`scripts/dev.sh` 缺少时自动生成 `APP_SECRET_KEY`；后端 94 个测试（D81） |
| 2026-09-28 | 按用户要求 AI 服务商 Key 改回写在 `.env`（D82，撤回 D80）：去掉加密存储和 `APP_SECRET_KEY`，新迁移删除 `ai_providers` 表；后台 AI 配置页的服务商卡片改为只读显示；`.env.example`、`backend/.env.example`、`backend/.env` 加入四个空的 Key 配置项 |
| 2026-09-28 | 豆包语音凭据改为单个 `VOLCENGINE_SPEECH_API_KEY`（D83），新版语音控制台不再有 App ID / Access Token |
| 2026-09-28 | AI 配置页"选择模型"：从百炼 / 方舟的模型列表获取并按能力筛选，与内置推荐合并，仍可手动输入（D84）；后端 96 个测试 |
| 2026-09-28 | AI 配置页的服务商由左右两张卡片改为一张卡片内用 Tabs 切换，标签上显示已设置的 Key 数量 |
| 2026-09-28 | 百炼视觉模型列表加入 Qwen3.5 起的原生多模态通用模型，按版本排序，默认改为 `qwen3.8-max`（D85） |
