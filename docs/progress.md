# 项目进度与交接

> 最后更新：2026-09-29 · 工作分支 `main` · 最后一个决策编号 **D97**（下一个 **D98**）
>
> **给接手的 Claude / 开发者**：这是继续工作的入口。用户说"继续我们的任务"时，按顺序读：本文件 → `CLAUDE.md` → 与当前任务相关的 `docs/0x-*.md`，然后按"下次开始时"一节执行。每次工作结束前更新本文件（当前位置、断点、下次开始时、工作记录）。

## 一句话现状

第一期（上传 → 书架 → 翻页阅读）功能全部完成，只差 iPad 真机实测和部署收尾（M4）。AI 阶段已完成 A1 AI 配置、A0 试验（D88）、A2 故事与草稿（D89–D90）、**A3 朗读 → Voice Ready**（角色音色、单元朗读、朗读稿扩充、Voice Ready 与阅读端小喇叭 / 自动朗读、开页开关，D91–D95），以及插入的**封面动画**（像魔法报纸上会动的照片，D96–D97：真实生成已跑通，第一次生成几乎不动，已修正提示词，待用户重新生成确认效果）。**下一步是 A4 动画 → Dance Ready!**，视频管道已在封面动画里建好，可直接复用。

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
[✅] A3 朗读 → Voice Ready   角色音色、单元朗读、朗读稿扩充、Voice Ready 与阅读端（iPad 真机待验证）
[✅] 封面动画（插入）       D96–D97：封面首尾帧视频、视频任务提交 / 查询调度、后台卡片、书架与阅读页封面播放；真实生成已跑通，修正后的动作效果待确认
[⬜] A4 动画 → Dance Ready!  ← 下一步
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
cd backend && uv run pytest            # 应全部通过（目前 144 个）
cd .. && npm run build && npm run lint # 构建通过；lint 只有 shadcn 组件和 ai-workbench.tsx 里原有的几个警告
```

然后登录管理后台 → "AI 配置"，每项点一次"测试连接"（豆包语音暂不支持测试，显示"已设置"即可）。**朗读和动画视频都要选阿里云百炼**（火山的豆包语音未开通合成权限、视频模型不支持首尾帧，D88）；故事与台词识别两家都可以。

### 4. 环境相关的坑

- **端口**：8000 被占用时 `dev.sh` 自动改用下一个空闲端口，并让 Vite 的 `/api` 代理指过去（原电脑上 8000 常被另一个项目占用）。
- **系统代理**：AI 请求不读取 `HTTP(S)_PROXY` / `ALL_PROXY`（D81），国内服务直连；不要为了"翻墙"把它改回去。
- **改 `.env` 或新增迁移后要重启 `dev.sh`**：`--reload` 只监听 `backend/app/` 下的 Python 代码，迁移在 API 启动时执行。
- **macOS**：`scripts/dev.sh` 兼容系统自带的 bash 3.2（不用 `wait -n`）；Ctrl+C 后 API、Worker、Vite 都会在 1–2 秒内退出。
- **Vite 缓存**：两个开发服务器不要共用 `node_modules/.vite`，否则浏览器可能加载到两份 React 而报 `useId` 错误；另开一套时用 `VITE_CACHE_DIR` 指定别的目录。
- **文件监听数上限**：Vite 启动报 `EMFILE: too many open files, watch …` 时，是系统的 inotify 实例数（`/proc/sys/fs/inotify/max_user_instances`，默认 128）被其他程序占满了。可以关掉不用的开发服务器 / 编辑器窗口，或由用户自己调高该限制（需要 root）。Claude 做端到端测试时可改用不监听文件的方式：`npm run build` 后 `API_PROXY_TARGET=http://127.0.0.1:8010 npx vite preview --port 5180 --strictPort`，后端直接 `DATA_DIR=<临时目录> backend/.venv/bin/uvicorn --factory app.main:create_app --port 8010`。

## 断点：等待用户的事项

