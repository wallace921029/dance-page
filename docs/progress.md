# 项目进度与交接

> 最后更新：2026-09-28 · 工作分支 `main` · 最后一个决策编号 **D90**（下一个 **D91**）
>
> **给接手的 Claude / 开发者**：这是继续工作的入口。用户说"继续我们的任务"时，按顺序读：本文件 → `CLAUDE.md` → 与当前任务相关的 `docs/0x-*.md`，然后按"下次开始时"一节执行。每次工作结束前更新本文件（当前位置、断点、下次开始时、工作记录）。

## 一句话现状

第一期（上传 → 书架 → 翻页阅读）功能全部完成，只差 iPad 真机实测和部署收尾（M4）。AI 阶段完成了 A1（AI 配置）、A0（真实 API 试验验证，D88）与 **A2（故事与草稿工作台，D89）**，并修复了视觉模型深度思考截断与弹窗关闭交互（D90）；**下一步是 A3 朗读 → Voice Ready**：角色音色设计与试听、单元台词逐行合成与拼接、后台确认与阅读端小喇叭播放。

## 当前位置

```
第一期（MVP）
[✅] 产品需求 01–04 / 技术设计 05
[🟡] M0 仿真翻页验证        桌面浏览器通过；等 iPad 真机实测（直接测正式阅读页）
[✅] M1 后端骨架与账户
[✅] M2 上传与拆页 + 管理后台（绘本 / 邀请码 / 读者）
[✅] M3 阅读端（小剧场书架、翻页阅读、收藏、搜索、四套书架主题、书本动效）
[🟡] M4 打磨与上线          ✅ 添加到主屏幕  ⬜ Nginx 参考配置  ⬜ 部署说明  ⬜ 备份

AI 阶段（设计见 06-ai-tech-design.md）
[✅] 需求（D61–D85）与技术设计 06
[✅] A1 AI 配置              后台 /admin/ai：Key 读 .env、每种能力选服务商和模型、选择模型下拉、测试连接
[✅] A0 试验                 全流程真实 API 验证通过（D88，见 samples/ai-trial/TRIAL_REPORT.md）
[✅] A2 故事与草稿           绘本详情页 AI 工作台、故事分析入库、角色 CRUD、开页分别/合并、草稿编辑与单单元重写
[⬜] A3 朗读 → Voice Ready   ← 下一步
[⬜] A4 动画 → Dance Ready!
```

## 在新电脑上接着做

### 1. 代码和工具

