// 与后端接口（backend/app/*/schemas.py）对应的类型

export type Role = "admin" | "reader";

export interface User {
  id: number;
  username: string;
  role: Role;
}

export type Language = "zh" | "en";
export type Orientation = "portrait" | "landscape";
export type Visibility = "listed" | "unlisted";
export type ProcessingStatus = "processing" | "ready" | "failed";
/** 跨页大图从第几页开始两两配对：2 → 2+3、4+5…；3 → 3+4、5+6… */
export type SpreadStartPage = 2 | 3;

export interface BookPage {
  index: number;
  width: number;
  height: number;
  url: string;
}

export interface AdminBook {
  id: string;
  title: string;
  original_filename: string;
  file_size: number;
  language: Language | null;
  orientation: Orientation | null;
  cover_page_index: number;
  page_count: number;
  spread_start_page: SpreadStartPage;
  spread_start_detected: SpreadStartPage | null;
  spread_start_override: SpreadStartPage | null;
  visibility: Visibility;
  processing_status: ProcessingStatus;
  processing_error: string | null;
  progress: { done: number; total: number } | null;
  cover_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminBookDetail extends AdminBook {
  pages: BookPage[];
}

export interface BookUpdate {
  title?: string;
  language?: Language | null;
  orientation?: Orientation;
  cover_page_index?: number;
  spread_start_override?: SpreadStartPage | null;
  visibility?: Visibility;
}

export type InviteStatus = "unused" | "used" | "expired" | "revoked";

export interface Invite {
  id: number;
  code: string;
  status: InviteStatus;
  created_at: string;
  expires_at: string;
  revoked_at: string | null;
  used_at: string | null;
  used_by: { id: number; username: string } | null;
}

export interface Reader {
  id: number;
  username: string;
  is_disabled: boolean;
  created_at: string;
  last_active_at: string | null;
}

// ---------- 阅读端 ----------

export interface ShelfBook {
  id: string;
  title: string;
  orientation: Orientation;
  page_count: number;
  cover_url: string;
  /** 封面宽高比，图片加载前就能排好封面框 */
  cover_aspect: number;
  is_favorite: boolean;
  favorited_at: string | null;
  /** 管理员确认过朗读（D70：书名前显示音乐符号） */
  voice_ready: boolean;
  dance_ready: boolean;
  /** 已启用的封面动画（D96），在书架和阅读页封面上循环播放 */
  cover_video_url: string | null;
}

/** 一个生成单元的朗读 / 动画；只有确认过的那一类产物才会出现 */
export interface ReaderUnit {
  /** 单页，或合并生成的左右两页 */
  pages: number[];
  /** 朗读（Voice Ready 后才有） */
  audio_url: string | null;
  audio_duration_ms: number | null;
  /** 开页动画（Dance Ready! 后才有）；合并单元的视频是两页宽，左页放左半边、右页放右半边（D74） */
  video_url: string | null;
}

export type ReadOrder = "left_first" | "right_first";

export interface ReaderBook extends ShelfBook {
  language: Language | null;
  spread_start_page: SpreadStartPage;
  pages: BookPage[];
  /** 书架封面用的是哪一页；阅读页只在它是第 1 页时播放封面动画 */
  cover_page_index: number;
  /** 对开时"分别生成"的两页的朗读顺序（D69） */
  read_order: ReadOrder;
  units: ReaderUnit[];
}

// ---------- AI 配置（backend/app/ai/schemas.py） ----------

export type AiProviderId = "dashscope" | "volcengine";
export type AiCapabilityId = "vision" | "tts" | "video";

export interface AiCredentialField {
  key: string;
  /** 在服务器 .env 里设置的环境变量名 */
  env_var: string;
  label: string;
  help: string;
  is_set: boolean;
  /** 只给末 4 位（"••••abcd"） */
  preview: string | null;
}

export interface AiProvider {
  id: AiProviderId;
  name: string;
  fields: AiCredentialField[];
}

export interface AiVideoOptions {
  durations: number[];
  resolutions: string[];
  default_duration: number;
  default_resolution: string;
}

export interface AiVideoSettings {
  duration: number;
  resolution: string;
}

export interface AiProviderConfig {
  provider: AiProviderId;
  model: string;
  base_url: string;
  options: Partial<AiVideoSettings>;
  /** false 表示还没保存过，以上是默认值 */
  saved: boolean;
  default_model: string;
  default_base_url: string;
  model_suggestions: string[];
  video_models: Record<string, AiVideoOptions>;
  video_fallback: AiVideoOptions | null;
  /** 这项能力在这家服务商上还缺哪些凭据（要在 .env 里设置的环境变量名） */
  missing_credentials: string[];
}

export interface AiCapability {
  id: AiCapabilityId;
  name: string;
  description: string;
  /** 当前使用的服务商 */
  provider: AiProviderId;
  configs: AiProviderConfig[];
}

export interface AiSettings {
  providers: AiProvider[];
  capabilities: AiCapability[];
}

export interface AiCapabilityUpdate {
  provider: AiProviderId;
  model: string;
  base_url: string;
  options: Partial<AiVideoSettings>;
}

export interface AiTestResult {
  status: "ok" | "failed" | "unsupported";
  message: string;
}

export interface AiModelOption {
  id: string;
  /** 如"推荐""即将下线" */
  note: string | null;
  retiring: boolean;
}

export interface AiModelList {
  models: AiModelOption[];
  /** 没能从服务商取到列表时的说明 */
  message: string | null;
}

// ---------- 绘本 AI 工作台（Milestone A2） ----------

export interface AiLineItem {
  character_id: number | null;
  text: string;
  /** 书上原文之外补充的内容（D93） */
  added?: boolean;
}

export interface CharacterVoice {
  id: number;
  provider: AiProviderId;
  tts_model: string;
  voice_prompt_used: string | null;
  created_at: string;
  /** 试听音频（WAV），仅后台可访问 */
  preview_url: string;
}

export type AiTaskStatus = "none" | "queued" | "running" | "ready" | "failed";

export interface Character {
  id: number;
  book_id: string;
  name: string;
  is_narrator: boolean;
  voice_prompt: string | null;
  sort_order: number;
  /** 当前朗读设置（服务商 + 合成模型）下的音色（D78） */
  voice: CharacterVoice | null;
  voice_status: AiTaskStatus;
  voice_error: string | null;
  /** 音色描述在生成音色后又改过 */
  voice_outdated: boolean;
}

export interface AiUnit {
  id: string;
  book_id: string;
  first_page_index: number;
  page_count: number;
  lines: AiLineItem[];
  motion_prompt: string | null;
  /** 开页的"朗读""动画"开关（D95） */
  audio_enabled: boolean;
  video_enabled: boolean;
  audio_status: AiTaskStatus;
  video_status: AiTaskStatus;
  audio_error: string | null;
  video_error: string | null;
  audio_source_hash: string | null;
  video_source_hash: string | null;
  audio_duration_ms: number | null;
  video_duration_s: number | null;
  video_resolution: string | null;
  audio_version: number;
  video_version: number;
  created_at: string;
  updated_at: string;
  /** 已生成的朗读（后台试听）；重新生成期间仍可听旧的 */
  audio_url: string | null;
  /** 台词或音色在生成朗读之后改过 */
  audio_outdated: boolean;
  /** 已生成的动画（后台预览）；重新生成期间仍可看旧的 */
  video_url: string | null;
  /** 动作描述或视频模型在生成动画之后改过 */
  video_outdated: boolean;
  /** 第 1 页是封面：由封面动画负责，不单独生成开页动画 */
  video_by_cover: boolean;
}

export interface Spread {
  index: number;
  left_page_index: number | null;
  right_page_index: number | null;
  mode: "single" | "separate" | "merged";
  /** 关闭后一键生成跳过、阅读端也不播放（D95） */
  audio_enabled: boolean;
  video_enabled: boolean;
  units: AiUnit[];
}

export interface AiJob {
  id: number;
  type: string;
  book_id: string;
  unit_id: string | null;
  character_id: number | null;
  /** waiting：视频已提交给服务商，等待查询 */
  status: "queued" | "running" | "waiting" | "done" | "failed";
  progress_done: number;
  progress_total: number;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

/** 封面动画（D96） */
export interface CoverVideo {
  motion_prompt: string | null;
  status: AiTaskStatus;
  error: string | null;
  /** 已生成的视频（后台预览） */
  video_url: string | null;
  resolution: string | null;
  duration_s: number | null;
  /** 动作描述或视频模型在生成之后改过 */
  outdated: boolean;
  /** 生成之后换了封面，旧动画对不上，读者看不到 */
  frame_changed: boolean;
  enabled_at: string | null;
}

export interface BookAi {
  story: string | null;
  read_order: ReadOrder;
  voice_ready_at: string | null;
  dance_ready_at: string | null;
  characters: Character[];
  spreads: Spread[];
  running_jobs: AiJob[];
  cover: CoverVideo;
  /** 当前动画视频模型可选的时长、清晰度，默认值来自 AI 配置（生成时可临时修改，D79） */
  video_options: AiVideoOptions | null;
}

export interface CharacterCreateInput {
  name: string;
  is_narrator?: boolean;
  voice_prompt?: string | null;
}

export interface CharacterUpdateInput {
  name?: string | null;
  is_narrator?: boolean | null;
  voice_prompt?: string | null;
  sort_order?: number | null;
}

export interface BookAiUpdateInput {
  cover_motion_prompt?: string | null;
  story?: string | null;
  read_order?: "left_first" | "right_first" | null;
}

export interface UnitUpdateInput {
  lines?: AiLineItem[] | null;
  motion_prompt?: string | null;
}