| # | 事项 | 何时需要 | 状态 |
| --- | --- | --- | --- |
| 1 | 在 iPad 上实测阅读页，按下方"iPad 验证清单"反馈结果（含朗读、封面动画两项） | 上线之前 | 待测试 |
| 2 | 再提供 1–2 本 PDF，**至少一本横版**，放到 `samples/`（目前只有竖版；横版只用生成的测试 PDF 验证过） | 上线之前 | 待提供 |
| 3–6 | AI Key 与连接测试、真实生成音色、真实生成朗读、朗读稿扩充效果 | A3 期间 | ✅ 均已完成（2026-09-29 用户确认"效果很好"） |
| 7 | 对一本已生成朗读的书点"确认 Voice Ready"，用读者账号在电脑和 iPad 上试：书架音符、每页小喇叭、自动朗读（尤其 iPad 上从书架点开后翻页能否自动出声） | A4 之前（iPad 部分可与第 1 项一起） | 待测试 |
| 8 | 封面动画：真实生成已跑通（约 80 秒，D96），但第一次生成的视频几乎不动；已修正提示词、描述留空时由 AI 看封面写具体动作（D97）。请在《波西和皮普尿裤子》上把动作描述留空点"重新生成"，用"放大预览"看动作幅度是否合适（会产生少量费用） | A4 之前 | 待测试 |

## 下次开始时（Claude 执行步骤）

1. 读本文件、`CLAUDE.md`、`docs/06-ai-tech-design.md`。
2. 向用户简要汇报当前位置：A3 已完成（D91–D95），插入的封面动画已完成（D96–D97）。先确认断点第 7、8 项的结果；第 8 项若动作仍太小或太大，调整 `backend/app/ai/video.py` 的 `COVER_PROMPT_TEMPLATE` / `NEGATIVE_PROMPT` 和 `vision.py` 的 `describe_cover_motion` 措辞（改提示词会让已生成的封面显示"需要重新生成"）。
3. 推进 **Milestone A4 动画 → Dance Ready!**（见下方"A4"一节和 06 第 6.5、6.7、8.2 节）：
   - 确认用户的"AI 配置"里动画视频已是百炼 `wan2.2-kf2v-flash`；
   - **复用封面动画的视频管道**（D96）：`providers.submit_video` / `poll_video` / `download`，`app/ai/video.py`（首帧 JPEG、去音轨与 faststart），Worker 的 `waiting` 调度——把 `ai_video_unit` 加进 `VIDEO_JOB_TYPES`，提交时的参数放 `jobs.payload`；
   - **提示词吸取 D97 的教训**：动作描述要点名具体角色和动作，不要把"幅度很小"强调过头；单元的 `motion_prompt` 已由 A2 写好草稿；
   - 合并单元把左右两页拼成一张整图做首帧；可临时改时长、清晰度（D79，放 `payload`）；
   - 遵守开页的"动画"开关（`ai_units.video_enabled`，D95）；
   - 后台：单元卡片加"动画"一栏（仿照"朗读"一栏）、生成进度卡片加"动画"一行（全部生成 + Dance Ready! 确认）；
   - 阅读端：页面上叠 `<video>`，复用 `FlipBook` 的 `overlay`、`onFlippingChange` 和按位置的 `slots`，以及 `src/pages/stage/cover-video.tsx` 的播放 / 隐藏做法；合并单元左右各显示一半；书架"Dance Ready!"剧场招牌。

## 接下来要做的事

### 已完成的 AI 里程碑（详见 06 和决策记录）

- **A0 试验**（D88）：`backend/scripts/ai_trial.py`，报告 `samples/ai-trial/TRIAL_REPORT.md`。结论：故事识别推荐 `qwen3.8-flash`；音色 `qwen-voice-design`；朗读 `qwen3-tts-vd` + PyAV 编码 AAC `.m4a`；动画 `wan2.2-kf2v-flash`。
- **A2 故事与草稿**（D89–D90）：分析整本故事、角色、开页分别 / 合并、台词与动作描述草稿编辑、单元重写。
- **A3 朗读 → Voice Ready**（D91–D95）：角色音色、单元朗读、朗读稿适度扩充（原文逐字保留 + 每页补 2–3 句）、Voice Ready 确认、阅读端小喇叭与自动朗读、开页的朗读 / 动画开关与"生成本开页朗读"。
- **封面动画**（D96–D97，插入需求）：封面首尾帧视频、视频任务提交 / 查询调度、后台"封面动画"卡片、书架与阅读页封面循环播放。

### A4 动画 → Dance Ready!（见 06 第 6.5、6.7、8.2 节）

- `ai_video_unit`：复用封面动画的视频管道（见"下次开始时"），合并单元拼接左右两页做首帧。
- 后台：单元"生成动画"（可临时改时长、清晰度，D79）、预览；生成进度卡片的"动画"一行（全部生成、确认 / 取消 Dance Ready!）。
- 阅读端：页面图上叠 `<video muted playsinline loop>`，翻页时隐藏、停稳后淡入；合并单元左右各播一半；书架"Dance Ready!"剧场招牌。

