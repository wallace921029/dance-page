# 技术设计（AI 阶段）

> 状态：已确认 · A1（AI 配置）已实现 · 最后更新 2026-09-28

本文把 AI 阶段的需求（D61–D79，见 [产品概述](./01-product-overview.md)、[阅读端](./02-reader.md#后续ai-阶段)、[Admin](./03-admin.md#后续ai-阶段)）落到技术方案上。第一期的架构、部署、文件访问方式沿用 [05 技术设计](./05-tech-design.md)，这里只写新增和改动的部分。

## 1. 总体思路

```
管理员（绘本详情页 · 页面模块）
   │ 分析整本故事 / 编辑草稿 / 设计音色 / 生成朗读、动画 / 确认 Voice Ready、Dance Ready!
   ▼
FastAPI ── 写入 jobs 表 ──► Worker
                              ├── 视觉模型（OpenAI 兼容接口）：分析故事、角色、台词、动作描述
                              ├── 语音：设计 / 选择音色，逐行合成后拼成一段音频
                              └── 视频：提交首尾帧任务 → 定时查询 → 下载保存
                              结果写入 DATA_DIR/books/{id}/ai/ 和数据库
阅读端 ◄── 只读取已确认（Voice Ready / Dance Ready!）的产物，不触发任何 AI 调用
```

- **不引入新服务**：仍是 api + worker 两个进程、SQLite、本地磁盘。
- **服务商适配层**：`app/ai/providers/` 下每家一个适配器，对上层提供统一接口（`analyze`、`design_voice`、`synthesize`、`submit_video` / `poll_video`）。切换服务商只是换一个适配器（D76）。
- **生成类的外部调用只在 Worker 里发生**，API 进程只负责读写数据库和文件；API Key 不出服务器。唯一的例外是后台的"测试连接"：请求很小，由 API 进程同步执行（超时 20 秒）。
- **不走系统代理**：请求服务商时不读取 `HTTP(S)_PROXY` / `ALL_PROXY` 环境变量（`trust_env=False`）。两家都是国内服务，服务器直连即可；开发机上的系统代理（如 `socks://`）反而会让请求失败。

## 2. 服务商对接

| 能力 | 阿里云百炼 | 火山引擎 |
| --- | --- | --- |
| 分析故事 / 台词（视觉模型） | Qwen3.5 起的通用模型原生多模态，能直接看图（默认 `qwen3.8-max`，百炼文档对看图任务的推荐），旧的 VL 系列也可用；OpenAI 兼容接口 `https://dashscope.aliyuncs.com/compatible-mode/v1` | 豆包视觉模型，OpenAI 兼容接口 `https://ark.cn-beijing.volces.com/api/v3` |
| 音色 | **按描述设计音色**：`qwen-voice-design`（千问 TTS）或 CosyVoice 的 `voice-enrollment`，返回音色 ID 和试听音频 | **没有按描述设计音色的接口**：从内置的现成音色清单里由视觉模型按提示词挑最接近的，管理员可换（D72 的后备方案） |
| 朗读合成 | 设计出的音色只能用于创建时指定的合成模型（如 `qwen3-tts-vd-*`、`cosyvoice-v3*`） | 豆包语音合成（支持情绪、语气控制），接口 `https://openspeech.bytedance.com/api/v3/tts/unidirectional`；用豆包语音控制台（新版）单独签发的 API Key，放在请求头 `X-Api-Key`，模型即请求头 `X-Api-Resource-Id`（如 `seed-tts-2.0`）（D83） |
| 首尾帧视频 | 通义万相 `wan2.2-kf2v-flash`（480P / 720P / 1080P，**时长固定 5 秒**）、`wanx2.1-kf2v-plus`（仅 720P）；异步任务，结果链接 24 小时有效 | Seedance 系列的首尾帧模式；时长、清晰度可选，具体范围以方舟文档为准，试验时确认；异步任务 |

- **两家的视觉模型共用一个"OpenAI 兼容"适配器**，只是 Base URL、Key、模型名不同。
- **图片以 base64 传给服务商**：绘本图片在登录后才能访问，不能给第三方公开链接。两家都支持 `data:image/...;base64,` 形式。
- **视频时长、清晰度的可选项跟随所选模型**（D77）：适配器声明自己支持的取值，后台界面只显示可选的（如万相首尾帧只能选 5 秒）。
- **音色与"服务商 + 合成模型"绑定**（D78）：换了朗读服务商或合成模型，角色需要重新设计 / 选择音色，旧音色记录保留，切回来还能用。

## 3. AI 配置

- **API Key 按服务商填一次**：百炼一个 Key；火山有两个——方舟一个 Key，豆包语音另有一个 Key（新版语音控制台只签发一个 API Key，不再需要旧版的 App ID 和 Access Token，D83）。两家都填好后，切换只需改下拉框。
- **每种能力单独选**：服务商、模型名、Base URL（预填默认值，一般不用改）。视频另有默认时长、清晰度（D79）。
- **Key 写在服务器的 `.env` 里**（D82，撤回了 D80 的"后台录入、加密存库"）：

  | 环境变量 | 说明 |
  | --- | --- |
  | `DASHSCOPE_API_KEY` | 阿里云百炼 API Key |
  | `VOLCENGINE_ARK_API_KEY` | 火山方舟 API Key（故事与台词识别、视频） |
  | `VOLCENGINE_SPEECH_API_KEY` | 豆包语音 API Key（朗读），在豆包语音控制台（新版）获取，与方舟的 Key 不是同一个 |

  修改后重启服务生效。后台"AI 配置"页只显示每项是否已设置（密钥只显示末 4 位），接口永远不返回完整的 Key。服务商、模型、Base URL、视频默认参数仍在后台选择，存在 SQLite 里。
- **选择模型**（D84）：模型名可以手动输入，也可以点"选择模型"从下拉列表里选。列表 = 内置推荐（排最前）+ 服务商的模型列表，只在打开下拉时请求（免费查询，前端缓存 5 分钟）：

  | 能力 | 百炼（`/compatible-mode/v1/models`，只有模型名） | 火山（方舟 `/api/v3/models`，带类别、输入方式、状态） |
  | --- | --- | --- |
  | 故事与台词识别 | Qwen 3.5 及以后的通用模型（含 omni）、QVQ、旧的 `-vl` 系列；去掉 OCR、实时语音、同传、向量模型。按版本从新到旧排序，同一版本里带日期的快照和预览版排后面（百炼列表里的时间与模型新旧对不上） | 类别为 VLM、能输入图片 |
  | 朗读 | 名字含 `tts-vd` / `cosyvoice` 的（能用设计出的音色）；列表里通常没有，靠内置推荐 | 豆包语音没有列模型的接口，只给 `seed-tts-2.0` / `seed-tts-1.0` |
  | 动画视频 | 名字含 `kf2v` 的；列表里通常没有，靠内置推荐 | 能输入图片、输出视频的；去掉已下线（Shutdown）的，即将下线（Retiring）的排最后并标注，标明支持首尾帧（`first_last_frame`）的排前面 |

  列表只说明平台上有这个模型，不代表账号已开通，选好后用"测试连接"确认。
- **连接测试**：每种能力一个"测试连接"按钮，测试的是已保存的设置：
  - 故事与台词识别（两家）：发一条极短的对话，验证 Base URL、Key 和模型名；
  - 百炼的朗读、视频：没有免费的测试接口，先用"列出模型"验证 Key，模型名在第一次生成时验证；
  - 火山的视频：查询视频任务列表（不产生费用）验证方舟 Key；
  - 火山的朗读：暂不支持测试，接入朗读时补上。

## 4. 数据模型

新增的表和字段（第一期的表不动）：

```
ai_capabilities                    # 每种能力当前用哪家（A1 已实现；没有记录时默认百炼）
  capability ('vision' | 'tts' | 'video') 主键
  provider, updated_at

ai_capability_configs              # 某种能力在某家服务商上的设置，两家各存一份（A1 已实现）
  (capability, provider) 主键        # 切换服务商后再切回来，原来的设置还在
  model, base_url
  options（JSON：视频默认时长、清晰度）, updated_at

books 新增
  story                            # 整本故事（大模型草稿，管理员可改）
  read_order ('left_first' | 'right_first'，默认 left_first，D69)
  voice_ready_at, dance_ready_at    # 为空表示未确认；两者相互独立（D67）

characters                         # 故事里的角色，含旁白
  id, book_id, name, is_narrator, voice_prompt, sort_order

character_voices                   # 角色在某家服务商 + 合成模型上的音色（D78）
  id, character_id, provider, tts_model,
  voice_id（服务商返回的音色 ID，或火山现成音色的编号）,
  voice_prompt_used, created_at
  唯一：(character_id, provider, tts_model)

ai_units                           # 生成单元：单页，或合并的左右两页（D71）
  id, book_id, first_page_index, page_count (1 | 2)
  lines（JSON：[{character_id, text}]，逐行标注说话人，可为空）
  motion_prompt                    # 动作描述
  audio_status / video_status ('none' | 'queued' | 'running' | 'ready' | 'failed')
  audio_error / video_error
  audio_source_hash                # 生成音频时"台词 + 音色"的哈希；与当前不一致即显示"需要重新生成"
  video_source_hash                # 生成视频时"动作描述 + 时长 + 清晰度"的哈希
  audio_duration_ms, video_duration_s, video_resolution
  audio_version, video_version     # 重新生成后加 1，拼进文件地址让缓存失效

jobs 新增
  unit_id, character_id（可空）
  type 新增：'ai_analyze_book' | 'ai_draft_unit' | 'ai_voice' | 'ai_tts_unit' | 'ai_video_unit'
  remote_task_id, next_poll_at     # 视频异步任务用
```

- **开页与生成单元**：开页的划分和阅读端对开完全一致（封面单独；`spread_start_page = 3` 时第 2 页单独）。"分别生成"= 两个单页单元，"合并生成"= 一个两页单元。切换模式时删除旧单元（连同已生成的文件）、建新单元。横版书每页一个单元，没有合并（D75）。
- **修改对开配对**：已有 AI 单元时，后台先提示"会清除受影响开页的朗读和动画"，确认后删除对不上的单元。
- **只给读者看已确认的内容**：`voice_ready_at` 为空时阅读端拿不到任何音频；`dance_ready_at` 为空时拿不到视频。

## 5. 文件存储

```
books/{book_id}/ai/
├── audio/{unit_id}.m4a          # 一个单元一段朗读（AAC）
├── video/{unit_id}.mp4          # 一个单元一段视频（H.264，去掉音轨）
└── voices/{character_voice_id}.wav   # 音色试听，仅后台使用
```

访问方式与页面图片相同：先校验登录（后台接口校验管理员），带版本参数和长期缓存头。

## 6. 生成流程

### 6.1 分析整本故事（`ai_analyze_book`）

1. 把全部页面缩到长边 1024px（够看清文字，省费用），连同页码一次发给视觉模型。
2. 要求模型按 JSON 返回：故事、角色（名字、是否旁白、音色提示词）、每页的台词（逐行标注说话人）、每页的动作描述，以及每个开页"左右是否同一场景"的建议。
3. 写入 `books.story`、`characters`，按建议建好生成单元（同一场景的开页默认"合并生成"），填入台词和动作描述草稿。管理员随后都可以改（D73）。

- 书的语言（中 / 英）写进提示词，台词保持原文语言。
- 重新分析会覆盖所有草稿，后台二次确认。

### 6.2 单元草稿（`ai_draft_unit`）

管理员切换某个开页的"分别 / 合并"后，可以单独让模型重新写这个单元的台词和动作描述（带上整本故事和角色表作为上下文，保证角色名一致）。

### 6.3 音色（`ai_voice`）

- **百炼**：用角色的音色提示词调用音色设计，得到音色 ID 和试听音频，存进 `character_voices`。
- **火山**：代码里维护一份适合讲故事的现成音色清单（编号 + 中文描述，如"温柔女声 · 讲故事"），由视觉模型按提示词挑一个，再用固定的试听句合成试听音频。
- 管理员在角色表里试听、改提示词重做，或从清单里手动换。

### 6.4 朗读（`ai_tts_unit`）

1. 检查单元里用到的每个角色在当前"服务商 + 合成模型"上都有音色，缺了就报错"请先为角色 X 生成音色"。
2. 逐行合成（请求 PCM / WAV），行与行之间插入 0.4 秒停顿，拼成一段。
3. 用 PyAV（pip 包，自带 FFmpeg 库，不需要装系统依赖）编码为 AAC `.m4a`，iPad Safari 和 Chrome 都能播放。
4. 记录时长和 `audio_source_hash`。

### 6.5 动画（`ai_video_unit`）

1. 准备首帧：单页单元直接用页面图；合并单元把左右两页拼成一张整图。**首帧和尾帧都用这张图**，视频从原画面开始、回到原画面结束，可以无缝循环，与静态页之间切换也看不出跳变。
2. 提示词 = 固定模板 + 动作描述，例如："镜头固定不动，背景和其他物体保持静止，保持原画的绘本画风、色彩和线条，画面中的文字不变。只有〔大怪兽慢慢眨眼，尾巴轻轻摆动〕，动作轻柔缓慢，最后回到初始姿态。"外加反向提示词（镜头移动、缩放、变形、画风变化、新增物体、文字抖动）。
3. 提交异步任务，记下 `remote_task_id`；Worker 每 15 秒查询一次，完成后立即下载（结果链接 24 小时有效），去掉音轨、把索引移到文件开头（便于边下边播）后保存。

### 6.6 Worker 调度

- 现在的 Worker 一次只做一个任务。视频任务一段要几分钟，不能让它堵住其他任务（如新上传的 PDF 拆页），所以视频任务拆成"提交"和"查询"两步：提交后任务进入等待状态，Worker 继续处理别的任务，到 `next_poll_at` 再查询。同时在服务商那边排队的视频任务最多 3 个（可配置）。
- **失败不自动重试**（D65）：任何一步出错即把任务和单元标记为失败，记录中文错误原因（如"服务商返回：余额不足"），管理员点"重试"重新入队。
- "全部生成"= 按每个开页已设好的方式，把需要生成（未生成、失败或草稿已修改）的单元都放进队列。

## 7. 接口

**管理端**（`require_admin`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/admin/ai/settings` | AI 配置：各服务商凭据（来自 `.env`）是否已设置（密钥只给末 4 位）、每种能力当前的服务商及两家各自的设置和可选项 |
| PUT | `/api/admin/ai/capabilities/{capability}` | 保存某种能力在某家服务商上的模型设置，并切换到这家 |
| POST | `/api/admin/ai/capabilities/{capability}/test` | 用已保存的设置测试当前服务商能否连通 |
| GET | `/api/admin/ai/capabilities/{capability}/models?provider=` | 可选模型：内置推荐 + 服务商的模型列表；取不到时附说明 |
| GET | `/api/admin/books/{id}/ai` | 故事、角色（含当前服务商下的音色）、开页与单元、各任务状态 |
| POST | `/api/admin/books/{id}/ai/analyze` | 分析整本故事 |
| PATCH | `/api/admin/books/{id}/ai` | 修改故事、朗读顺序 |
| POST / PATCH / DELETE | `/api/admin/books/{id}/ai/characters[/{cid}]` | 增删改角色 |
| POST | `/api/admin/books/{id}/ai/characters/{cid}/voice` | 设计 / 选择音色（可指定火山的音色编号） |
| PUT | `/api/admin/books/{id}/ai/spreads/{first_page}` | 设置开页为"分别 / 合并生成" |
| PATCH | `/api/admin/ai/units/{uid}` | 修改台词、动作描述 |
| POST | `/api/admin/ai/units/{uid}/draft` | 重新生成该单元的草稿 |
| POST | `/api/admin/ai/units/{uid}/audio` | 生成朗读 |
| POST | `/api/admin/ai/units/{uid}/video` | 生成动画（可临时指定时长、清晰度，D79） |
| POST | `/api/admin/books/{id}/ai/generate-all` | 全部生成（朗读或动画） |
| PUT / DELETE | `/api/admin/books/{id}/ai/voice-ready`、`/dance-ready` | 确认 / 取消 Voice Ready、Dance Ready! |

**阅读端**（`require_user`）

- `GET /api/books`：每本书加 `voice_ready`、`dance_ready`（书架标识，D70）。
- `GET /api/books/{id}`：加 `read_order` 和 `units`：`[{pages: [4, 5], audio_url, audio_duration_ms, video_url}]`。只有已确认的那一类产物才会出现。
- 音频、视频文件：`/api/books/{id}/ai/audio/{uid}`、`/api/books/{id}/ai/video/{uid}`。

## 8. 前端

### 8.1 后台：绘本详情页的"页面"模块

- 顶部："分析整本故事""全部生成朗读""全部生成动画"按钮，Voice Ready / Dance Ready! 确认开关。
- "故事与角色"卡片：故事文本、角色表（名字、音色提示词、试听、重新生成音色 / 换音色）。
- 每个开页一张卡片：左右页缩略图、"分别 / 合并生成"切换；每个单元显示台词（逐行：说话人下拉 + 文本）、动作描述、朗读和动画的状态、生成 / 重试按钮、试听 / 预览，草稿修改过的显示"需要重新生成"。
- 有任务进行中时轮询 `GET /ai`（与现在的拆页进度一样）。

### 8.2 阅读端

- **朗读按钮**：有朗读的页面，在页面下方角落显示一个手绘风格的小喇叭（与收藏、翻页按钮同一风格）。对开时两页各一个；合并单元只有一个。
- **自动朗读**：阅读页顶部加一个开关，状态存在 `localStorage`（D68）。翻页停稳后，按 `read_order` 依次播放当前可见单元；竖屏单页时，合并单元只在它的前一页自动读一次（D74）。翻页或离开时立即停止。
- **iPad 自动播放限制**：Safari 只允许在用户点击时开始播放声音。统一用 Web Audio（`AudioContext`）播放：孩子第一次点朗读按钮或打开自动朗读开关时解锁，之后翻页自动朗读就不再受限。需要真机验证。
- **动画**：在页面图片上叠一个 `<video muted playsinline loop>`，只给当前可见的页加载视频。翻页过程中暂停、显示静态图；翻页停稳后淡入播放。合并单元的视频宽度是页面的两倍，左页显示左半边、右页显示右半边（竖屏单页时同样处理，D74）。
- **书架标识**：`voice_ready` 的书在书名前显示音乐符号（D70）；`dance_ready` 的书在封面底部显示"Dance Ready!"剧场招牌。

## 9. 风险与验证

需要用样书 + 真实 API Key 试验后确定的事项（A0 试验已全面验证，D88）：

| 风险 / 试验项 | 验证结论（实测结果） |
| --- | --- |
| 视频画面文字抖动与画风跑偏 | **已验证通过**：百炼 `wan2.2-kf2v-flash`（720P，首尾帧相同）生成的视频中，绘本原画风保持极好，文字稳定无抖动，主角微动作自然。 |
| 首尾帧相同时模型是否几乎不动 / 对比单首帧 | **已验证通过**：首尾帧相同时首尾画面色差仅 5.0-6.6（几乎完全重合），循环播放极其平滑无跳跃；对比单首帧（火山 `doubao-seedance-1-0-pro-fast`）末帧漂移明显（色差 9.2-12.8），循环有明显顿挫。 |
| 火山 Seedance 2.x 首尾帧支持 | **实测确认**：火山方舟中用户已开通的 `doubao-seedance-1-0-pro-fast` 不支持首尾帧（`task_type flf2v does not support model`）；2.0 系列显示 `ModelNotOpen`。动画视频首选百炼。 |
| 视觉分析整本图片数量与耗时 | **已验证通过**：全书 30 页长边缩至 800px（JPEG 75%）一次发送给百炼 `qwen3.8-flash`，耗时 150s 稳定返回完整 JSON，准确提取角色、逐行台词、动作描述与开页建议；单本费用不足 0.05 元。`qwen3.8-max` 耗时易超 180s。 |
| 角色音色设计与合成模型绑定 | **已验证通过**：百炼 `qwen-voice-design` 可通过文本提示词成功设计角色音色并生成试听音频，返回的 voice ID 完美支持 `qwen3-tts-vd-2026-01-26` 非实时合成。 |
| 多角色台词合成与拼接 | **已验证通过**：按角色音色逐行合成 WAV，行间插入 0.4s 静音后通过 PyAV（aac, 24000Hz, mono）编码为 `.m4a`，Safari 与 Chrome 完美播放。 |
| 豆包语音接口与权限 | **实测确认**：豆包语音使用 `X-Api-Key` + `X-Api-Resource-Id: seed-tts-2.0` 调用，当前账号返回 403 `requested resource not granted`，需在火山语音控制台开通实例权限。朗读首选百炼。 |

## 10. 开发顺序

| 里程碑 | 内容 | 完成标志 |
| --- | --- | --- |
| A1 AI 配置 | 读取 `.env` 里的服务商 Key、后台选择各能力的服务商和模型、连接测试、适配器骨架 | ✅ 后台能保存配置并测试通过 |
| A0 试验 | 用样书和 `.env` 里的 Key 验证：故事分析、音色设计 / 选择、逐行合成、首尾帧视频（含一个合并开页）。试验脚本读取同一份配置 | ✅ 验证通过（D88），结论已沉淀，输出样本在 `samples/ai-trial/` |
| A2 故事与草稿 | 分析整本故事、角色、开页 / 单元、草稿编辑、"页面"模块界面 | ← 下一步：一本书能生成并编辑全部草稿 |
| A3 朗读（第一步） | 音色设计 / 选择与试听、逐行合成、Voice Ready、阅读端朗读按钮与自动朗读、书架音乐符号 | 孩子在 iPad 上能听整本书的多角色朗读 |
| A4 动画（第二步） | 视频任务提交与查询、Dance Ready!、阅读端视频播放、剧场招牌 | 开页里的主角在 iPad 上循环动起来 |
