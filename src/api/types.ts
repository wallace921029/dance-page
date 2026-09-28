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
}

export interface ReaderBook extends ShelfBook {
  language: Language | null;
  spread_start_page: SpreadStartPage;
  pages: BookPage[];
}