### M4 上线收尾（可与 AI 工作穿插，见 05 第 4 节）

- Nginx 参考配置：`client_max_body_size 210m`、上传接口加大超时、SPA 回退到 `index.html`、`/api/` 转发、`.webmanifest` 的 `application/manifest+json` 类型（较旧的 Nginx `mime.types` 里没有）；视频、音频接口要保留分段请求（Range）。
- 部署说明（README）：`.env`（含 AI Key、`COOKIE_SECURE`）、`docker compose up -d --build`、`npm run build` 后把 `dist/` 交给 Nginx。
- 备份：SQLite 在线备份命令 + `books/` 目录同步的脚本或说明。
- 视情况：Admin 页面预览改用缩略图（现在直接加载 2048px 大图）、Docker 镜像多阶段构建瘦身。

## 以后再做 / 已知问题

- **管理后台窄屏**：手机宽度下顶部导航放不下，页面出现横向滚动（管理后台主要在电脑上用，暂未处理；可改为窄屏收成菜单）。
- **火山暂不支持朗读和动画**：豆包语音账号未开通合成权限（403），视频模型不支持首尾帧（D88）；选火山时"生成音色""生成朗读""生成封面动画"会提示切换到百炼（D91、D96）。按 06 第 6.3 节，火山的音色应从现成音色清单里挑，开通权限后再做；豆包语音的"测试连接"也等那时补上。
- **百炼上的旧音色不会删除**：重新生成音色只替换本地记录，百炼账号里的旧音色还在（账号有音色数量上限，本项目用量很小；需要时再接百炼的删除接口）。
- **封面动画的文件偏大**：720P、5 秒约 6MB；书架一屏最多 8–9 本、只播看得见的，但网络慢时会晚一些才动起来。需要时可以为书架另存一份低清晰度版本。
- **iPad 相关待验证**：卷页性能、添加到主屏幕、Web Audio 自动朗读解锁、静音视频自动播放、同时播放多个视频的内存占用。
- **AI 阶段已明确不做**：文字高亮（D62）、读者自选音色（D63）、生成前的费用预估（D65）、失败自动重试（D65）。

## 给 Claude 的操作注意事项

- **提交**：所有工作直接在 `main` 分支上进行，不要保留或创建任何其他分支；只在用户要求时提交 / 推送（用户也常在另一个会话里自己提交）。不要提交 `backend/.env`、`.env`、`backend/data/`、`samples/`。
- **并行会话**：用户有时会同时开另一个会话改代码或提交。改文件前先看 `git status` / 最新内容；决策编号以 `decision-log.md` 最后一条为准。
- **端到端测试不要碰用户的开发环境**：用独立端口、临时数据目录和独立 Vite 缓存，例如 `DATA_DIR=<临时目录>/data VITE_CACHE_DIR=<临时目录>/vite BACKEND_PORT=8010 FRONTEND_PORT=5180 ADMIN_USERNAME=e2eadmin ADMIN_PASSWORD=… DASHSCOPE_API_KEY=sk-invalid-e2e-test scripts/dev.sh`（环境变量优先于 `backend/.env`；无效 Key 让误点的生成请求直接失败、不产生费用）。浏览器测试用 `uv run --with playwright python 脚本.py`，macOS 上 Chrome 路径是 `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`。**不要删除或改写 `backend/data`**，查看用户数据只用只读连接（`sqlite3.connect('file:data/app.db?mode=ro', uri=True)`）。
- **停测试环境**：记下后台启动的 `dev.sh` 进程号，`kill -TERM <pid>` 即可（它会停掉自己的 API、Worker、Vite）；用 `lsof -nP -iTCP:8010 -iTCP:5180 -sTCP:LISTEN` 确认已停。不要用会误杀用户进程的 `pkill -f <模式>`。
- **迁移**：
  - 一旦写出就不要再改：用户的开发服务器会在代码变化时自动重启并执行迁移，改已执行过的迁移不会再生效（D96 时出过缺列事故）；要补字段就新建一个迁移。
  - 迁移手写或在临时 `DATA_DIR` 上生成；验证时在临时目录上跑 `upgrade head` → `alembic check` → `downgrade -1`，**先确认临时目录变量非空**（为空时 `DATA_DIR=""` 会在 `backend/` 下建出 `app.db`）。
