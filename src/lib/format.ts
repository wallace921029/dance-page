import dayjs from "dayjs";

export function formatDateTime(value: string | null | undefined): string {
  return value ? dayjs(value).format("YYYY-MM-DD HH:mm") : "—";
}

export function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** 8 位邀请码显示为 K7M3-Q9TX */
export function formatInviteCode(code: string): string {
  return `${code.slice(0, 4)}-${code.slice(4)}`;
}

/**
 * 默认书名取文件名（与后端 title_from_filename 一致）。
 * 网上下载的文件名常带 "(作者) (来源站点)" 之类的后缀，由内向外去掉。
 */
export function titleFromFilename(filename: string): string {
  const dotIndex = filename.lastIndexOf(".");
  const stem = (dotIndex > 0 ? filename.slice(0, dotIndex) : filename).trim();
  let title = stem;
  while (true) {
    const stripped = title.replace(/\s*[(（][^()（）]*[)）]/g, "");
    if (stripped === title) break;
    title = stripped;
  }
  return (title.trim() || stem || "未命名绘本").slice(0, 100);
}