- 仓库：`github.com/wallace921029/dance-page`，**直接使用 `main` 分支（全量代码均在 `main`，无其他分支）**：`git clone … && cd dance-page`。
- 工具：Node 24（npm）、[uv](https://docs.astral.sh/uv/)（自动安装 Python 3.13）、git、Google Chrome（`scripts/make-icons.py` 和端到端测试会用到）。
- 启动：仓库根目录执行 `scripts/dev.sh`（首次会自动 `npm install`、`uv sync`，并从模板创建 `backend/.env`）。浏览器打开 `http://localhost:5173`，管理员账号密码在 `backend/.env`。

### 2. 不在 git 里、需要手动处理的东西

| 内容 | 位置 | 怎么处理 |
| --- | --- | --- |
| 本地配置和 AI Key | `backend/.env` | 从 `backend/.env.example` 复制（dev.sh 会自动复制），再填 `DASHSCOPE_API_KEY`、`VOLCENGINE_ARK_API_KEY`、`VOLCENGINE_SPEECH_API_KEY`（见 06 第 3 节）。**Key 不要提交** |
| 样书 PDF | `samples/` | 从旧电脑拷过来（目前只有《波西和皮普 大怪兽》）；`samples/` 在 `.gitignore` 里 |
| 本地数据（数据库、拆好的页面图） | `backend/data/` | 不需要拷贝：新电脑启动后重新上传样书即可；想保留就整个目录拷过来 |
| 部署配置 | 仓库根目录 `.env` | 部署到服务器时从 `.env.example` 复制并填写 |

### 3. 检查环境是否正常

```bash
cd backend && uv run pytest            # 应全部通过（目前 103 个）
cd .. && npm run build && npm run lint # 构建通过；lint 只有 shadcn 组件里原有的几个警告
```

然后登录管理后台 → "AI 配置"，每项点一次"测试连接"（豆包语音暂不支持测试，显示"已设置"即可）。

### 4. 环境相关的坑

- **端口**：8000 被占用时 `dev.sh` 自动改用下一个空闲端口，并让 Vite 的 `/api` 代理指过去（原电脑上 8000 常被另一个项目占用）。
- **系统代理**：AI 请求不读取 `HTTP(S)_PROXY` / `ALL_PROXY`（D81），国内服务直连；不要为了"翻墙"把它改回去。
- **改 `.env` 要重启 `dev.sh`**：`--reload` 只监听 Python 代码。
- **Vite 缓存**：两个开发服务器不要共用 `node_modules/.vite`，否则浏览器可能加载到两份 React 而报 `useId` 错误；另开一套时用 `VITE_CACHE_DIR` 指定别的目录。
- **文件监听数上限**：Vite 启动报 `EMFILE: too many open files, watch …` 时，是系统的 inotify 实例数（`/proc/sys/fs/inotify/max_user_instances`，默认 128）被其他程序占满了。可以关掉不用的开发服务器 / 编辑器窗口，或由用户自己调高该限制（需要 root）。Claude 做端到端测试时可改用不监听文件的方式：`npm run build` 后 `API_PROXY_TARGET=http://127.0.0.1:8010 npx vite preview --port 5180 --strictPort`，后端直接 `DATA_DIR=<临时目录> backend/.venv/bin/uvicorn --factory app.main:create_app --port 8010`。

## 断点：等待用户的事项

| # | 事项 | 何时需要 | 状态 |
| --- | --- | --- | --- |
| 1 | 在 iPad 上实测阅读页，按下方"iPad 验证清单"反馈结果 | 上线之前 | 待测试 |
| 2 | 再提供 1–2 本 PDF，**至少一本横版**，放到 `samples/`（目前只有一本竖版；横版只用生成的测试 PDF 验证过） | 上线之前 | 待提供 |
| 3 | 在 `.env` 填好三个 AI Key，并在"AI 配置"页各点一次"测试连接" | A0 试验之前 | ✅ 已完成（A0 试验已全面验证） |

## 下次开始时（Claude 执行步骤）

1. 读本文件、`CLAUDE.md`、`docs/06-ai-tech-design.md`。
2. 向用户简要汇报当前位置：A2 故事与草稿工作台已完成（D89），视觉大模型深度思考截断与弹窗关闭交互已修复（D90）。
3. 推进 **Milestone A3 朗读 → Voice Ready**（分三步执行）：
   - **步骤 1：角色专属音色设计与试听服务**
     - Worker `ai_voice` 任务：针对角色 `voice_prompt` 调用百炼 `qwen-voice-design`（支持自定义提示词定制音色），试听 WAV 保存至 `books/{id}/ai/voices/{voice_id}.wav`，存入 `character_voices` 表；
     - 后端提供音频静态服务接口：`GET /api/admin/books/{id}/ai/voices/{voice_id}`；
     - 前端角色卡片：显示音色状态、播放试听音频、重新生成/更换音色；
   - **步骤 2：单元台词逐行合成与拼接**
     - Worker `ai_tts_unit` 任务：检查单元所有说话人角色均已生成音色，逐行调用 `qwen3-tts-vd-2026-01-26` 合成音频，行间插入 0.4s 静音，使用 PyAV 编码为 AAC `.m4a` 保存至 `books/{id}/ai/audio/{unit_id}.m4a`；
     - 记录 `audio_duration_ms` 与 `audio_source_hash`，单元状态更新为 `ready`；
     - 前端单元卡片：显示 **"生成朗读"** 按钮与试听音频播放器（若草稿被编辑过提示"需要重新生成"）；
     - 顶部工具栏：新增 **"全部生成朗读"** 批量入队（`POST /api/admin/books/{id}/ai/generate-all?type=audio`）；
   - **步骤 3：后台 Voice Ready 确认与阅读端小喇叭播放**
     - 后台 Voice Ready 状态切换接口（`PUT/DELETE /api/admin/books/{id}/ai/voice-ready`）；
     - 书架端：对 `voice_ready` 为 true 的书名左侧展示手绘音乐符号 🎵（D70）；
     - 阅读端：详情接口返回 `read_order` 与 units `audio_url`，页面展示手绘小喇叭按钮（分别生成左右各一，合并生成居中），顶栏提供"自动朗读"开关（本地 `localStorage`）与 Web Audio 解锁。

## 接下来要做的事

### A0 试验（已完成，D88）

试验脚本 `backend/scripts/ai_trial.py`（`uv run scripts/ai_trial.py`）已完成全部 4 项试验验证，完整报告存档于 `samples/ai-trial/TRIAL_REPORT.md`。结论：故事识别推荐 `qwen3.8-flash`；角色音色设计用 `qwen-voice-design`；朗读合成用 `qwen3-tts-vd` + PyAV 编码 AAC .m4a；动画视频用 `wan2.2-kf2v-flash`（单页与对开左右拼图）。

| # | 试验内容 | 要回答的问题 |
| --- | --- | --- |
| 1 | 故事分析：把样书全部页面缩到长边 1024px，一次发给视觉模型（百炼 `qwen3.8-max` / 火山视觉模型各一次），按 06 第 6.1 节要求返回 JSON | JSON 是否稳定；故事、角色、每页台词（逐行标说话人）、动作描述、"左右是否同一场景"的质量；30 页一次发送是否超限、耗时和费用 |
| 2 | 音色：百炼 `qwen-voice-design` 按角色音色提示词设计 2–3 个音色；火山从现成音色里挑 2–3 个 | 设计出的音色能否用于非实时合成（`qwen3-tts-vd-*`）；让用户试听选择 |
| 3 | 朗读合成：同一页台词，逐行用不同音色合成，拼成一段（行间停 0.4 秒），用 PyAV 编码为 `.m4a` | 两家接口的请求格式、音频格式、速度和费用；豆包语音 `X-Api-Key` + `X-Api-Resource-Id: seed-tts-2.0` 的实际用法（顺便补上它的"测试连接"） |
| 4 | 首尾帧视频：挑一个单页和一个"合并生成"的开页（左右拼成整图），首尾帧都用原图，按 06 第 6.5 节的提示词模板生成；百炼 `wan2.2-kf2v-flash`，火山 Seedance（**2.x 系列在模型列表里没标明支持首尾帧，要实际验证**） | 主角是否真的动、画面里的文字会不会抖、画风是否跑偏、清晰度（720P / 1080P）、首尾帧相同时是否几乎不动（对比"只给首帧"） |

试验完成后：把结论写进 06 第 2 节（接口参数）和第 9 节（风险结论），重要取舍记入决策记录；给用户一页对比结果（可做成 artifact），请用户选定服务商和参数。

### A2 故事与草稿（见 06 第 4、6.1、6.2、7、8.1 节）

- 数据表：`books` 加 `story`、`read_order`、`voice_ready_at`、`dance_ready_at`；新表 `characters`、`character_voices`、`ai_units`；`jobs` 加 `unit_id`、`character_id`、`remote_task_id`、`next_poll_at` 和新任务类型。
- Worker：`ai_analyze_book`（分析整本故事 → 角色、按开页建生成单元、写台词和动作描述草稿）、`ai_draft_unit`（单个单元重写草稿）。
- 接口：`/api/admin/books/{id}/ai`（读取、分析、改故事和朗读顺序）、角色增删改、开页"分别 / 合并"切换、单元台词和动作描述修改。
- 管理后台：绘本详情页"页面"模块改为按开页的 AI 工作台（故事与角色卡片、每个开页一张卡片，示意图见 03 "在哪里操作"）。
- 规则：失败不自动重试（D65）；修改对开配对时提示会清除受影响开页的 AI 内容。

### A3 朗读 → Voice Ready（见 06 第 6.3、6.4、8.2 节）

- `ai_voice`（百炼按提示词设计音色 / 火山从现成音色清单里挑）、`ai_tts_unit`（逐行合成、拼接、编码 `.m4a`）；音色与"服务商 + 合成模型"绑定（D78）。
- 后台：角色试听、换音色；单元"生成朗读"、试听、"全部生成"；确认 / 取消 Voice Ready。
- 阅读端：每页手绘小喇叭按钮、"自动朗读"开关（存本机，读完不自动翻页，D68）、对开朗读顺序（D69）、竖屏合并单元的播放规则（D74）；用 Web Audio 解决 iPad 自动播放限制（需真机验证）；书架书名前的音乐符号（D70）。

### A4 动画 → Dance Ready!（见 06 第 6.5、6.6、8.2 节）

- `ai_video_unit`：提交首尾帧任务 → 定时查询 → 下载（链接 24 小时有效）→ 去音轨、faststart；Worker 不能被视频任务堵住（提交和查询分开，同时最多 3 个）。
- 后台：单元"生成动画"（可临时改时长、清晰度，D79）、预览；确认 / 取消 Dance Ready!。
- 阅读端：页面图上叠 `<video muted playsinline loop>`，翻页时暂停、停稳后淡入；合并单元左右各播一半；书架"Dance Ready!"剧场招牌。

### M4 上线收尾（可与 AI 工作穿插，见 05 第 4 节）

- Nginx 参考配置：`client_max_body_size 210m`、上传接口加大超时、SPA 回退到 `index.html`、`/api/` 转发、`.webmanifest` 的 `application/manifest+json` 类型（较旧的 Nginx `mime.types` 里没有）。
- 部署说明（README）：`.env`（含 AI Key、`COOKIE_SECURE`）、`docker compose up -d --build`、`npm run build` 后把 `dist/` 交给 Nginx。
- 备份：SQLite 在线备份命令 + `books/` 目录同步的脚本或说明。
- 视情况：Admin 页面预览改用缩略图（现在直接加载 2048px 大图）、Docker 镜像多阶段构建瘦身。

## 以后再做 / 已知问题

- **管理后台窄屏**：手机宽度下顶部导航放不下，页面出现横向滚动（管理后台主要在电脑上用，暂未处理；可改为窄屏收成菜单）。
- **`scripts/dev.sh` 启动阶段崩溃时不退出**：Vite 刚启动就崩溃（如 EMFILE）时，脚本没有停掉 API 和 Worker，而是一直挂着。推测是崩溃发生在执行到 `wait -n` 之前，`wait -n` 没能察觉；尚未验证和修复。
- **豆包语音的"测试连接"**：暂不支持，A0 摸清接口后补上。
- **Seedance 2.x 首尾帧**：方舟模型列表只给 1.0 系列标了 `first_last_frame`，2.x 是否支持待 A0 验证。
- **iPad 相关待验证**：卷页性能、添加到主屏幕、Web Audio 自动朗读解锁、同时播放视频的内存占用。
- **AI 阶段已明确不做**：文字高亮（D62）、读者自选音色（D63）、生成前的费用预估（D65）、失败自动重试（D65）。

## 给 Claude 的操作注意事项

- **提交**：所有工作直接在 `main` 分支上进行，不要保留或创建任何其他分支；只在用户要求时提交 / 推送。不要提交 `backend/.env`、`.env`、`backend/data/`、`samples/`。
- **并行会话**：用户有时会同时开另一个会话改代码（曾改过 `shelf.tsx`、文档、决策编号）。改文件前先看 `git status` / 最新内容；决策编号以 `decision-log.md` 最后一条为准。
- **端到端测试不要碰用户的开发环境**：用独立端口、临时数据目录和独立 Vite 缓存，例如 `DATA_DIR=<临时目录>/data VITE_CACHE_DIR=<临时目录>/vite BACKEND_PORT=8010 FRONTEND_PORT=5180 scripts/dev.sh`；浏览器测试用 `uv run --with playwright python 脚本.py`（Chrome 路径 `/usr/bin/google-chrome`）。**不要删除或改写 `backend/data`**；用户的开发服务器可能正在运行并自动执行迁移。
- **停测试环境**：按端口查进程号再结束（`ss -ltnp "sport = :8010"`），不要用会匹配到自己命令行的 `pkill -f <模式>`。
- **Worker 进程**：测试环境的 Worker 通过 `/proc/<pid>/environ` 里的 `DATA_DIR` 区分，不要结束用户的 Worker。
- **AI Key**：只从 `.env` 读，任何接口、日志、页面都不能输出完整 Key；调用服务商的付费接口前先告诉用户。

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
  - 每个决策追加到 [decision-log.md](./decision-log.md)，编号连续（以 `decision-log.md` 最后一条为准，当前 **D87**）。
  - 每次工作结束前更新本文件的"当前位置""断点""下次开始时"。
- **视觉风格**：阅读端为"B 小剧场"。示意图的本地副本在 [design/reader-style-options.html](./design/reader-style-options.html)，在线版在 https://claude.ai/artifact/3TwChZ4w49eXKvKkSMSW1z（需要登录用户本人的 claude.ai 账号）。

## 代码现状

- **前端**（`src/`，Vite + React 19 + TypeScript + Tailwind v4 + shadcn/ui on Base UI + react-query + react-router 8 + `motion`）：
  - 阅读端（小剧场风格，`src/pages/stage/`）：登录 `/login`、注册 `/register?code=`、书架 `/`、我的收藏 `/favorites`、阅读页 `/books/:id`。主题色和字体在 `src/index.css` 的 `@theme`；书架主题 `shelf-themes.ts`、背景装饰 `shelf-backdrop.tsx`、动效 `shelf-motion.ts`、翻开过渡 `book-opening.ts`、阅读排版 `reader-layout.ts`、翻页 `flip-book.tsx`。
  - 管理后台（`src/pages/admin/`）：`/admin/books`、`/admin/books/:id`、`/admin/invites`、`/admin/readers`、`/admin/ai`；进场动画用 `motion.tsx` 里的 `Reveal` / `AnimatedTableRow` / `RevealItem`。
  - 数据请求：`src/api/*.ts`（react-query hooks + 类型 `src/api/types.ts`，AI 配置在 `src/api/ai.ts`）；路由守卫 `src/router/guards.ts`；会话过期跳回登录页（`src/lib/query-client.ts`）。
  - 添加到主屏幕：`public/manifest.webmanifest`、`public/icons/`（由 `uv run scripts/make-icons.py` 生成）。
- **后端**（`backend/app/`，FastAPI + SQLAlchemy 2 + SQLite + Alembic，uv 管理）：账户 / 会话（`auth/`）、邀请码（`invites/`）、读者（`readers/`）、绘本与收藏（`books/`）、Worker 拆页（`worker/`、`books/render.py`）、AI 配置（`ai/`：`catalog.py` 服务商和能力目录、`settings.py` 配置读写、`providers/` 百炼 / 火山适配器——目前实现了连接测试和模型列表）；96 个 pytest 测试。
  - 测试与检查：`cd backend && uv run pytest`、`uv run ruff check . && uv run ruff format .`；前端 `npm run build`、`npm run lint`。
  - 新增数据表：改 `app/models.py` 后运行 `uv run alembic revision --autogenerate -m "说明"`（在临时 `DATA_DIR` 上生成，别用 `backend/data`），检查生成的迁移文件。
  - `backend/scripts/render_samples.py`：把 `samples/*.pdf` 渲染到 `samples/rendered/`，调整拆页参数时对比效果。
- **部署**：仓库根目录 `docker-compose.yml`（api + worker）+ `.env.example`；数据在仓库根目录 `./data`；Nginx 由用户自己配置（D39）。

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
| 2026-09-28 | 管理后台进场动画（D86）：`src/pages/admin/motion.tsx`（`Reveal` 模块、`AnimatedTableRow` 表格行、`RevealItem` 缩略图），布局里用 `MotionConfig reducedMotion="user"` 和按路径淡入的 `motion.main` |
| 2026-09-28 | 整理交接文档：`progress.md` 重写为"现状 / 新电脑上手 / 断点 / 接下来要做的事（A0–A4、M4）/ 已知问题 / 操作注意事项"，方便换电脑、换模型后直接继续 |
| 2026-09-28 | 管理后台"退出"收进右上角头像下拉菜单（D87）；记录 Vite 文件监听数上限（EMFILE）问题和不监听文件的测试方式 |
| 2026-09-28 | 完成 A0 试验（D88）：编写 `backend/scripts/ai_trial.py`；全流程验证百炼与火山方舟视觉故事分析（推荐 `qwen3.8-flash` 单本成本<0.05元）、百炼 `qwen-voice-design` 角色音色设计与试听、多角色朗读逐行合成与 PyAV 拼接为 AAC `.m4a`、百炼 `wan2.2-kf2v-flash` 首尾帧循环视频（单页与对开大图拼接）；发现火山方舟 Seedance 2.0 未开通且 1.0 pro fast 不支持首尾帧，豆包语音 Key 缺 resource 权限；生成完整试验报告 `samples/ai-trial/TRIAL_REPORT.md` |
| 2026-09-28 | 完成 AI Milestone A2（D89）：数据库迁移（`characters`、`character_voices`、`ai_units`、`books` AI 字段）；后端故事分析与单单元重写 Worker、开页与单元 CRUD 接口；前端绘本详情页 AI 工作台（故事/角色卡片、开页分别/合并切换、逐行台词与微动作编辑、单单元重写草稿）；102 个后端测试全部通过，前端打包与检查零错误 |
| 2026-09-28 | 修复大模型长链思考截断与交互缺陷（D90）：视觉模型显式关闭思考模式（百炼 `enable_thinking=False`，方舟 `thinking={"type": "disabled"}`），Token 上限提至 8192；增强 JSON 解析容错（`strict=False` 支持未转义换行符、Markdown 代码块提取、末尾逗号自动修复与 `length` 截断拦截）；修复 Base UI `AlertDialogAction` 补全 Close 包装与工作台分析弹窗受控关闭；103 个后端测试通过，前端 Lint 0 错误 |