- **AI Key**：只从 `.env` 读，任何接口、日志、页面都不能输出完整 Key；调用服务商的付费接口前先告诉用户，自动测试一律用假的服务商（`monkeypatch` 替换 `providers.http_client`）。

## 阅读页实现要点（M0 验证得出，已用于 `src/pages/stage/flip-book.tsx`）

- 用 `page-flip` 的 HTML 模式（canvas 模式不处理 devicePixelRatio，在 iPad 高清屏上会发虚）。
- 单页 / 对开由我们自己决定（竖版书且横屏 → 对开）：设 `minWidth = maxWidth = 页宽`，根元素宽度为 1 倍或 2 倍页宽。
- 库会把根元素宽度改成 `100%`，所以外面要套一层定宽容器；库的 `destroy()` 会把根元素一起删掉，因此根元素由代码动态创建，不交给 React 管理；排版变化（旋转屏幕等）时销毁重建，并保持当前页。
- 库绘制时会用 `style.cssText` 覆盖页面元素自身的内联样式，底色等样式要放在内层子元素上。
- **不用 `showCover`**：它会把封面设成硬页（整张翻转、没有卷页），而且往回翻到封面时左侧会残留当前左页。改为对开时在封面左边放一张"舞台页"（内层是与舞台背景对齐的背景），按 (0,1)(2,3)… 配对；`spread_start_page = 3` 时在封面后插入空白页；`loadFromHTML` 之后对所有页调用 `getPage(i).setDensity("soft")`。
- 合上书本用 `pageFlip.flip(封面位置)`：无论隔多少页都只播放一次翻页动画。
- 图片只给当前页前后 4 页设置地址（兼作预加载），其余页释放以节省内存；封面始终保留（合书时要用）。
- `FlipBook` 对外提供（A3、封面动画用）：`onVisibleChange(pages, slots)`——`slots` 按位置给页码（单页 1 项，对开 [左, 右]，舞台页 / 空白页为 null）；`onFlippingChange`——拖动或翻页动画中为 true；`overlay`——叠在书上方、与书同尺寸的 React 层（小喇叭、封面视频）。对开时起始位置要对齐到偶数（左页），否则左右会算反。
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
- [ ] 封面动画（D96）：书架上的封面在动且不卡；阅读页封面翻开前在动，翻页时立即停住；静音模式下也能自动播放
- [ ] 朗读（D94）：书架上有朗读的书名前有音符；每页小喇叭点了能出声、再点停止；打开"自动朗读"后翻页停稳自动读，翻页时立刻停；从书架点开书后不用再点任何按钮，翻页也能自动出声（Web Audio 解锁）；静音开关打开时是否仍有声音（Web Audio 在 iOS 上受静音键影响，记录实际表现）
- [ ] Safari"分享 → 添加到主屏幕"后图标、名称正确；从主屏幕打开没有地址栏，夜幕背景铺到状态栏下，按钮不被状态栏和底部横条遮挡，没有全屏按钮

## 协作约定

- **语言**：与用户用中文交流，文档用中文。
- **角色**：Claude 以产品经理 + 技术负责人的身份推进，每轮给出**带推荐方案的问题**（表格形式），用户常以"都同意"一次确认。
- **文档规则**：
  - 只把**已确认**的内容写入 `docs/01–05`；未确认的放 [open-questions.md](./open-questions.md)。
  - 每个决策追加到 [decision-log.md](./decision-log.md)，编号连续（以 `decision-log.md` 最后一条为准，见本文件开头）。
  - 每次工作结束前更新本文件的"当前位置""断点""下次开始时"。
- **视觉风格**：阅读端为"B 小剧场"。示意图的本地副本在 [design/reader-style-options.html](./design/reader-style-options.html)，在线版在 https://claude.ai/artifact/3TwChZ4w49eXKvKkSMSW1z（需要登录用户本人的 claude.ai 账号）。

## 代码现状

