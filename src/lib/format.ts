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
