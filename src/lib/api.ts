import axios, { isAxiosError } from "axios";

export const api = axios.create({
  baseURL: "/api",
});

/** 从接口错误中取出给用户看的中文提示（后端统一返回 {"detail": "..."}） */
export function getErrorMessage(error: unknown, fallback = "操作失败，请稍后再试"): string {
  if (isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (!error.response) return "网络连接失败，请检查网络";
  }
  return fallback;
}

export function isUnauthorized(error: unknown): boolean {
  return isAxiosError(error) && error.response?.status === 401;
}