- **前端**（`src/`，Vite + React 19 + TypeScript + Tailwind v4 + shadcn/ui on Base UI + react-query + react-router 8 + `motion`）：
  - 阅读端（小剧场风格，`src/pages/stage/`）：登录 `/login`、注册 `/register?code=`、书架 `/`、我的收藏 `/favorites`、阅读页 `/books/:id`。主题色和字体在 `src/index.css` 的 `@theme`；书架主题 `shelf-themes.ts`、背景装饰 `shelf-backdrop.tsx`、动效 `shelf-motion.ts`、翻开过渡 `book-opening.ts`、阅读排版 `reader-layout.ts`、翻页 `flip-book.tsx`。
  - 朗读与封面动画：`story-audio.ts`（Web Audio 单例播放器）、`use-read-aloud.ts`（自动朗读逻辑）、`read-aloud.tsx`（小喇叭、自动朗读开关）、`cover-video.tsx`（书架和阅读页的封面循环视频）；手绘图标 `doodle-*.tsx`（爱心、翻页箭头、小喇叭、音符）。
  - 管理后台（`src/pages/admin/`）：`/admin/books`、`/admin/books/:id`（AI 工作台 `ai-workbench.tsx`：流程说明 → 故事与角色 → 封面动画 → 生成进度 → 开页列表）、`/admin/invites`、`/admin/readers`、`/admin/ai`；进场动画用 `motion.tsx`。
  - 数据请求：`src/api/*.ts`（react-query hooks，类型 `src/api/types.ts`，AI 相关在 `src/api/ai.ts`）；路由守卫 `src/router/guards.ts`；会话过期跳回登录页（`src/lib/query-client.ts`）。
  - 添加到主屏幕：`public/manifest.webmanifest`、`public/icons/`（由 `uv run scripts/make-icons.py` 生成）。
- **后端**（`backend/app/`，FastAPI + SQLAlchemy 2 + SQLite + Alembic，uv 管理）：账户 / 会话（`auth/`）、邀请码（`invites/`）、读者（`readers/`）、绘本与收藏（`books/`，含读者的朗读 / 封面动画文件接口）、Worker（`worker/runner.py`：拆页、分析、草稿、音色、朗读、封面视频；视频任务的 `waiting` 调度）。
  - AI（`ai/`）：`catalog.py` / `settings.py` 配置；`providers/` 百炼 / 火山适配器（连接测试、模型列表、设计音色、合成、首尾帧视频）；`vision.py`（整本分析、单元草稿、朗读稿规则 `script_rules()`、封面动作描述）；`voices.py` 音色；`speech.py` 台词解析与朗读指纹；`audio.py` PyAV 拼接编码；`video.py` 首帧、封面提示词、视频去音轨；`spreads.py` 开页与单元；`book_router.py` 工作台接口。
  - 测试与检查：`cd backend && uv run pytest`（144 个）、`uv run ruff check . && uv run ruff format .`；前端 `npm run build`、`npm run lint`。
  - `backend/scripts/render_samples.py`：把 `samples/*.pdf` 渲染到 `samples/rendered/`，调整拆页参数时对比效果；`backend/scripts/ai_trial.py`：A0 试验脚本。
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
| 2026-09-28 | 修复 macOS 上 `scripts/dev.sh` 一启动就退出：系统自带 bash 3.2 不支持 `wait -n`，改为轮询子进程（顺带修好"启动阶段崩溃时不退出"）；Worker 恢复默认 SIGINT 处理，停止时不再等 5 秒被强杀 |
| 2026-09-29 | 修复 macOS 上 `scripts/dev.sh` 因 bash 3.2 不支持 `wait -n` 一启动就退出等问题（见上一条）；更新 `CLAUDE.md`。A3 步骤 1（D91）：百炼 `qwen-voice-design` 按音色描述设计角色音色（Worker `ai_voice` 任务），试听 WAV 与音色记录按"服务商 + 合成模型"保存；接口 `POST …/characters/{cid}/voice`、`GET …/ai/voices/{voice_id}`；角色卡片显示音色状态、失败原因、"描述已修改"，可试听、生成 / 重新生成；112 个后端测试通过；隔离环境浏览器实测（无效 Key 真实请求百炼得到"API Key 无效"提示） |
| 2026-09-29 | A3 步骤 2（D92）：Worker `ai_tts_unit` 逐行用说话人音色合成（百炼 `qwen3-tts-vd`，下载合成音频），PyAV 解码为 24kHz 单声道、行间停 0.4 秒、编码 AAC `.m4a`（faststart）；记录时长和"台词 + 音色"指纹，改了台词或音色显示"需要重新生成"；接口 `POST /admin/ai/units/{uid}/audio`、`POST …/ai/generate-all?type=audio`、`GET /admin/ai/units/{uid}/audio`；单元卡片新增"朗读"一栏（状态、时长、试听、生成 / 重新生成、缺音色或未保存时的提示），工具栏"全部生成朗读"；修复 A2 台词说话人下拉框显示数字而不是角色名；121 个后端测试通过；隔离环境浏览器实测 |
| 2026-09-29 | 朗读稿适度扩充（D93）：整本分析和单元重写的提示词改为"原文逐字保留 + 每页补充 2–3 句 + 无字页 1–2 句旁白"（`vision.py` 的 `script_rules()`），台词行新增 `added` 标记、后台显示"补充"；整本分析输出上限 16384 token、超时 300 秒；顺带修掉 `vision.py` 的两处超长行；122 个后端测试通过 |
| 2026-09-29 | A3 步骤 3（D94）：后台 Voice Ready 确认 / 取消（至少有一个单元已生成朗读；确认前提示未生成和需要重新生成的单元数）；书架接口加 `voice_ready` / `dance_ready`，书名前手绘音符；阅读接口加 `read_order`、`units`（只含已生成朗读的单元），读者音频接口 `GET /api/books/{id}/ai/audio/{uid}`；阅读页每页手绘小喇叭（对开各一、合并居中、单页左下）、顶部"自动朗读"开关（本机保存），Web Audio 单例播放器（书架点书、点小喇叭、打开开关时解锁）；`FlipBook` 新增 `onFlippingChange`、`overlay` 和按位置的可见页；修复 A2 朗读顺序下拉框显示英文值；126 个后端测试通过；隔离环境浏览器实测对开 / 合并 / 先右后左 / 竖屏单页 D74 / 从书架打开跳过封面 |
| 2026-09-29 | 开页的"朗读""动画"开关与"生成本开页朗读"（D95）：迁移 `3b7d2c9e4f10` 给 `ai_units` 加 `audio_enabled` / `video_enabled`；接口 `PATCH …/ai/spreads/{first_page}`、`POST …/ai/spreads/{first_page}/audio`；一键生成、单元生成、Voice Ready、阅读端、Worker 都遵守朗读开关；开页标题栏加两个开关和生成按钮；132 个后端测试通过；隔离环境浏览器实测 |
| 2026-09-29 | 按用户反馈精简工作台顶部卡片：改为"朗读"一行（进度条 + 状态统计 + 全部生成 + Voice Ready + "⋯"菜单里的朗读顺序），"分析整本故事"移到"故事与角色"卡片右上角（已分析过显示"重新分析整本故事"）；随后按用户建议把朗读进度独立成一张卡片，放在"故事与角色"和开页列表之间（顶部卡片只留流程说明）；A4 在这张进度卡片里加"动画"一行即可 |
| 2026-09-29 | 插入需求封面动画（D96）：迁移 `8c1f4a7d2e55`（`books` 加封面动画字段）和 `d4e6b1a9c3f7`（`jobs` 加 `payload`；原先放在同一个迁移里，用户的开发服务器已自动执行了前一版，导致缺列报错，拆成新迁移修复）；百炼首尾帧视频适配（上传凭证 + OSS 直传、提交、查询、下载）、`app/ai/video.py`、Worker 的 `waiting` 调度（15 秒查询、最多 3 个远程视频任务、查询出错重试、30 分钟超时、重启不重复提交）；接口生成 / 预览 / 启用封面动画，书架与阅读接口返回 `cover_video_url`；后台"封面动画"卡片，书架与阅读页封面叠循环视频；修复 `FlipBook` 首次排版时对开左右页算反（直接打开书或旋转后小喇叭 / 封面动画位置错位）；142 个后端测试通过；隔离环境浏览器实测 |
| 2026-09-29 | 封面动画真实生成跑通（百炼上传凭证 + OSS 直传 + 首尾帧任务，约 80 秒），但视频几乎不动；修正提示词并在描述为空时让视觉模型看封面写具体动作（D97），后台预览放大并加"放大预览"弹窗；144 个后端测试通过 |
| 2026-09-29 | 整理交接文档：一句话现状、断点（合并已完成的 3–6 项，新增封面动画效果确认）、下次开始时（A4 复用视频管道、吸取 D97 提示词教训）、待做（已完成的 AI 里程碑收成摘要）、已知问题（火山限制、封面视频体积）、操作注意事项（改为 macOS 的做法、迁移注意事项）、代码现状（补上 A2–封面动画的模块）；同步 `CLAUDE.md` 的项目状态 |
